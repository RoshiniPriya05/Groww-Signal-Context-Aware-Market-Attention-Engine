"""FCM dispatch for high-attention signals.

Firebase is optional for local development. When credentials are not configured,
dispatch is skipped and the signal pipeline continues normally.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

from app.config import settings

logger = logging.getLogger(__name__)

ALERT_TOPIC = "watchlist_alerts"
HIGH_ATTENTION_THRESHOLD = 80
ALERT_DEDUPE_SECONDS = 300
_last_alert_at: dict[str, float] = {}


def _get_firebase_app() -> Any | None:
    if not settings.firebase_credentials_json:
        return None
    if firebase_admin._apps:
        return firebase_admin.get_app()

    try:
        service_account = json.loads(settings.firebase_credentials_json)
        return firebase_admin.initialize_app(credentials.Certificate(service_account))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        logger.warning("FCM credentials are invalid; push alerts are disabled: %s", exc)
        return None
    except Exception:
        logger.exception("Unable to initialize Firebase Admin; push alerts are disabled")
        return None


def send_high_attention_alert(symbol: str, mci_score: float, headline: str) -> str | None:
    """Send a topic alert when a signal reaches the high-attention threshold."""
    if mci_score < HIGH_ATTENTION_THRESHOLD:
        return None

    now = time.monotonic()
    alert_key = f"{symbol.upper()}:{int(mci_score)}"
    previous = _last_alert_at.get(alert_key)
    if previous is not None and now - previous < ALERT_DEDUPE_SECONDS:
        return None

    app = _get_firebase_app()
    if app is None:
        return None

    message = messaging.Message(
        notification=messaging.Notification(
            title=f"🚨 High Attention: {symbol.upper()} (MCI: {mci_score:.0f}/100)",
            body=headline,
        ),
        topic=ALERT_TOPIC,
    )
    message_id = messaging.send(message, app=app)
    _last_alert_at[alert_key] = now
    logger.info("Sent high-attention FCM alert for %s: %s", symbol.upper(), message_id)
    return message_id


def register_watchlist_alert_token(token: str) -> bool:
    """Subscribe a browser FCM token to the shared watchlist alert topic."""
    if not token or _get_firebase_app() is None:
        return False
    try:
        messaging.subscribe_to_topic([token], ALERT_TOPIC)
        return True
    except Exception:
        logger.exception("Unable to subscribe FCM token to watchlist alerts")
        return False