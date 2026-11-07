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

    # AI: FAKE_AI=true returns canned responses, so tests and UI work need no key (plan §6.10).
    fake_ai: bool = True
    openai_api_key: str | None = None

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


settings = Settings()
