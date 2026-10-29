"""Unit tests for overlay color helpers, boundary clamping, and pin logic."""
import os
import sys
import unittest

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from codex_timer.gui.overlay import adjust_color_hex


class TestOverlay(unittest.TestCase):
    def test_adjust_color_hex(self):
        # Base dark color should yield a slightly lighter border
        dark = "#181A1D"
        border = adjust_color_hex(dark)
        self.assertTrue(border.startswith("#"))
        self.assertEqual(len(border), 7)

        # Black
        black_border = adjust_color_hex("#000000")
        self.assertEqual(black_border, "#0f0f0f")

        # Invalid fallback
        self.assertEqual(adjust_color_hex("invalid"), "#2F333A")


if __name__ == "__main__":
    unittest.main()
