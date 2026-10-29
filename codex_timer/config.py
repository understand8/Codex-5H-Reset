"""Configuration and Profile Management for Codex-5H-Reset."""
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

DEFAULT_PROMPT = 'Reply with exactly OK. Do not use tools, read files, run commands, or perform any other actions.'
BASE_DIR = Path(__file__).resolve().parent.parent


def get_default_config_path() -> Path:
    """Resolve config location with fallback to user home directory."""
    env_cfg = os.environ.get('CODEX_TIMER_CONFIG')
    if env_cfg:
        return Path(env_cfg)
    local_cfg = BASE_DIR / 'settings.json'
    if local_cfg.exists():
        return local_cfg
    home_dir = Path.home() / '.codex_timer'
    try:
        home_dir.mkdir(parents=True, exist_ok=True)
        return home_dir / 'settings.json'
    except Exception:
        return local_cfg


class ConfigManager:
    """Thread-safe configuration & multi-account profile manager."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or get_default_config_path()
        self.data: Dict[str, Any] = self._default_config()
        self.load()

    def _default_config(self) -> Dict[str, Any]:
        return {
            'auto_active': True,
            'when': '',
            'next_at': None,
            'repeat_minutes': None,
            'poll_interval_seconds': 900,  # 15 minutes
            'prompt': DEFAULT_PROMPT,
            'handled_resets': [],
            'scheduled_reset': None,
            'show_overlay': False,
            'overlay_pinned': True,
            'overlay_alpha': 0.94,
            'overlay_normal_alpha': 0.94,
            'overlay_pinned_alpha': 0.38,
            'overlay_bg_color': '#181A1D',
            'overlay_border_color': '#2F333A',
            'overlay_x': 120,
            'overlay_y': 120,
            'active_profile': 'default',
            'profiles': {
                'default': {
                    'name': '默认账号',
                    'codex_home': str(Path.home() / '.codex'),
                    'enabled': True
                }
            },
            'webhooks': {
                'enabled': False,
                'provider': 'generic',  # 'dingtalk', 'feishu', 'wecom', 'telegram', 'serverchan', 'generic'
                'url': '',
                'token': '',
                'chat_id': '',
                'notify_on_refresh': True,
                'notify_on_success': True,
                'notify_on_failure': True
            }
        }

    def load(self) -> None:
        if not self.state_file.exists():
            return
        try:
            loaded = json.loads(self.state_file.read_text(encoding='utf-8'))
            self.data.update(loaded)
        except Exception:
            pass

    def save(self) -> None:
        try:
            tmp = self.state_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
            tmp.replace(self.state_file)
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        self.data[key] = value
        if auto_save:
            self.save()

    # --- Profile Support ---
    def get_profiles(self) -> Dict[str, Dict[str, Any]]:
        return self.data.get('profiles', {})

    def get_active_profile_name(self) -> str:
        return self.data.get('active_profile', 'default')

    def get_active_codex_home(self) -> Path:
        profiles = self.get_profiles()
        active = self.get_active_profile_name()
        profile_data = profiles.get(active, {})
        codex_home_str = profile_data.get('codex_home')
        if codex_home_str:
            return Path(codex_home_str)
        return Path.home() / '.codex'

    def add_profile(self, profile_id: str, name: str, codex_home: str) -> None:
        profiles = self.data.setdefault('profiles', {})
        profiles[profile_id] = {
            'name': name,
            'codex_home': codex_home,
            'enabled': True
        }
        self.save()

    def remove_profile(self, profile_id: str) -> None:
        if profile_id == 'default':
            return
        profiles = self.data.get('profiles', {})
        if profile_id in profiles:
            del profiles[profile_id]
            if self.data.get('active_profile') == profile_id:
                self.data['active_profile'] = 'default'
            self.save()

    def set_active_profile(self, profile_id: str) -> None:
        if profile_id in self.data.get('profiles', {}):
            self.data['active_profile'] = profile_id
            self.save()
