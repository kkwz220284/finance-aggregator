from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: Literal["local", "cloud"] = "local"

    # Database
    database_url: str

    # TrueLayer
    truelayer_client_id: str
    truelayer_client_secret: str
    truelayer_redirect_uri: str
    truelayer_webhook_secret: str
    truelayer_sandbox: bool = True

    # Derived from sandbox flag
    @property
    def truelayer_auth_url(self) -> str:
        return (
            "https://auth.truelayer-sandbox.com"
            if self.truelayer_sandbox
            else "https://auth.truelayer.com"
        )

    @property
    def truelayer_api_url(self) -> str:
        return (
            "https://api.truelayer-sandbox.com"
            if self.truelayer_sandbox
            else "https://api.truelayer.com"
        )

    # Security
    fernet_key: str
    api_key: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
