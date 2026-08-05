"""
Конфігурація застосунку.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Безпека ---
    api_key: str

    # --- Google Gemini API ---
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # --- Краулінг (crawl4ai / Playwright) ---
    crawl_timeout_ms: int = 30_000

    # --- Обмеження вхідних даних ---
    max_task_length: int = 4000
    max_url_length: int = 2000
    # Збільшено бюджет до 100 000 символів завдяки великому вікну Gemini
    max_markdown_chars: int = 100_000

    # --- CORS ---
    cors_origins: str = "*"

    # --- Rate limiting ---
    rate_limit: str = "20/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()