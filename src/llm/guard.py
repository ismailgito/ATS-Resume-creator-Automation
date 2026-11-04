"""Daily LLM usage guard: switch to offline mode when the provider's limit is hit.

Typical day with DAILY_LIMIT=10 and a provider that runs out after six resumes:

    resumes 1-6   written with the LLM
    resume 7      limit hit in the middle of it -> guard trips, the rest of that resume and
                  resumes 8-10 are written in offline (non-LLM) mode, nothing fails
    next day      the guard has rolled over, the LLM is tried again, and it falls back to
                  offline again as soon as the limit is hit

The state lives in a small JSON file (``LLM_STATE_PATH``), so a second run on the same day
does not waste time on calls that are known to fail. Delete it, or run
``python -m src.cli llm-reset``, after topping up credits to re-enable the LLM at once.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Provider messages that mean "out for the day / out of credit", so retrying is pointless.
HARD_LIMIT_MARKERS = (
    "insufficient_quota",
    "exceeded your current quota",
    "credit balance",
    "billing",
    "per day",
    "perday",
    "daily",
)

# Status codes for "too many requests" / "payment required"
RATE_LIMIT_STATUS = 429
PAYMENT_STATUS = 402

CONSECUTIVE_FAILURE_LIMIT = 3


def _redact(text: str) -> str:
    """Remove API keys from error text before it is logged or sent in a notification."""
    return re.sub(r"(key=|Bearer\s+|x-api-key[:=]\s*|x-goog-api-key[:=]\s*)[^&\s'\"]+", r"\1***", text, flags=re.I)


def classify_error(exc: BaseException) -> Tuple[str, str]:
    """Classify an LLM call failure.

    Returns ``(kind, detail)`` where kind is one of:
      * ``limit_hard``: quota or credit exhausted; switch to offline until tomorrow
      * ``limit_soft``: rate limit (HTTP 429) that may clear in seconds; worth a short retry
      * ``auth``: invalid key or no permission
      * ``other``: network problem, server error, unparseable answer, ...
    """
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    body = ""
    if response is not None:
        try:
            body = (response.text or "")[:500]
        except Exception:  # noqa: BLE001
            body = ""
    lowered = body.lower()
    hard = any(marker in lowered for marker in HARD_LIMIT_MARKERS)

    snippet = " ".join(body.split())[:140] if body else str(exc)[:140]
    detail = _redact(f"HTTP {status}: {snippet}" if status else snippet)

    if status == PAYMENT_STATUS:
        return "limit_hard", detail
    if status == RATE_LIMIT_STATUS:
        return ("limit_hard" if hard else "limit_soft"), detail
    if status in (400, 403) and hard:
        return "limit_hard", detail
    if status in (401, 403):
        return "auth", detail
    return "other", detail


def _local_today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _default_notify(message: str) -> None:
    try:
        from src.notifications import send_notification  # noqa: PLC0415

        send_notification(message)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Notification skipped: %s", exc)


class LLMUsageGuard:
    """Remembers, per calendar day, whether the LLM may still be used."""

    def __init__(
        self,
        path: Path,
        today: Callable[[], str] = _local_today,
        notifier: Optional[Callable[[str], None]] = None,
    ):
        self.path = Path(path)
        self._today = today
        self._notify = notifier or _default_notify
        self._session_off_reason: Optional[str] = None  # not persisted (e.g. broken API key)
        self._consecutive_failures = 0
        self._calls_llm = 0
        self._calls_offline = 0
        self._state = self._load()

    # ------------------------------------------------------------------ #
    # State
    # ------------------------------------------------------------------ #

    def _fresh(self) -> Dict[str, Any]:
        return {
            "date": self._today(),
            "limit_hit": False,
            "reason": "",
            "tripped_at": "",
            "llm_resumes": 0,
            "offline_resumes": 0,
        }

    def _load(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("date") == self._today():
                return {**self._fresh(), **data}
        except (OSError, ValueError):
            pass
        return self._fresh()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        except OSError as exc:
            logger.warning("Could not save LLM usage state to %s: %s", self.path, exc)

    def _roll_day(self) -> None:
        """A new calendar day starts with a clean slate, so the LLM is tried again."""
        if self._state.get("date") != self._today():
            logger.info("New day: LLM usage state reset, the LLM will be used again.")
            self._state = self._fresh()
            self._session_off_reason = None
            self._consecutive_failures = 0
            self._save()

    # ------------------------------------------------------------------ #
    # Decisions
    # ------------------------------------------------------------------ #

    def llm_available(self) -> bool:
        self._roll_day()
        return not self._state["limit_hit"] and self._session_off_reason is None

    def trip(self, reason: str) -> None:
        """Mark today's LLM limit as hit. Idempotent: only the first call notifies."""
        self._roll_day()
        if self._state["limit_hit"]:
            return
        self._state.update(
            limit_hit=True,
            reason=reason,
            tripped_at=datetime.now().isoformat(timespec="seconds"),
        )
        self._save()
        logger.warning("LLM limit reached (%s). Switching to offline mode until tomorrow.", reason)
        self._notify(
            f"⚠️ LLM usage limit reached ({reason}). {self._state['llm_resumes']} resume(s) finished "
            "with the LLM today; all remaining resumes switch to offline mode automatically. "
            "The LLM is used again tomorrow."
        )

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._calls_llm += 1

    def record_failure(self, detail: str) -> None:
        """Count a non-limit failure; after a few in a row stop trying the LLM for this run."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= CONSECUTIVE_FAILURE_LIMIT and self._session_off_reason is None:
            self._session_off_reason = detail
            logger.warning(
                "LLM failed %d times in a row (%s). Using offline mode for the rest of this run.",
                self._consecutive_failures,
                detail,
            )

    def note_offline_call(self) -> None:
        self._calls_offline += 1

    # ------------------------------------------------------------------ #
    # Per-resume bookkeeping
    # ------------------------------------------------------------------ #

    def start_resume(self) -> None:
        self._calls_llm = 0
        self._calls_offline = 0

    def current_mode(self) -> str:
        if self._calls_llm and self._calls_offline:
            return "LLM -> OFFLINE (limit reached during this resume)"
        if self._calls_llm:
            return "LLM"
        return "OFFLINE"

    def finish_resume(self, counted: bool = True) -> str:
        """Close the current resume, add it to today's totals, and return how it was written."""
        mode = self.current_mode()
        if counted:
            self._roll_day()
            # "LLM" only when every call went to the LLM; a resume that switched mid-way counts as offline
            key = "llm_resumes" if self._calls_llm and not self._calls_offline else "offline_resumes"
            self._state[key] += 1
            self._save()
        self.start_resume()
        return mode

    # ------------------------------------------------------------------ #
    # Reporting / manual control
    # ------------------------------------------------------------------ #

    def status(self) -> Dict[str, Any]:
        self._roll_day()
        return {
            **self._state,
            "llm_available": self.llm_available(),
            "session_off_reason": self._session_off_reason or "",
        }

    def reset(self) -> None:
        """Re-enable the LLM right away (for example after adding credits)."""
        self._state = self._fresh()
        self._session_off_reason = None
        self._consecutive_failures = 0
        self._save()


_GUARDS: Dict[Path, LLMUsageGuard] = {}


def get_guard(settings: Any) -> LLMUsageGuard:
    """One shared guard per state file, so parser, tailor and pipeline see the same state."""
    path = Path(settings.llm_state_path)
    if path not in _GUARDS:
        _GUARDS[path] = LLMUsageGuard(path)
    return _GUARDS[path]
