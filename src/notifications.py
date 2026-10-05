"""Notification Helper – sends webhook alerts for pipeline events."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Resilient import: requests is used but we don't want to hard-fail if absent
try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]


def send_notification(message: str, webhook_url: Optional[str] = None) -> bool:
    """Post a notification message to the configured webhook URL.

    Reads ``NOTIFY_WEBHOOK_URL`` from the environment (via :class:`~src.config.AppSettings`)
    when *webhook_url* is not supplied explicitly.

    Supports Slack-compatible JSON (``{"text": "…"}``) and Discord webhooks
    (``{"content": "…"}``).  The payload is sent as both keys so a single call
    works for either platform.

    Returns ``True`` if the notification was delivered successfully, ``False``
    otherwise (errors are logged but never re-raised so the pipeline continues).
    """
    # Lazy import to avoid circular deps and allow the module to load when
    # config is not yet initialised.
    from src.config import AppSettings  # noqa: PLC0415

    settings = AppSettings()
    url = webhook_url or settings.notify_webhook_url

    if not url:
        logger.debug("NOTIFY_WEBHOOK_URL not configured – skipping notification.")
        return False

    if _requests is None:
        logger.warning("'requests' library not installed – cannot send notification.")
        return False

    payload = {
        "text": message,      # Slack / generic webhook
        "content": message,   # Discord webhook
    }

    try:
        resp = _requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 201, 204):
            logger.info("Notification sent successfully: %s", message[:80])
            return True
        else:
            logger.warning(
                "Notification webhook returned HTTP %s: %s",
                resp.status_code,
                resp.text[:200],
            )
            return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send notification: %s", exc)
        return False
