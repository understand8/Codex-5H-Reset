"""AuthVault: Hot-swapping account tokens within the same CODEX_HOME to preserve all project sessions, history, and skills."""
import base64
import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional

DEFAULT_CODEX_HOME = Path.home() / '.codex'
VAULT_DIR = DEFAULT_CODEX_HOME / 'auth_vault'


class AuthVault:
    """Manages credentials within a shared ~/.codex directory so project sessions, history, and custom skills remain 100% shared across account swaps."""

    @staticmethod
    def get_vault_dir() -> Path:
        VAULT_DIR.mkdir(parents=True, exist_ok=True)
        return VAULT_DIR

    @staticmethod
    def parse_token_info(auth_data: Dict[str, Any]) -> Dict[str, str]:
        info = {'email': '', 'name': '', 'account_id': ''}
        id_tok = auth_data.get('tokens', {}).get('id_token', '')
        if id_tok and '.' in id_tok:
            try:
                payload_b64 = id_tok.split('.')[1]
                payload_b64 += '=' * ((4 - len(payload_b64) % 4) % 4)
                payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode()))
                info['email'] = payload.get('email', '')
                info['name'] = payload.get('name', '')
                info['account_id'] = payload.get('sub', '')
            except Exception:
                pass
        return info

    @classmethod
    def get_active_account_info(cls) -> Dict[str, Any]:
        auth_file = DEFAULT_CODEX_HOME / 'auth.json'
        if not auth_file.exists():
            return {'email': '', 'name': '', 'logged_in': False}
        try:
            data = json.loads(auth_file.read_text(encoding='utf-8'))
            info = cls.parse_token_info(data)
            info['logged_in'] = True
            return info
        except Exception:
            return {'email': '', 'name': '', 'logged_in': False}

    @classmethod
    def get_desktop_auth_mtime(cls) -> float:
        auth_file = DEFAULT_CODEX_HOME / 'auth.json'
        if not auth_file.exists():
            return 0.0
        try:
            return auth_file.stat().st_mtime
        except Exception:
            return 0.0

    @classmethod
    def is_current_desktop_saved(cls) -> bool:
        info = cls.get_active_account_info()
        email = info.get('email')
        if not email or not info.get('logged_in'):
            return False
        vault_file = cls.get_vault_dir() / f"auth_{email}.json"
        return vault_file.exists()

    @classmethod
    def import_current_desktop_account(cls) -> Optional[str]:
        """One-click import current desktop CLI login into the Auth Vault."""
        return cls.backup_current_to_vault()

    @classmethod
    def sync_if_known_account(cls) -> Optional[str]:
        """Automatically updates the vault copy if the current desktop account is already in the vault."""
        info = cls.get_active_account_info()
        email = info.get('email')
        if not email or not info.get('logged_in'):
            return None
        vault_file = cls.get_vault_dir() / f"auth_{email}.json"
        if vault_file.exists():
            auth_file = DEFAULT_CODEX_HOME / 'auth.json'
            try:
                shutil.copy2(auth_file, vault_file)
            except Exception:
                pass
            return email
        return None

    @classmethod
    def backup_current_to_vault(cls) -> Optional[str]:
        auth_file = DEFAULT_CODEX_HOME / 'auth.json'
        if not auth_file.exists():
            return None
        info = cls.get_active_account_info()
        email = info.get('email')
        if not email:
            email = 'default'
        vault_file = cls.get_vault_dir() / f"auth_{email}.json"
        shutil.copy2(auth_file, vault_file)
        return email

    @classmethod
    def list_saved_accounts(cls) -> List[Dict[str, str]]:
        accounts = []
        cls.get_vault_dir()
        for f in VAULT_DIR.glob('auth_*.json'):
            try:
                data = json.loads(f.read_text(encoding='utf-8'))
                info = cls.parse_token_info(data)
                accounts.append({
                    'email': info.get('email') or f.stem.replace('auth_', ''),
                    'name': info.get('name', ''),
                    'file': str(f)
                })
            except Exception:
                pass
        return accounts

    @classmethod
    def switch_to_account(cls, email: str) -> bool:
        vault_file = cls.get_vault_dir() / f"auth_{email}.json"
        if not vault_file.exists():
            return False
        # Save current active first before swapping
        cls.backup_current_to_vault()
        # Overwrite ~/.codex/auth.json
        target = DEFAULT_CODEX_HOME / 'auth.json'
        shutil.copy2(vault_file, target)
        return True
