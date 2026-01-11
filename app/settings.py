from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_NAME: str = "Jump AI Email Sorter"
    BASE_URL: str = "http://localhost:8000"
    SECRET_KEY: str = "change-me"  # used for signing cookies + encrypting tokens (see crypto.py)

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_PATH: str = "/auth/google/callback"
    GOOGLE_TEST_USER: str = "webshookeng@gmail.com"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Sync behavior
    SYNC_QUERY: str = "in:inbox newer_than:3d"  # can tighten/loosen for demo

settings = Settings()
