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


if __name__ == "__main__":
    unittest.main()
