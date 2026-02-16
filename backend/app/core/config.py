"""
Application Configuration
Uses pydantic-settings for environment variable management
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=False)
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:password@localhost:5432/zoomcar"
    )
    DB_POOL_SIZE: int = Field(default=10)
    DB_MAX_OVERFLOW: int = Field(default=5)
    
    # Redis
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    
    # JWT
    SECRET_KEY: str = Field(default="your-super-secret-key-change-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRY_DAYS: int = Field(default=30)
    
    # Razorpay
    RAZORPAY_KEY_ID: str = Field(default="")
    RAZORPAY_KEY_SECRET: str = Field(default="")
    RAZORPAY_WEBHOOK_SECRET: str = Field(default="")
    
    # AWS
    AWS_REGION: str = Field(default="ap-south-1")
    AWS_ACCESS_KEY_ID: str = Field(default="")
    AWS_SECRET_ACCESS_KEY: str = Field(default="")
    
    # Twilio (WhatsApp OTP and Confirmations)
    TWILIO_ACCOUNT_SID: str = Field(default="")
    TWILIO_AUTH_TOKEN: str = Field(default="")
    TWILIO_WHATSAPP_FROM: str = Field(default="whatsapp:+14155238886")
    TWILIO_CONTENT_SID: str = Field(default="HX229f5a04fd0510ce1b071852155d3e75")  # OTP template
    TWILIO_BOOKING_CONFIRMATION_TEMPLATE_SID: str = Field(default="")  # Booking confirmation template (optional)
    
    # Sentry
    SENTRY_DSN: str = Field(default="")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000"])
    
    # Business Rules
    MIN_RENTAL_HOURS: int = Field(default=1)
    BOOKING_EXPIRY_MINUTES: int = Field(default=8)
    BUFFER_HOURS: float = Field(default=1.0)
    SEARCH_RADIUS_METERS: int = Field(default=15000)
    
    # Rate Limiting
    OTP_RATE_LIMIT_HOUR: int = Field(default=3)
    OTP_EXPIRY_SECONDS: int = Field(default=300)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()
