"""Configuration: env-var + optional local ``.env`` loading.

Secrets never live in code. Real tokens come from ``CHATURBATE_*`` environment
variables, optionally loaded from ``<repo-root>/.env`` (gitignored). Process
environment always wins over ``.env`` values.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def project_root() -> Path:
    """Repository root: ``CLAUDE_PROJECT_DIR`` (set by Claude Code) or package path.

    ``src/chaturbate_mcp/config.py`` -> ``parents[2]`` is the repo root, so this
    works under ``uv run`` from any cwd.
    """
    env_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if env_dir:
        return Path(env_dir).resolve()
    return Path(__file__).resolve().parents[2]


_loaded = False


def load_env() -> Path:
    """Load ``<repo-root>/.env`` once. Absent file is a harmless no-op."""
    global _loaded
    root = project_root()
    if not _loaded:
        load_dotenv(root / ".env", override=False)
        _loaded = True
    return root


@dataclass(frozen=True)
class Config:
    username: str | None
    stats_token: str | None
    events_token: str | None

    @property
    def stats_configured(self) -> bool:
        """Both username and stats token present (stats token also authorizes the affiliate API)."""
        return bool(self.username and self.stats_token)

    @property
    def events_configured(self) -> bool:
        return bool(self.username and self.events_token)


def get_config() -> Config:
    load_env()
    return Config(
        username=os.getenv("CHATURBATE_USERNAME") or None,
        stats_token=os.getenv("CHATURBATE_STATS_TOKEN") or None,
        events_token=os.getenv("CHATURBATE_EVENTS_TOKEN") or None,
    )


def resolve_account(username: str | None, token: str | None, *, events: bool = False) -> tuple[str, str]:
    """Merge per-call overrides with environment config.

    Raises ``ValueError`` (surfaced as a clean MCP tool error) when either half of
    a credential pair is missing. Never returns secrets in the message.
    """
    cfg = get_config()
    u = username or cfg.username
    if events:
        t = token or cfg.events_token
        env = "CHATURBATE_EVENTS_TOKEN"
    else:
        t = token or cfg.stats_token
        env = "CHATURBATE_STATS_TOKEN"
    if not u or not t:
        raise ValueError(
            f"Missing credentials: provide username/token arguments or set "
            f"CHATURBATE_USERNAME and {env} in the environment (or the project .env)."
        )
    return u, t
