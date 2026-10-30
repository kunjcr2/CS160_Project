"""Settings loaded from .env. Never commit .env; commit .env.example."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # postgresql+psycopg://USER:PASSWORD@localhost:5432/voice_assistant
    database_url: str

    # Frontend origins allowed to call the API (Vite dev server).
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    # Speech adapters can run locally in development; conversation intent extraction always uses OpenAI.
    fake_ai: bool = True
    openai_api_key: str | None = None
    openai_model: str = "gpt-6-luna"
    openai_reasoning_effort: str = "none"
    openai_max_output_tokens: int = 120
    openai_stt_model: str = "gpt-4o-mini-transcribe"
    openai_tts_model: str = "gpt-4o-mini-tts"
    openai_tts_voice: str = "alloy"

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
