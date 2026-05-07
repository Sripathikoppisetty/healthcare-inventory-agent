"""config/settings.py — centralised configuration via environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Groq
    groq_api_key: str = Field(..., env="GROQ_API_KEY")
    model_name: str = Field("llama-3.3-70b-versatile", env="MODEL_NAME")
    max_iterations: int = Field(12, env="MAX_ITERATIONS")

    # Database
    database_url: str = Field("sqlite:///./healthcare_inventory.db", env="DATABASE_URL")

    # Redis
    redis_url: str | None = Field(None, env="REDIS_URL")

    # LangSmith
    langchain_tracing_v2: bool = Field(False, env="LANGCHAIN_TRACING_V2")
    langchain_api_key: str | None = Field(None, env="LANGCHAIN_API_KEY")
    langchain_project: str = Field("healthcare-inventory-agent", env="LANGCHAIN_PROJECT")

    # API
    api_secret_key: str = Field("change-me", env="API_SECRET_KEY")
    api_host: str = Field("0.0.0.0", env="API_HOST")
    api_port: int = Field(8000, env="API_PORT")

    # Alerts
    alert_email: str | None = Field(None, env="ALERT_EMAIL")
    smtp_host: str | None = Field(None, env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_user: str | None = Field(None, env="SMTP_USER")
    smtp_pass: str | None = Field(None, env="SMTP_PASS")

    # Business rules
    low_stock_threshold_days: int = Field(3, env="LOW_STOCK_THRESHOLD_DAYS")
    reorder_lead_time_buffer: float = Field(1.2, env="REORDER_LEAD_TIME_BUFFER")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
