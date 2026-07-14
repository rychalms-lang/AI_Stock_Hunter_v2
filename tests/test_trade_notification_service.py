import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from trade_notification_service import (
    FakeEmailSender,
    build_html_body,
    build_subject,
    build_text_body,
    notify_trade_event,
    notification_status,
    sample_event,
)


class TradeNotificationServiceTest(unittest.TestCase):
    def env(self):
        return {
            "EMAIL_ADDRESS": "sender@example.com",
            "EMAIL_PASSWORD": "secret",
            "TRADE_EMAIL_NOTIFICATIONS_ENABLED": "true",
            "TRADE_EMAIL_RECIPIENT": "recipient@example.com",
            "TRADE_EMAIL_FROM_NAME": "AI Stock Hunter",
            "TRADE_EMAIL_MAX_RETRIES": "3",
        }

    def test_entry_subject(self):
        self.assertIn("Simulated Position Opened: HIMS", build_subject(sample_event("opened")))

    def test_exit_subject_includes_return(self):
        self.assertIn("HIMS Closed at +6.20%", build_subject(sample_event("closed")))

    def test_test_subject_prefix(self):
        self.assertTrue(build_subject(sample_event("opened"), test=True).startswith("TEST —"))

    def test_user_approved_subject(self):
        event = sample_event("opened")
        event["decision_authority"] = "user_approved_v8"
        self.assertIn("Approved Simulated Position Opened: HIMS", build_subject(event))

    def test_opening_html_renders_premium_template(self):
        body = build_html_body(sample_event("opened"), test=True)
        self.assertIn("AI STOCK HUNTER", body)
        self.assertIn("Simulated Position Opened", body)
        self.assertIn("max-width:640px", body)
        self.assertIn("#9bd23c", body)

    def test_closing_html_renders_trade_result(self):
        body = build_html_body(sample_event("closed"), test=True)
        self.assertIn("Simulated Position Closed", body)
        self.assertIn("Trade Result", body)
        self.assertIn("+$62.00", body)

    def test_opening_plain_text_renders_sections(self):
        body = build_text_body(sample_event("opened"), test=True)
        self.assertIn("POSITION SUMMARY", body)
        self.assertIn("RESEARCH SUMMARY", body)
        self.assertIn("RISK CONTROLS", body)

    def test_closing_plain_text_renders_sections(self):
        body = build_text_body(sample_event("closed"), test=True)
        self.assertIn("TRADE RESULT", body)
        self.assertIn("EXECUTION DETAILS", body)
        self.assertIn("ORIGINAL RESEARCH CONTEXT", body)

    def test_positive_and_negative_return_formatting(self):
        positive = build_html_body(sample_event("closed"))
        negative_event = sample_event("closed")
        negative_event["realized_pnl"] = -50
        negative_event["realized_return_pct"] = -5
        negative = build_html_body(negative_event)
        self.assertIn("+6.20%", positive)
        self.assertIn("-$50.00", negative)
        self.assertIn("-5.00%", negative)

    def test_humanized_management_and_quote_wording(self):
        event = sample_event("opened")
        event["governance_mode"] = "user_managed"
        user_body = build_text_body(event)
        event["governance_mode"] = "ai_assisted"
        assisted_body = build_text_body(event)
        event["governance_mode"] = "ai_managed"
        ai_body = build_text_body(event)
        self.assertIn("User Managed", user_body)
        self.assertIn("AI Assisted", assisted_body)
        self.assertIn("AI Managed", ai_body)
        self.assertIn("Delayed quote", ai_body)

    def test_visible_content_avoids_raw_enums_snake_case_and_iso_dates(self):
        rendered = build_text_body(sample_event("opened")) + build_html_body(sample_event("closed"))
        forbidden = ["ai_managed", "take_profit", "position_opened", "DELAYED", "test_pick_001"]
        for value in forbidden:
            self.assertNotIn(value, rendered)
        self.assertNotRegex(rendered, r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")

    def test_disclaimer_and_email_safety(self):
        body = build_html_body(sample_event("opened"))
        self.assertIn("Paper trading simulation only", body)
        self.assertNotIn("<script", body.lower())
        self.assertNotIn("tracking", body.lower())
        self.assertNotIn("EMAIL_PASSWORD", body)
        self.assertNotIn("secret", body.lower())

    def test_success_records_sent_once(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, self.env(), clear=False):
            sender = FakeEmailSender()
            event = sample_event("opened")
            first = notify_trade_event(event, state_dir=Path(temp_dir), sender=sender)
            second = notify_trade_event(event, state_dir=Path(temp_dir), sender=sender)
            self.assertEqual(first["status"], "sent")
            self.assertEqual(second["status"], "skipped")
            self.assertEqual(len(sender.messages), 1)

    def test_failure_is_recorded_without_rollback_exception(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, self.env(), clear=False):
            result = notify_trade_event(sample_event("opened"), state_dir=Path(temp_dir), sender=FakeEmailSender(fail=True))
            self.assertFalse(result["ok"])
            state = json.loads((Path(temp_dir) / "trade_notifications.json").read_text())
            record = next(iter(state["notifications"].values()))
            self.assertEqual(record["status"], "retry_pending")
            self.assertIn("Fake sender failure", record["failure_reason"])

    def test_retry_succeeds_once(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, self.env(), clear=False):
            event = sample_event("closed")
            notify_trade_event(event, state_dir=Path(temp_dir), sender=FakeEmailSender(fail=True))
            sender = FakeEmailSender()
            result = notify_trade_event(event, state_dir=Path(temp_dir), sender=sender)
            self.assertEqual(result["status"], "sent")
            self.assertEqual(len(sender.messages), 1)

    def test_max_retries_stop(self):
        env = {**self.env(), "TRADE_EMAIL_MAX_RETRIES": "1"}
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, env, clear=False):
            event = sample_event("opened")
            notify_trade_event(event, state_dir=Path(temp_dir), sender=FakeEmailSender(fail=True))
            result = notify_trade_event(event, state_dir=Path(temp_dir), sender=FakeEmailSender())
            self.assertEqual(result["status"], "failed")

    def test_disabled_notifications_record_disabled(self):
        env = {**self.env(), "TRADE_EMAIL_NOTIFICATIONS_ENABLED": "false"}
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, env, clear=False):
            result = notify_trade_event(sample_event("opened"), state_dir=Path(temp_dir), sender=FakeEmailSender())
            self.assertEqual(result["status"], "disabled")

    def test_missing_configuration_records_failure(self):
        env = {
            "TRADE_EMAIL_NOTIFICATIONS_ENABLED": "true",
            "EMAIL_ADDRESS": "",
            "EMAIL_PASSWORD": "",
            "TRADE_EMAIL_RECIPIENT": "",
        }
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, env, clear=False):
            result = notify_trade_event(sample_event("opened"), state_dir=Path(temp_dir), sender=FakeEmailSender())
            self.assertEqual(result["status"], "failed")

    def test_render_only_does_not_write_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            result = notify_trade_event(sample_event("closed"), state_dir=Path(temp_dir), dry_run=True, test=True)
            self.assertEqual(result["status"], "rendered")
            self.assertFalse((Path(temp_dir) / "trade_notifications.json").exists())

    def test_status_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, self.env(), clear=False):
            notify_trade_event(sample_event("opened"), state_dir=Path(temp_dir), sender=FakeEmailSender())
            status = notification_status(Path(temp_dir))
            self.assertTrue(status["enabled"])
            self.assertEqual(status["total_sent"], 1)


if __name__ == "__main__":
    unittest.main()
