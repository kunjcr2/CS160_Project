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


settings = Settings()
