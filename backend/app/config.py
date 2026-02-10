"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "Bayesline"
    debug: bool = False
    port: int = 8000  # Many platforms (Render, Railway, Cloud Run) set PORT

    # Database
    database_url: str = "sqlite+aiosqlite:///./bayesline.db"
    redis_url: str = "redis://localhost:6379/0"

    # Prediction market API keys
    polymarket_api_url: str = "https://clob.polymarket.com"
    manifold_api_url: str = "https://api.manifold.markets/v0"
    metaculus_api_url: str = "https://www.metaculus.com/api2"
    kalshi_api_url: str = "https://trading-api.kalshi.com/trade-api/v2"
    kalshi_api_key: Optional[str] = None

    # News APIs
    newsapi_key: Optional[str] = None
    gdelt_api_url: str = "https://api.gdeltproject.org/api/v2"

    # LLM
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    llm_provider: str = "anthropic"  # "openai" or "anthropic"
    llm_model: str = "claude-sonnet-4-5-20250929"

    # Scoring weights
    market_signal_weight: float = 0.45
    coverage_gap_weight: float = 0.20
    consequence_weight: float = 0.20
    time_sensitivity_weight: float = 0.10
    manipulation_risk_penalty: float = 0.15
    hype_gap_penalty: float = 0.10

    # Market activity composite weights
    volume_weight: float = 0.35
    open_interest_weight: float = 0.25
    depth_weight: float = 0.15
    price_change_weight: float = 0.15
    jump_weight: float = 0.10

    # Quality composite weights
    quality_weight: float = 0.6
    robustness_weight: float = 0.4

    # Ingestion intervals (seconds)
    market_poll_interval: int = 300
    news_poll_interval: int = 600

    # Feed
    feed_page_size: int = 20
    min_consequence_floor: float = 0.3

    model_config = {"env_prefix": "BAYESLINE_", "env_file": ".env"}


settings = Settings()
