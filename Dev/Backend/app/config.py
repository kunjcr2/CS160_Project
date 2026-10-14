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
    # TEMPORARY, local development only, until auth (S2-03): trust an X-User-Id header.
    dev_user_header: bool = False

    # Confirmation (plan §5.3): how long a proposed action waits for a yes.
    pending_action_ttl_minutes: int = 5

    # Reminder worker (plan §6.3). RUN_REMINDER_WORKER=true runs it inside the API process
    # (one terminal); otherwise run `python -m app.workers.reminders` separately.
    reminder_poll_seconds: float = 30
    run_reminder_worker: bool = False


settings = Settings()
