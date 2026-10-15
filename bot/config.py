"""
config.py — Central configuration for Discord Server OS.
TOKEN is intentionally NOT here — load it from Replit Secrets (env vars).
"""

import os


class Config:
    # ── Bot behaviour ─────────────────────────────────────────────────────────
    PREFIX: str = "!"
    TEST_GUILD_ID: int = None   # Set to your server ID for instant slash sync

    # ── Database ──────────────────────────────────────────────────────────────
    # Absolute path is computed in main.py; this fallback is for local dev.
    DB_PATH: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_os.db")

    # ── Economy ───────────────────────────────────────────────────────────────
    DAILY_REWARD: int       = 100
    WEEKLY_REWARD: int      = 500
    STARTING_BALANCE: int   = 50
    CURRENCY_NAME: str      = "coins"
    CURRENCY_SYMBOL: str    = "🪙"

    # ── AI ────────────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str  = os.getenv("ANTHROPIC_API_KEY", "")
    AI_MODEL: str           = "claude-3-haiku-20240307"
    AI_MAX_TOKENS: int      = 512
    AI_SYSTEM_PROMPT: str   = (
        "You are a helpful Discord bot assistant. "
        "Keep responses concise and Discord-friendly (no markdown headers). "
        "Be friendly, informative, and slightly witty."
    )

    # ── Moderation ────────────────────────────────────────────────────────────
    MOD_LOG_CHANNEL: str        = "mod-logs"
    MAX_WARNS_BEFORE_KICK: int  = 3
    MAX_WARNS_BEFORE_BAN: int   = 5

    # ── Automation ────────────────────────────────────────────────────────────
    WELCOME_CHANNEL: str    = "welcome"
    AUTO_ROLE: str          = ""
    LEAVE_CHANNEL: str      = "welcome"

    # ── Analytics ─────────────────────────────────────────────────────────────
    ANALYTICS_ENABLED: bool = True
    LEADERBOARD_SIZE: int   = 10
