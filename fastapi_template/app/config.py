"""Configuration management for Embassy Aviation Mailbot."""

import os
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with validation."""
    
    # Application
    APP_NAME: str = "Embassy Aviation Mailbot"
    VERSION: str = "0.1.0"
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    ENVIRONMENT: str = Field(default="development", description="Environment")
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    HOST: str = Field(default="0.0.0.0", description="Host to bind")
    PORT: int = Field(default=8000, description="Port to bind")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./embassy_mailbot.db",
        description="Database connection URL"
    )
    
    # Redis (for Celery and caching)
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # Microsoft Graph API
    GRAPH_TENANT_ID: str = Field(default="", description="Azure AD Tenant ID")
    GRAPH_CLIENT_ID: str = Field(default="", description="Graph App Client ID")
    GRAPH_CLIENT_SECRET: str = Field(default="", description="Graph App Client Secret")
    GRAPH_USER_MAILBOXES: str = Field(
        default="ops@embassy-aviation.com,maintenance@embassy-aviation.com",
        description="Comma-separated list of mailboxes to monitor"
    )
    
    # SMTP Configuration
    SMTP_HOST: str = Field(default="", description="SMTP server host")
    SMTP_PORT: int = Field(default=587, description="SMTP server port")
    SMTP_USER: str = Field(default="", description="SMTP username")
    SMTP_PASS: str = Field(default="", description="SMTP password")
    SMTP_FROM: str = Field(
        default="noreply@embassy-aviation.com",
        description="From email address"
    )
    SMTP_FROM_NAME: str = Field(
        default="Embassy Aviation",
        description="From name for emails"
    )
    
    # Twilio SMS
    TWILIO_ACCOUNT_SID: str = Field(default="", description="Twilio Account SID")
    TWILIO_AUTH_TOKEN: str = Field(default="", description="Twilio Auth Token")
    TWILIO_FROM_NUMBER: str = Field(default="", description="Twilio phone number")
    
    # Escalation Configuration
    ESCALATION_INTERNAL_EMAILS: str = Field(
        default="ops-bridge@embassy-aviation.com",
        description="Comma-separated internal emails for escalation"
    )
    ESCALATION_INTERNAL_NUMBERS: str = Field(
        default="+1234567890",
        description="Comma-separated phone numbers for SMS escalation"
    )
    ESCALATION_WINDOW_MINUTES: str = Field(
        default="15,60,240",
        description="Escalation intervals in minutes (AOG, Service, General)"
    )
    ESCALATION_MAX_STEPS: int = Field(
        default=3,
        description="Maximum escalation steps before stopping"
    )
    
    # Processing Configuration
    POLLING_INTERVAL_SECONDS: int = Field(
        default=300,
        description="How often to poll mailboxes (seconds)"
    )
    MAX_EMAILS_PER_BATCH: int = Field(
        default=50,
        description="Maximum emails to process in one batch"
    )
    EMAIL_RETENTION_DAYS: int = Field(
        default=90,
        description="Days to retain processed emails in database"
    )
    
    # Security
    SECRET_KEY: str = Field(
        default="dev-secret-key-change-in-production",
        description="Secret key for JWT tokens"
    )
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30,
        description="JWT token expiration minutes"
    )
    
    # Monitoring & Observability
    SENTRY_DSN: Optional[str] = Field(
        default=None,
        description="Sentry DSN for error tracking"
    )
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    PROMETHEUS_METRICS_PORT: int = Field(
        default=8001,
        description="Port for Prometheus metrics"
    )
    
    # Features
    ENABLE_ML_CLASSIFICATION: bool = Field(
        default=True,
        description="Enable ML-based email classification"
    )
    ENABLE_ESCALATION: bool = Field(
        default=True,
        description="Enable automatic escalation"
    )
    ENABLE_SMS_ALERTS: bool = Field(
        default=True,
        description="Enable SMS alerts via Twilio"
    )
    
    @validator("GRAPH_USER_MAILBOXES")
    def validate_mailboxes(cls, v: str) -> List[str]:
        """Convert comma-separated mailboxes to list."""
        if not v:
            return []
        return [email.strip() for email in v.split(",") if email.strip()]
    
    @validator("ESCALATION_INTERNAL_EMAILS")
    def validate_internal_emails(cls, v: str) -> List[str]:
        """Convert comma-separated emails to list."""
        if not v:
            return []
        return [email.strip() for email in v.split(",") if email.strip()]
    
    @validator("ESCALATION_INTERNAL_NUMBERS")
    def validate_internal_numbers(cls, v: str) -> List[str]:
        """Convert comma-separated phone numbers to list."""
        if not v:
            return []
        return [num.strip() for num in v.split(",") if num.strip()]
    
    @validator("ESCALATION_WINDOW_MINUTES")
    def validate_escalation_windows(cls, v: str) -> List[int]:
        """Convert comma-separated intervals to list of integers."""
        if not v:
            return [15, 60, 240]  # Default intervals
        try:
            return [int(interval.strip()) for interval in v.split(",")]
        except ValueError:
            return [15, 60, 240]  # Fallback to defaults
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Global settings instance
settings = Settings()