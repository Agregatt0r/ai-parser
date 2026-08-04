"""
Конфігурація застосунку.

Усі параметри читаються зі змінних середовища (файл .env поруч із docker-compose.yml),
щоб жодних секретів чи серверних адрес не було захардкодено в коді, який лежить
у git-репозиторії.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Безпека ---
    api_key: str  # обов'язковий секрет для доступу до /api/parse (заголовок X-API-Key)

    # --- Ollama / LLM ---
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b"  # Оптимальний баланс швидкості та якості для CPU
    ollama_num_ctx: int = 4096        # Зменшено з 8192 для прискорення префілу на CPU
    ollama_request_timeout: int = 120 # Зменшено таймаут, оскільки 3b модель працює швидко
    ollama_temperature: float = 0.1   # Низька температура для стабільного JSON

    # --- Краулінг (crawl4ai / Playwright) ---
    crawl_timeout_ms: int = 30_000

    # --- Обмеження вхідних даних ---
    max_task_length: int = 4000
    max_url_length: int = 2000
    # Символьний бюджет під markdown-контент (зменшено для розвантаження CPU)
    max_markdown_chars: int = 15_000

    # --- CORS: звідки дозволено запити фронтенду (через кому) ---
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    # --- Rate limiting ---
    rate_limit: str = "10/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()