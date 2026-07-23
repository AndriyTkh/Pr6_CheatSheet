from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — all values from env vars, never hardcoded."""

    database_url: str = "postgresql+asyncpg://localhost:5432/cheatsheet"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    youcontrol_api_key: str = ""
    r2_bucket_name: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""

    model_config = {"env_prefix": "CS_", "env_file": ".env"}


settings = Settings()
