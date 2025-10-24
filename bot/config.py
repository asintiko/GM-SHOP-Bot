"""
Configuration module for GM SHOP Bot.
Loads settings from environment variables using Pydantic Settings.
"""

from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Bot configuration settings loaded from environment variables."""

    # Telegram Bot Configuration
    bot_token: str = Field(..., description="Telegram Bot API token")

    # Owner IDs (comma-separated in .env)
    owner_ids: List[int] = Field(..., description="List of bot owner user IDs")

    # Admin Log Channel
    admin_log_chat_id: int = Field(..., description="Chat ID for admin logs")

    # Main Chat ID (optional)
    main_chat_id: int | None = Field(None, description="Main group chat ID")

    # Database Configuration
    database_url: str = Field(..., description="PostgreSQL connection URL")
    postgres_password: str = Field(default="gmshop_password", description="PostgreSQL password")

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")

    # Timezone
    tz: str = Field(default="Europe/Moscow", description="Timezone for scheduled tasks")

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    # Features Toggle
    enable_marriages: bool = Field(default=True, description="Enable marriage system")
    enable_karma: bool = Field(default=True, description="Enable karma system")
    enable_weekly_top: bool = Field(default=True, description="Enable weekly top")
    enable_giveaways: bool = Field(default=True, description="Enable giveaways")

    # Development Mode
    dev_mode: bool = Field(default=False, description="Development mode flag")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @field_validator("owner_ids", mode="before")
    @classmethod
    def parse_owner_ids(cls, v):
        """Parse comma-separated owner IDs from string to list of integers."""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            return v
        return v

    @field_validator("main_chat_id", mode="before")
    @classmethod
    def parse_main_chat_id(cls, v):
        """Parse main chat ID, handle empty string."""
        if v == "" or v is None:
            return None
        return int(v)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level is one of the standard levels."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper


# Global settings instance
settings = Settings()


# Default bot settings for new chats (stored in chats.settings JSONB)
DEFAULT_CHAT_SETTINGS = {
    # Welcome settings
    "welcome": {
        "enabled": True,
        "auto_delete_minutes": 5,
        "pin_rules": False,
        "custom_text": None  # None means use default template
    },

    # Antiflood settings
    "antiflood": {
        "enabled": True,
        "messages_count": 6,
        "window_minutes": 3,
        "mute_duration_minutes": 50,
        "delete_messages": True
    },

    # Content filters
    "filters": {
        "enabled": True,
        "default_action": "mute_forever",  # or "mute_duration", "ban"
        "mute_duration_minutes": 10080,  # 7 days
        "check_links": True,
        "whitelist_domains": ["t.me", "telegram.me"]
    },

    # Karma settings
    "karma": {
        "enabled": True,
        "cooldown_hours": 12,
        "daily_negative_limit": -3,
        "weekly_bonus_weight": 2
    },

    # Warns/escalation
    "warns": {
        "enabled": True,
        "warn_threshold": 3,
        "first_action": "mute",
        "first_duration_hours": 24,
        "second_action": "ban",
        "second_duration_days": 7
    },

    # Weekly top
    "weekly_top": {
        "enabled": True,
        "day_of_week": 0,  # Monday
        "hour": 12,
        "top_count": 3,
        "formula": {
            "messages_weight": 1,
            "karma_weight": 2,
            "replies_weight": 0.5,
            "reactions_weight": 0.3
        },
        "exclude_if_muted_hours": 24,
        "prizes": [
            "🥇 Донат на 500 руб",
            "🥈 Донат на 300 руб",
            "🥉 Донат на 200 руб"
        ]
    },

    # Marriages
    "marriages": {
        "enabled": True,
        "proposal_cooldown_days": 3,
        "proposal_expiry_hours": 24,
        "anniversary_notifications": True,
        "karma_bonus_enabled": False
    },

    # Moderation
    "moderation": {
        "allow_exclamation_prefix": True,  # !бан, !мут etc.
        "delete_command_messages": True,
        "notify_in_chat": True,
        "notify_in_log": True
    }
}
