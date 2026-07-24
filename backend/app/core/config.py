"""Settings — every value from env, never hardcoded (§11, §15).

Provider keys live here and nowhere else: they are read server-side, used behind
one proxy endpoint, and never returned by a route, logged, or shipped to the
client. `masked()` is what diagnostics are allowed to print.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — all values from env vars, never hardcoded."""

    environment: str = "dev"
    database_url: str = "postgresql+asyncpg://localhost:5432/cheatsheet"

    # --- providers (§11: server-side only) ---
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    youcontrol_api_key: str = ""
    youcontrol_base_url: str = "https://api.youscore.com.ua"
    prozorro_base_url: str = "https://public.api.openprocurement.org/api/2.5"

    # --- object storage (§15) ---
    r2_bucket_name: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""

    model_config = {"env_prefix": "CS_", "env_file": ".env"}

    @property
    def youcontrol_configured(self) -> bool:
        """Role 1's key handoff gates the YouControl connector (TASKS.md wk 1)."""
        return bool(self.youcontrol_api_key)

    @property
    def openrouter_configured(self) -> bool:
        return bool(self.openrouter_api_key)

    def masked(self) -> dict[str, object]:
        """Config summary safe to log or serve — key *presence*, never key value."""
        return {
            "environment": self.environment,
            "database": self.database_url.rsplit("@", 1)[-1],
            "openrouter_configured": self.openrouter_configured,
            "youcontrol_configured": self.youcontrol_configured,
            "r2_configured": bool(self.r2_bucket_name),
        }


settings = Settings()
