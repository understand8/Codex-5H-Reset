"""Unit tests for scheduler core algorithms and alignment engine."""
import os
import sys
import time
import unittest

# Ensure repo root is on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from codex_timer.core import five_hour, reset_target, refresh_evidence, SchedulerEngine
from codex_timer.config import ConfigManager


class TestCoreScheduler(unittest.TestCase):
    def setUp(self):
        self.mock_payload = {
            "rateLimits": {
                "primary": {
                    "windowDurationMins": 300,
                    "usedPercent": 75,
                    "resetsAt": int(time.time()) + 3600
                },
                "secondary": {
                    "windowDurationMins": 10080,
                    "usedPercent": 20,
                    "resetsAt": int(time.time()) + 86400 * 3
                }
            },
            "ordinaryUsageAllowed": True
        }

    def test_five_hour_extraction(self):
        f5_map = five_hour(self.mock_payload)
        self.assertIn("codex/primary", f5_map)
        f5 = f5_map["codex/primary"]
        self.assertEqual(f5.get("windowDurationMins"), 300)
        self.assertEqual(f5.get("usedPercent"), 75)

    def test_five_hour_fallback_secondary(self):
        payload = {
            "rateLimits": {
                "primary": {
                    "windowDurationMins": 10080,
                    "usedPercent": 10,
                    "resetsAt": int(time.time()) + 5000
                },
                "secondary": {
                    "windowDurationMins": 300,
                    "usedPercent": 50,
                    "resetsAt": int(time.time()) + 1800
                }
            }
        }
        f5_map = five_hour(payload)
        self.assertIn("codex/secondary", f5_map)
        f5 = f5_map["codex/secondary"]
        self.assertEqual(f5.get("windowDurationMins"), 300)
        self.assertEqual(f5.get("usedPercent"), 50)

    def test_reset_target_calculation(self):
        target = reset_target(self.mock_payload)
        self.assertIsNotNone(target)
        ident, stamp = target
        expected_stamp = self.mock_payload["rateLimits"]["primary"]["resetsAt"] + 120
        self.assertEqual(stamp, expected_stamp)
        self.assertTrue(ident.startswith("codex/primary:"))

    def test_reset_target_none_when_empty(self):
        target = reset_target({})
        self.assertIsNone(target)

    def test_boundary_missing_resets_at(self):
        payload = {"rateLimits": {"primary": {"windowDurationMins": 300, "resetsAt": None}}}
        self.assertIsNone(reset_target(payload))

    def test_boundary_empty_rate_limits(self):
        payload = {"rateLimits": {}}
        self.assertEqual(five_hour(payload), {})
        self.assertIsNone(reset_target(payload))

    def test_refresh_evidence_detects_reset(self):
        old_data = {"rateLimits": {"primary": {"windowDurationMins": 300, "resetsAt": 1000}}}
        new_data = {"rateLimits": {"primary": {"windowDurationMins": 300, "resetsAt": 2000}}, "ordinaryUsageAllowed": True}
        msg = refresh_evidence(old_data, new_data)
        self.assertIn("服务端已返回新的 5 小时窗口", msg)
        self.assertIn("普通额度可用", msg)

    def test_refresh_evidence_detects_no_reset(self):
        old_data = {"rateLimits": {"primary": {"windowDurationMins": 300, "resetsAt": 1000}}}
        new_data = {"rateLimits": {"primary": {"windowDurationMins": 300, "resetsAt": 1000}}}
        msg = refresh_evidence(old_data, new_data)
        self.assertIn("尚未确认 5 小时窗口刷新", msg)

    def test_scheduler_sync_reset(self):
        import tempfile
        from pathlib import Path
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
            temp_path = Path(tf.name)
        try:
            cfg = ConfigManager(state_file=temp_path)
            engine = SchedulerEngine(config=cfg, log_callback=lambda _: None)
            target_ts = int(time.time()) + 600
            engine.latest = {
                "rateLimits": {
                    "primary": {
                        "windowDurationMins": 300,
                        "usedPercent": 80,
                        "resetsAt": target_ts
                    }
                }
            }
            engine.sync_reset()
            self.assertEqual(engine.next_at, target_ts + 120)
            self.assertEqual(engine.scheduled_reset, f"codex/primary:{target_ts}")
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_process_bus_events_invokes_limits_and_error_callbacks(self):
        received_limits = []
        received_errors = []
        engine = SchedulerEngine(
            log_callback=lambda _: None,
            limits_callback=lambda data: received_limits.append(data),
            error_callback=lambda err: received_errors.append(err)
        )
        sample_data = {"rateLimits": {"primary": {"windowDurationMins": 300, "usedPercent": 50}}}
        engine.bus.put(('limits', sample_data))
        engine.bus.put(('error', 'Network test failure'))
        engine.process_bus_events()

        self.assertEqual(len(received_limits), 1)
        self.assertEqual(received_limits[0], sample_data)
        self.assertEqual(len(received_errors), 1)
        self.assertEqual(received_errors[0], 'Network test failure')


if __name__ == "__main__":
    unittest.main()
