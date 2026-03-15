from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PM Multi-Strategy Backend"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "dT3Hu89envHg3Nc"
    postgres_db: str = "postgres"
    postgres_schema: str = "polypdt"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0
    external_stream_enabled: bool = False
    polymarket_ws_enabled: bool = True
    polymarket_ws_url: str = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"
    polymarket_ws_custom_feature_enabled: bool = True
    polymarket_ws_max_assets: int = 200
    goalserve_ws_enabled: bool = False
    goalserve_token_url: str = ""
    goalserve_token_method: str = "auto"
    goalserve_token_ttl_minutes: int = 60
    goalserve_token_refresh_ahead_seconds: int = 300
    goalserve_ws_url: str = ""
    goalserve_api_key: str = ""
    goalserve_username: str = ""
    goalserve_password: str = ""
    goalserve_subscribe_payload: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_dsn(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


settings = Settings()
