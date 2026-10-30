"""Unit tests for AuthVault token parsing and switching."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from codex_timer.auth_vault import AuthVault


class TestAuthVault(unittest.TestCase):
    def test_parse_token_empty(self):
        info = AuthVault.parse_token_info({})
        self.assertEqual(info['email'], '')
        self.assertEqual(info['name'], '')

    def test_parse_token_jwt_simulation(self):
        # Base64 encoded payload: {"email": "test@domain.com", "name": "Tester"}
        payload_b64 = "eyJlbWFpbCI6ICJ0ZXN0QGRvbWFpbi5jb20iLCAibmFtZSI6ICJUZXN0ZXIifQ"
        dummy_jwt = f"header.{payload_b64}.sig"
        info = AuthVault.parse_token_info({'tokens': {'id_token': dummy_jwt}})
        self.assertEqual(info['email'], 'test@domain.com')
        self.assertEqual(info['name'], 'Tester')

    def test_import_and_saved_check(self):
        with tempfile.TemporaryDirectory() as td:
            fake_home = Path(td) / '.codex'
            fake_home.mkdir(parents=True)
            fake_auth = fake_home / 'auth.json'
            payload_b64 = "eyJlbWFpbCI6ICJ2YXVsdEBkb21haW4uY29tIiwgIm5hbWUiOiAiVmF1bHQgVXNlciJ9"
            fake_auth.write_text(json.dumps({'tokens': {'id_token': f'h.{payload_b64}.s'}}), encoding='utf-8')

            import codex_timer.auth_vault as av_mod
            orig_home = av_mod.DEFAULT_CODEX_HOME
            orig_vault = av_mod.VAULT_DIR
            try:
                av_mod.DEFAULT_CODEX_HOME = fake_home
                av_mod.VAULT_DIR = fake_home / 'auth_vault'
                
                self.assertFalse(AuthVault.is_current_desktop_saved())
                saved_em = AuthVault.import_current_desktop_account()
                self.assertEqual(saved_em, 'vault@domain.com')
                self.assertTrue(AuthVault.is_current_desktop_saved())

                # Test sync
                synced = AuthVault.sync_if_known_account()
                self.assertEqual(synced, 'vault@domain.com')
            finally:
                av_mod.DEFAULT_CODEX_HOME = orig_home
                av_mod.VAULT_DIR = orig_vault


if __name__ == "__main__":
    unittest.main()
