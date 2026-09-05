from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.config import settings

DEMO_USER_ID = UUID(settings.demo_user_id)


class MemoryDatabase:
    """Enough tables for watchlist attention / checkout without Postgres."""

    def __init__(self) -> None:
        now = datetime.now(timezone.utc)
        self.users: dict[UUID, dict[str, Any]] = {
            DEMO_USER_ID: {
                "id": DEMO_USER_ID,
                "name": "Demo Trader",
                "email": "demo@groww.signal",
                "last_seen_at": now,
            }
        }
        self.watchlists: dict[UUID, list[str]] = {
            DEMO_USER_ID: ["RELIANCE", "TCS", "INFY", "HDFCBANK", "TATAMOTORS"]
        }
        self.snapshots: dict[UUID, list[dict[str, Any]]] = {DEMO_USER_ID: []}

    def get_user(self, user_id: UUID) -> dict[str, Any] | None:
        return self.users.get(user_id)

    def ensure_user(self, user_id: UUID) -> dict[str, Any]:
        user = self.users.get(user_id)
        if user is not None:
            return user
        user = {
            "id": user_id,
            "name": "Trader",
            "email": f"{user_id}@groww.signal",
            "last_seen_at": None,
        }
        self.users[user_id] = user
        self.watchlists.setdefault(user_id, ["RELIANCE", "TCS", "INFY"])
        self.snapshots.setdefault(user_id, [])
        return user

    def watchlist_symbols(self, user_id: UUID) -> list[str]:
        return list(self.watchlists.get(user_id, []))

    def latest_snapshots(self, user_id: UUID) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for row in self.snapshots.get(user_id, []):
            latest[row["symbol"]] = row
        return latest

    def replace_snapshots(self, user_id: UUID, rows: list[dict[str, Any]], seen_at: datetime) -> None:
        self.snapshots[user_id] = rows
        user = self.ensure_user(user_id)
        user["last_seen_at"] = seen_at
