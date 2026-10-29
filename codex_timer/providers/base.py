"""Abstract Base Rate Limit Provider."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional


class BaseRateLimitProvider(ABC):
    """Interface for multi-CLI AI rate limit providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier, e.g. 'codex', 'claude'."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name, e.g. 'OpenAI Codex CLI'."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if CLI binary and prerequisites are installed."""
        pass

    @abstractmethod
    def is_logged_in(self) -> bool:
        """Check if local CLI authentication credentials exist."""
        pass

    @abstractmethod
    def read_limits(self, timeout: int = 35) -> Dict[str, Any]:
        """Fetch current rate limit status from CLI."""
        pass

    @abstractmethod
    def extract_windows(self, data: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Return (short_window, long_window), e.g. (5h_window, weekly_window)."""
        pass

    @abstractmethod
    def send_heartbeat(self, prompt: str) -> str:
        """Send a minimal heartbeat prompt in isolated mode to refresh window."""
        pass
