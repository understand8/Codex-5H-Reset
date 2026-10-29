"""Claude Code CLI Provider (Extension skeleton for future AI CLI integrations)."""
from typing import Dict, Any, Tuple, Optional
from .base import BaseRateLimitProvider


class ClaudeCLIProvider(BaseRateLimitProvider):
    @property
    def provider_id(self) -> str:
        return 'claude'

    @property
    def display_name(self) -> str:
        return 'Anthropic Claude Code CLI'

    def is_available(self) -> bool:
        # Placeholder for claude cli binary detection
        return False

    def is_logged_in(self) -> bool:
        return False

    def read_limits(self, timeout: int = 35) -> Dict[str, Any]:
        return {}

    def extract_windows(self, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        return None, None

    def send_heartbeat(self, prompt: str) -> str:
        raise NotImplementedError('Claude Code CLI 额度适配器正在开发中。')
