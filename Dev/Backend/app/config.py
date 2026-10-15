"""Settings loaded from .env. Never commit .env; commit .env.example."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+psycopg://USER:PASSWORD@localhost:5432/voice_assistant
    database_url: str

    # Frontend origins allowed to call the API (Vite dev server).
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # AI: FAKE_AI=true returns canned responses, so tests and UI work need no key (plan §6.10).
    fake_ai: bool = True
    openai_api_key: str | None = None

    # Auth (used once auth is implemented).
    jwt_secret: str = "change-me-in-dotenv"
    access_token_minutes: int = 15

    # How long a signed-in device stays signed in without logging in again.
    refresh_token_days: int = 90

    # Cookie "Secure" flag: cookie sent only over https. False for local http; True in production.
    cookie_secure: bool = False

    # How long a pairing code works after it's created.
    pairing_code_minutes: int = 15

    # Mock doctor's office. 0 = fast and never fails (good for tests).
    # Turn on in .env to test slow or broken provider paths.
    mock_provider_latency_ms: int = 0
    mock_provider_failure_rate: float = 0.0  # 0.0 to 1.0 (0.2 = 20% of calls fail)


settings = Settings()
