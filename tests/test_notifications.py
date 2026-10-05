"""Unit tests for notification helper and daily completion counter."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.notifications import send_notification
from src.tracker.db import ApplicationTrackerDB


# ---------------------------------------------------------------------------
# send_notification tests
# ---------------------------------------------------------------------------


class TestSendNotification:
    """Tests for src.notifications.send_notification."""

    def test_returns_false_when_no_webhook_url(self):
        """No webhook configured → silently returns False, does not raise."""
        import os
        with patch.dict(os.environ, {"NOTIFY_WEBHOOK_URL": ""}, clear=False):
            with patch("src.notifications._requests") as mock_req:
                result = send_notification("hello")
        assert result is False
        mock_req.post.assert_not_called()

    def test_posts_to_webhook_and_returns_true_on_200(self):
        """When webhook URL is passed directly and returns 200, returns True."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("src.notifications._requests") as mock_req:
            mock_req.post.return_value = mock_resp
            result = send_notification("✅ Done", webhook_url="https://hooks.example.com/notify")

        assert result is True
        mock_req.post.assert_called_once()
        call_kwargs = mock_req.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
        assert "✅ Done" in payload.get("text", "")
        assert "✅ Done" in payload.get("content", "")

    def test_returns_false_on_non_200_response(self):
        """When webhook returns non-2xx, returns False without raising."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"

        with patch("src.notifications._requests") as mock_req:
            mock_req.post.return_value = mock_resp
            result = send_notification("msg", webhook_url="https://hooks.example.com/notify")

        assert result is False

    def test_returns_false_on_network_error(self):
        """Network exception is caught; returns False without raising."""
        with patch("src.notifications._requests") as mock_req:
            mock_req.post.side_effect = ConnectionError("timeout")
            result = send_notification("msg", webhook_url="https://hooks.example.com/notify")

        assert result is False

    def test_returns_false_when_requests_not_installed(self):
        """If requests library is absent, gracefully returns False."""
        import src.notifications as notif_mod

        original = notif_mod._requests
        notif_mod._requests = None
        try:
            result = send_notification("msg", webhook_url="https://hooks.example.com/notify")
        finally:
            notif_mod._requests = original

        assert result is False


# ---------------------------------------------------------------------------
# Daily completion counter tests
# ---------------------------------------------------------------------------


class TestDailyCompletionCounter:
    """Tests for ApplicationTrackerDB.increment_completion and get_today_count."""

    def _make_db(self) -> ApplicationTrackerDB:
        return ApplicationTrackerDB(in_memory=True)

    def test_get_today_count_starts_at_zero(self):
        """Fresh in-memory DB returns 0 completions for today."""
        db = self._make_db()
        assert db.get_today_count() == 0

    def test_increment_completion_returns_increasing_count(self):
        """Each call to increment_completion increases the count by 1."""
        db = self._make_db()
        assert db.increment_completion(daily_limit=10) == 1
        assert db.increment_completion(daily_limit=10) == 2
        assert db.increment_completion(daily_limit=10) == 3

    def test_get_today_count_after_increments(self):
        """get_today_count reflects all prior increments."""
        db = self._make_db()
        for _ in range(5):
            db.increment_completion(daily_limit=10)
        assert db.get_today_count() == 5

    def test_increment_to_exact_limit(self):
        """Counter reaches the daily limit correctly."""
        db = self._make_db()
        for _ in range(9):
            db.increment_completion(daily_limit=10)
        count = db.increment_completion(daily_limit=10)
        assert count == 10

    def test_notification_called_on_limit_in_pipeline(self):
        """Pipeline fires send_notification after the Nth successful resume."""
        from src.pipeline import ResumeAutomationPipeline
        from src.models.job import JobRecord

        pipeline = ResumeAutomationPipeline()
        pipeline.settings.daily_limit = 2  # lower limit for test

        # Pre-seed counter to 1 so next increment hits limit=2
        pipeline.db.increment_completion(daily_limit=2)

        fake_report = MagicMock()
        fake_report.overall_score = 90
        fake_pkg = MagicMock()

        with patch.object(pipeline, "_process_job_inner", return_value=(fake_report, fake_pkg)):
            with patch("src.pipeline.send_notification") as mock_notify:
                job = JobRecord(
                    job_id="j1",
                    source="test",
                    url="http://test.com",
                    title="Test Role",
                    company="TestCo",
                    location="Remote",
                    description_raw="Test job",
                )
                pipeline.process_job(job)
                mock_notify.assert_called_once()
                call_msg = mock_notify.call_args[0][0]
                assert "limit" in call_msg.lower()

    def test_error_notification_fired_on_exception(self):
        """Pipeline calls send_notification with error message when processing fails."""
        from src.pipeline import ResumeAutomationPipeline
        from src.models.job import JobRecord

        pipeline = ResumeAutomationPipeline()

        with patch.object(pipeline, "_process_job_inner", side_effect=RuntimeError("boom")):
            with patch("src.pipeline.send_notification") as mock_notify:
                job = JobRecord(
                    job_id="j2",
                    source="test",
                    url="http://test.com",
                    title="Failing Role",
                    company="ErrorCo",
                    location="Remote",
                    description_raw="Bad job",
                )
                with pytest.raises(RuntimeError):
                    pipeline.process_job(job)

                mock_notify.assert_called_once()
                call_msg = mock_notify.call_args[0][0]
                assert "❌" in call_msg
                assert "boom" in call_msg
