"""LLM usage limit -> automatic offline fallback -> LLM again the next day."""

import json
from pathlib import Path

import pytest
import requests

from src.config import AppSettings, PROJECT_ROOT
from src.ingest.job_sources import IngestionManager
from src.llm.client import BaseLLMClient, FallbackLLMClient, get_llm_client
from src.llm.guard import LLMUsageGuard, classify_error
from src.pipeline import ResumeAutomationPipeline


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def http_error(status: int, body: str = "", headers=None) -> requests.HTTPError:
    resp = requests.Response()
    resp.status_code = status
    resp._content = body.encode()
    resp.headers.update(headers or {})
    return requests.HTTPError(f"{status} error for url: https://x/?key=SECRET123", response=resp)


class ScriptedLive(BaseLLMClient):
    """Live client that plays back a list of results / exceptions."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def generate_json(self, system_prompt, user_prompt):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class StubOffline(BaseLLMClient):
    def generate_json(self, system_prompt, user_prompt):
        return {"source": "offline"}


@pytest.fixture
def clock():
    """Mutable fake calendar day for the guard."""
    day = {"value": "2026-11-04"}
    return day


@pytest.fixture
def guard(tmp_path, clock):
    messages = []
    g = LLMUsageGuard(tmp_path / "state.json", today=lambda: clock["value"], notifier=messages.append)
    g.messages = messages
    return g


QUOTA_BODY = '{"error": {"status": "RESOURCE_EXHAUSTED", "message": "You exceeded your current quota"}}'


# --------------------------------------------------------------------------- #
# Error classification
# --------------------------------------------------------------------------- #

def test_classify_error_kinds():
    assert classify_error(http_error(429, QUOTA_BODY))[0] == "limit_hard"
    assert classify_error(http_error(429, "slow down"))[0] == "limit_soft"
    assert classify_error(http_error(402))[0] == "limit_hard"
    assert classify_error(http_error(400, "Your credit balance is too low"))[0] == "limit_hard"
    assert classify_error(http_error(401, "bad key"))[0] == "auth"
    assert classify_error(http_error(500, "oops"))[0] == "other"
    assert classify_error(ValueError("not json"))[0] == "other"


def test_classify_error_never_leaks_api_key():
    _, detail = classify_error(requests.ConnectionError("failed for https://x/?key=SECRET123&alt=json"))
    assert "SECRET123" not in detail


# --------------------------------------------------------------------------- #
# FallbackLLMClient + guard
# --------------------------------------------------------------------------- #

def test_limit_switches_to_offline_and_stops_calling_the_llm(guard):
    live = ScriptedLive([{"source": "llm"}, {"source": "llm"}, http_error(429, QUOTA_BODY)])
    client = FallbackLLMClient(live, StubOffline(), guard, sleep=lambda s: None)

    assert client.generate_json("s", "u") == {"source": "llm"}
    assert client.generate_json("s", "u") == {"source": "llm"}
    # Third call hits the limit: answered offline, no exception
    assert client.generate_json("s", "u") == {"source": "offline"}
    calls_at_trip = live.calls
    # Every later call goes straight to offline, the provider is not contacted again
    for _ in range(5):
        assert client.generate_json("s", "u") == {"source": "offline"}
    assert live.calls == calls_at_trip

    assert len(guard.messages) == 1  # one notification, not one per call
    assert "limit" in guard.messages[0].lower()


def test_state_survives_restart_and_resets_next_day(tmp_path, clock, guard):
    guard.trip("HTTP 429: quota")

    # Same day, new process: still offline
    same_day = LLMUsageGuard(tmp_path / "state.json", today=lambda: clock["value"], notifier=lambda m: None)
    assert same_day.llm_available() is False

    # Next day: LLM is tried again, in an old process and in a new one
    clock["value"] = "2026-11-05"
    assert same_day.llm_available() is True
    assert LLMUsageGuard(tmp_path / "state.json", today=lambda: clock["value"]).llm_available() is True

    # ...and it can trip again that day
    same_day.trip("HTTP 429: quota again")
    assert same_day.llm_available() is False


def test_reset_reenables_llm_immediately(guard):
    guard.trip("quota")
    guard.reset()
    assert guard.llm_available() is True


def test_short_rate_limit_is_retried_without_switching(guard):
    live = ScriptedLive([http_error(429, "slow down", {"Retry-After": "3"}), {"source": "llm"}])
    waits = []
    client = FallbackLLMClient(live, StubOffline(), guard, sleep=waits.append)

    assert client.generate_json("s", "u") == {"source": "llm"}
    assert waits == [3.0]
    assert guard.llm_available() is True


def test_rate_limit_that_never_clears_switches_to_offline(guard):
    live = ScriptedLive([http_error(429, "slow down")] * 3)
    client = FallbackLLMClient(live, StubOffline(), guard, sleep=lambda s: None)

    assert client.generate_json("s", "u") == {"source": "offline"}
    assert live.calls == 3  # first try + 2 retries
    assert guard.llm_available() is False


def test_other_errors_are_raised_and_three_in_a_row_disable_llm_for_the_run(guard):
    live = ScriptedLive([http_error(500, "boom")] * 3)
    client = FallbackLLMClient(live, StubOffline(), guard, sleep=lambda s: None)

    for _ in range(3):
        with pytest.raises(requests.HTTPError):
            client.generate_json("s", "u")
    assert guard.llm_available() is False
    assert client.generate_json("s", "u") == {"source": "offline"}
    # Not a quota problem, so nothing is written for tomorrow
    assert guard.status()["limit_hit"] is False


def test_get_llm_client_wraps_live_provider_only_when_enabled(tmp_path):
    base = dict(llm_provider="gemini", gemini_api_key="k" * 20, llm_state_path=tmp_path / "s.json")
    assert isinstance(get_llm_client(AppSettings(**base)), FallbackLLMClient)
    assert not isinstance(get_llm_client(AppSettings(**base, llm_auto_fallback=False)), FallbackLLMClient)
    assert not isinstance(
        get_llm_client(AppSettings(llm_provider="offline", gemini_api_key=None, openai_api_key=None,
                                   anthropic_api_key=None, llm_state_path=tmp_path / "s.json")),
        FallbackLLMClient,
    )


# --------------------------------------------------------------------------- #
# Whole workflow: 10 resumes, limit hit in the middle of resume 7
# --------------------------------------------------------------------------- #

class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text
        self.headers = {}

    def raise_for_status(self):
        if self.status_code >= 400:
            resp = requests.Response()
            resp.status_code = self.status_code
            resp._content = self.text.encode()
            raise requests.HTTPError(f"{self.status_code} error", response=resp)

    def json(self):
        return json.loads(self.text)


def test_ten_resumes_with_limit_hit_during_the_seventh(tmp_path, monkeypatch):
    settings = AppSettings(
        llm_provider="gemini",
        gemini_api_key="k" * 20,
        output_dir=tmp_path / "out",
        llm_state_path=tmp_path / "llm-state.json",
        daily_limit=10,
    )
    ok_text = json.dumps({"candidates": [{"content": {"parts": [{"text": "{}"}]}}]})

    # 3 LLM calls per resume (parse, tailor, cover note): 6 full resumes, then the parse of
    # resume 7 works and its tailoring call hits the limit.
    state = {"calls": 0, "ok_calls": 6 * 3 + 1}

    def fake_post(url, **kwargs):
        state["calls"] += 1
        if state["calls"] <= state["ok_calls"]:
            return FakeResponse(200, ok_text)
        return FakeResponse(429, QUOTA_BODY)

    monkeypatch.setattr("src.llm.client.requests.post", fake_post)

    pipeline = ResumeAutomationPipeline(settings=settings)
    job = IngestionManager.from_file(PROJECT_ROOT / "data/sample-jobs/01-perf-mktg-manager.json")[0]

    modes = []
    for _ in range(10):
        _, pkg = pipeline.process_job(job, force_generate=True)
        assert pkg is not None and Path(pkg.resume_pdf_path).exists()
        modes.append(pipeline.last_generation_mode)

    assert modes[:6] == ["LLM"] * 6
    assert modes[6].startswith("LLM -> OFFLINE")
    assert modes[7:] == ["OFFLINE"] * 3

    # After the limit the provider was never contacted again
    assert state["calls"] == 6 * 3 + 2
    totals = pipeline.guard.status()
    assert (totals["llm_resumes"], totals["offline_resumes"]) == (6, 4)
    assert totals["limit_hit"] is True

    # The change log of an offline resume says so
    last_log = Path(pkg.change_log_path).read_text(encoding="utf-8")
    assert "**Generated with:** OFFLINE" in last_log

    # Next day: the LLM is used again
    pipeline.guard._today = lambda: "2099-01-01"
    state["ok_calls"] = 10**6
    _, pkg = pipeline.process_job(job, force_generate=True)
    assert pipeline.last_generation_mode == "LLM"
