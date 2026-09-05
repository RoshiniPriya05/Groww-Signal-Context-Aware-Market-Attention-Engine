from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import UUID
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db import connect, disconnect, get_pool, get_redis
from app import db as db_mod
from app.config import configured_cors_origins, validate_optional_integrations
from app.services.ai_story_service import generate_change_story
from app.services.snapshot_service import (
    checkout_session,
    engine_breakdown_for_symbol,
    get_session_delta,
    seed_demo_state,
)
from app.services.notification_service import register_watchlist_alert_token


class CheckoutBody(BaseModel):
    user_id: UUID = Field(description="User whose session snapshot should be captured")


class NotificationTokenBody(BaseModel):
    token: str = Field(min_length=1)


class AttentionStock(BaseModel):
    symbol: str
    company_name: str
    price: float
    price_change_pct: float
    mci_score: float
    priority: str
    breakdown: dict[str, float]
    summary: str
    data_quality: dict[str, Any]
    status: str


class AttentionWatchlistResponse(BaseModel):
    user_id: str
    time_away: str
    critical_count: int
    moderate_count: int
    unchanged_count: int
    stocks: list[AttentionStock]


class ChangeStoryResponse(BaseModel):
    headline: str
    why_it_matters: str
    what_changed: list[str]
    what_didnt: list[str]
    ai_explanation: str


COMPANY_NAMES = {
    "INFY": "Infosys",
    "TATAMOTORS": "Tata Motors",
    "HDFCBANK": "HDFC Bank",
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "ICICIBANK": "ICICI Bank",
    "SBIN": "State Bank of India",
    "BHARTIARTL": "Bharti Airtel",
    "ITC": "ITC",
    "LT": "Larsen & Toubro",
    "AXISBANK": "Axis Bank",
    "HINDUNILVR": "Hindustan Unilever",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "BAJFINANCE": "Bajaj Finance",
    "MARUTI": "Maruti Suzuki",
}


def _time_away(last_seen_at: str | None) -> str:
    if not last_seen_at:
        return "Just now"
    last_seen = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
    elapsed = max(datetime.now(timezone.utc) - last_seen, timedelta(0))
    total_minutes = int(elapsed.total_seconds() // 60)
    return f"{total_minutes // 60}h {total_minutes % 60}m"


def _attention_response(payload: dict[str, Any]) -> AttentionWatchlistResponse:
    stocks: list[AttentionStock] = []
    for row in payload["watchlist"]:
        priority = str(row["priority"]).lower()
        stocks.append(
            AttentionStock(
                symbol=row["symbol"],
                company_name=COMPANY_NAMES.get(row["symbol"], row["symbol"]),
                price=row["price"],
                price_change_pct=row["price_delta_pct"],
                mci_score=row["mci"],
                priority=priority,
                breakdown={
                    "price": row["z_price"],
                    "volume": row["z_volume"],
                    "relative": row["sector_relative_delta"],
                },
                summary=(
                    f"{row['symbol']} moved {row['price_delta_pct']:.2f}% with "
                    f"{row['volume_delta_pct']:.2f}% volume change."
                ),
                data_quality=row.get("data_quality", {"is_stale": False}),
                status=row.get("status", "LIVE"),
            )
        )

    critical_count = sum(stock.mci_score >= 75 for stock in stocks)
    moderate_count = sum(50 <= stock.mci_score < 75 for stock in stocks)
    unchanged_count = sum(stock.mci_score < 50 for stock in stocks)
    return AttentionWatchlistResponse(
        user_id=payload["user_id"],
        time_away=_time_away(payload["last_seen_at"]),
        critical_count=critical_count,
        moderate_count=moderate_count,
        unchanged_count=unchanged_count,
        stocks=stocks,
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    validate_optional_integrations()
    await connect()
    await seed_demo_state()
    yield
    await disconnect()


app = FastAPI(
    title="Groww Signal",
    description="Attention-engine stock watchlist API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    postgres_ok = False
    redis_ok = False
    try:
        value = await get_pool().fetchval("SELECT 1")
        postgres_ok = value == 1
    except Exception:
        postgres_ok = False
    try:
        redis_ok = (await get_redis().ping()) is True
    except Exception:
        redis_ok = False

    status = "ok" if postgres_ok and redis_ok else "degraded"
    return {
        "status": status,
        "service": "groww-signal",
        "postgres": postgres_ok,
        "redis": redis_ok,
        "memory_store": db_mod.using_memory_store,
    }


@app.get("/api/signals")
async def list_signals() -> dict:
    return {"signals": []}


@app.get("/api/v1/watchlist/attention")
async def watchlist_attention(user_id: UUID = Query(...)) -> AttentionWatchlistResponse:
    try:
        payload = await get_session_delta(user_id)
        return _attention_response(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/watchlist/story/{symbol}")
async def watchlist_story(
    symbol: str,
    user_id: UUID | None = Query(default=None),
) -> ChangeStoryResponse:
    try:
        engine = await engine_breakdown_for_symbol(symbol, user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    story = generate_change_story(engine)
    return ChangeStoryResponse(
        headline=story["headline"],
        why_it_matters=story["why_it_matters"],
        what_changed=story["what_changed_summary"],
        what_didnt=["No unchanged metrics were provided by the signal engine."],
        ai_explanation=story["action_context"],
    )


@app.post("/api/v1/session/checkout")
async def session_checkout(body: CheckoutBody) -> dict:
    try:
        return await checkout_session(body.user_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/notifications/register")
async def register_notification_token(body: NotificationTokenBody) -> dict[str, bool]:
    return {"registered": register_watchlist_alert_token(body.token)}
