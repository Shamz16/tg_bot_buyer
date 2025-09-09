    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./tg_gifts.db"
    )

"""Configuration management using Pydantic"""
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, validator

class Settings(BaseSettings):
    """Application settings with validation"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )
    
    # Telegram
    bot_token: str = Field(..., description="Telegram Bot API token")
    api_id: int = Field(..., description="Telegram API ID")
    api_hash: str = Field(..., description="Telegram API hash")
    phone_number: str = Field(..., description="Phone number for MTProto")
    session_name: str = Field(default="gift_buyer_session")
    
    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./tg_gifts.db"
    )
    
    # Security
    secret_key: str = Field(..., min_length=32)
    operator_user_ids: List[int] = Field(default_factory=list)
    
    # Limits & Safety
    max_spend_per_day: int = Field(default=10000, ge=0)
    max_purchases_per_hour: int = Field(default=10, ge=1)
    default_polling_interval: int = Field(default=5, ge=1)
    fast_polling_interval: int = Field(default=1, ge=1)
    purchase_cooldown_ms: int = Field(default=800, ge=100)
    
    # Environment
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    timezone: str = Field(default="UTC")
    
    # Paths
    session_file_path: str = Field(default="./sessions/")
    log_file_path: str = Field(default="./logs/")
    
    @validator("operator_user_ids", pre=True)
    def parse_operator_ids(cls, v):
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v
    
    @property
    def is_production(self) -> bool:
        return self.environment == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment == "development"

# Global settings instance
settings = Settings()
