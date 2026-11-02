"""Notification Helper – sends alerts for pipeline events.

Supported channels (all optional, each fires independently when configured):

* **Generic webhook** – Slack-compatible / Discord via ``NOTIFY_WEBHOOK_URL``
* **Telegram** – Bot API via ``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_CHAT_ID``
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Telegram Bot API endpoint (base so the bot token never appears in code)
TELEGRAM_API_BASE = "https://api.telegram.org"

# Resilient import: requests is used but we don't want to hard-fail if absent
try:
    import requests as _requests
except ImportError:
    _requests = None  # type: ignore[assignment]


def _post_webhook(url: str, message: str) -> bool:
    """Post *message* to a Slack/Discord-compatible webhook *url*.

    Returns ``True`` on a 2xx response, ``False`` otherwise (never raises).
    """
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
        logger.warning(
            "Notification webhook returned HTTP %s: %s",
            resp.status_code,
            resp.text[:200],
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send notification: %s", exc)
        return False


def send_telegram(
    message: str,
    bot_token: Optional[str] = None,
    chat_id: Optional[str] = None,
) -> bool:
    """Post *message* to Telegram via the Bot API.

    Reads ``TELEGRAM_BOT_TOKEN`` and ``TELEGRAM_CHAT_ID`` from the environment
    (via :class:`~src.config.AppSettings`) when not supplied explicitly.

    Returns ``True`` if Telegram accepted the message, ``False`` otherwise
    (unconfigured, missing ``requests``, HTTP error or network failure — all
    logged but never re-raised so the pipeline continues).
    """
    from src.config import AppSettings  # noqa: PLC0415

    settings = AppSettings()
    token = (bot_token if bot_token is not None else settings.telegram_bot_token or "").strip()
    target = (chat_id if chat_id is not None else settings.telegram_chat_id or "").strip()

    if not token or not target:
        logger.debug("Telegram not configured – skipping Telegram notification.")
        return False

    if _requests is None:
        logger.warning("'requests' library not installed – cannot send Telegram notification.")
        return False

    url = f"{TELEGRAM_API_BASE}/bot{token}/sendMessage"
    payload = {"chat_id": target, "text": message}

    try:
        resp = _requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 201):
            logger.info("Telegram notification sent successfully: %s", message[:80])
            return True
        logger.warning(
            "Telegram API returned HTTP %s: %s",
            resp.status_code,
            getattr(resp, "text", "")[:200],
        )
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to send Telegram notification: %s", exc)
        return False


def send_notification(message: str, webhook_url: Optional[str] = None) -> bool:
    """Deliver *message* on every configured notification channel.

    Channels:

    * Generic webhook – explicit *webhook_url* or ``NOTIFY_WEBHOOK_URL``
      (Slack-compatible ``{"text": …}`` and Discord ``{"content": …}`` keys are
      both sent so one call works for either platform).
    * Telegram – ``TELEGRAM_BOT_TOKEN`` + ``TELEGRAM_CHAT_ID``.

    Returns ``True`` if **at least one** channel delivered the message,
    ``False`` if nothing was configured or every attempt failed (errors are
    logged but never re-raised so the pipeline continues).
    """
    # Lazy import to avoid circular deps and allow the module to load when
    # config is not yet initialised.
    from src.config import AppSettings  # noqa: PLC0415

    settings = AppSettings()
    url = webhook_url or settings.notify_webhook_url
    telegram_ready = settings.has_telegram_credentials()

    if not url and not telegram_ready:
        logger.debug("No notification channel configured – skipping notification.")
        return False

    delivered = False

    if url:
        delivered = _post_webhook(url, message)

    # Telegram fires whenever configured, even if the webhook already succeeded
    # (or failed) – both channels are best-effort and independent.
    telegram_ok = send_telegram(message)
    delivered = delivered or telegram_ok

    return delivered
