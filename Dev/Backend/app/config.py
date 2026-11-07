"""Settings loaded from .env. Never commit .env; commit .env.example."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# The placeholder shipped in .env.example. A real .env must replace it.
_DEFAULT_JWT_SECRET = "change-me-in-dotenv"
_MIN_JWT_SECRET_BYTES = 32


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
    jwt_secret: str = _DEFAULT_JWT_SECRET
    access_token_minutes: int = 15

    # How long a signed-in device stays signed in without logging in again.
    refresh_token_days: int = 90

    # Cookie "Secure" flag: cookie sent only over https. True in production (plan §5.1);
    # set COOKIE_SECURE=false in .env for local http development.
    cookie_secure: bool = True

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_must_be_set_and_long_enough(cls, value: str) -> str:
        """Refuse to start with a secret anyone could guess or find on GitHub.

        A short/default secret lets anyone mint an access token for any user id.
        """
        if value == _DEFAULT_JWT_SECRET or len(value.encode()) < _MIN_JWT_SECRET_BYTES:
            raise ValueError(
                "JWT_SECRET must be set in .env to a random string of at least "
                f"{_MIN_JWT_SECRET_BYTES} bytes, e.g.: "
                'python -c "import secrets; print(secrets.token_hex(32))"'
            )
        return value

    # How long a pairing code works after it's created.
    pairing_code_minutes: int = 15

    # Mock doctor's office. 0 = fast and never fails (good for tests).
    # Turn on in .env to test slow or broken provider paths.
    mock_provider_latency_ms: int = 0
    mock_provider_failure_rate: float = 0.0  # 0.0 to 1.0 (0.2 = 20% of calls fail)


settings = Settings()
