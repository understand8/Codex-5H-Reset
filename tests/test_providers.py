"""Unit tests for Multi-CLI Provider abstractions."""
import os
import sys
import unittest

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from codex_timer.providers.codex import CodexCLIProvider
from codex_timer.providers.claude import ClaudeCLIProvider


class TestProviders(unittest.TestCase):
    def test_codex_window_extraction(self):
        provider = CodexCLIProvider()
        sample = {
            "rateLimits": {
                "primary": {
                    "windowDurationMins": 300,
                    "usedPercent": 45,
                    "resetsAt": 1700000000
                },
                "secondary": {
                    "windowDurationMins": 10080,
                    "usedPercent": 15,
                    "resetsAt": 1700500000
                }
            }
        }
        f5, wk = provider.extract_windows(sample)
        self.assertIsNotNone(f5)
        self.assertIsNotNone(wk)
        self.assertEqual(f5["windowDurationMins"], 300)
        self.assertEqual(f5["usedPercent"], 45)
        self.assertEqual(wk["windowDurationMins"], 10080)
        self.assertEqual(wk["usedPercent"], 15)

    def test_codex_window_extraction_swapped(self):
        provider = CodexCLIProvider()
        sample = {
            "rateLimits": {
                "primary": {
                    "windowDurationMins": 10080,
                    "usedPercent": 90,
                    "resetsAt": 1700500000
                },
                "secondary": {
                    "windowDurationMins": 300,
                    "usedPercent": 30,
                    "resetsAt": 1700000000
                }
            }
        }
        f5, wk = provider.extract_windows(sample)
        self.assertEqual(f5["windowDurationMins"], 300)
        self.assertEqual(f5["usedPercent"], 30)
        self.assertEqual(wk["windowDurationMins"], 10080)
        self.assertEqual(wk["usedPercent"], 90)

    def test_claude_provider_dummy(self):
        claude = ClaudeCLIProvider()
        self.assertEqual(claude.provider_id, "claude")
        self.assertEqual(claude.display_name, "Anthropic Claude Code CLI")
        self.assertFalse(claude.is_logged_in())
        limits = claude.read_limits()
        f5, wk = claude.extract_windows(limits)
        self.assertIsNone(f5)
        self.assertIsNone(wk)


if __name__ == "__main__":
    unittest.main()
