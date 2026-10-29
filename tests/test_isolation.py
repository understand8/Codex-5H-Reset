"""Unit tests for subprocess sandboxing and CODEX_HOME environment isolation."""
import os
import sys
import unittest
import tempfile
from pathlib import Path

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from codex_timer.providers.codex import CodexCLIProvider
from codex_timer.config import ConfigManager


class TestIsolationAndProfiles(unittest.TestCase):
    def test_provider_environment_isolation(self):
        custom_home = r"C:\tmp\custom_codex_home"
        original_env_val = os.environ.get("CODEX_HOME")

        provider = CodexCLIProvider(codex_home=custom_home)
        self.assertEqual(provider.codex_home, custom_home)

        # Global os.environ must NOT be modified by simply instantiating provider
        self.assertEqual(os.environ.get("CODEX_HOME"), original_env_val)

    def test_config_profile_operations(self):
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
            temp_path = Path(tf.name)
        try:
            mgr = ConfigManager(state_file=temp_path)
            # Test adding a temporary profile
            test_pid = "_test_profile_999"
            test_path = r"C:\test\codex"
            mgr.add_profile(test_pid, "Test Name", test_path)
            profiles = mgr.get_profiles()
            self.assertIn(test_pid, profiles)
            self.assertEqual(profiles[test_pid]["name"], "Test Name")
            self.assertEqual(profiles[test_pid]["codex_home"], test_path)

            # Test switching
            old_active = mgr.get_active_profile_name()
            mgr.set_active_profile(test_pid)
            self.assertEqual(mgr.get_active_profile_name(), test_pid)
            self.assertEqual(str(mgr.get_active_codex_home()), str(Path(test_path)))

            # Cleanup
            mgr.set_active_profile(old_active)
            mgr.remove_profile(test_pid)
            self.assertNotIn(test_pid, mgr.get_profiles())
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()
