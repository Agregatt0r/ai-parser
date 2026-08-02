"""
Конфігурація застосунку.

Усі параметри читаються зі змінних середовища (файл .env поруч із docker-compose.yml),
щоб жодних секретів чи серверних адрес не було захардкоджено в коді, який лежить
у git-репозиторії.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Безпека ---
    api_key: str  # обов'язковий секрет для доступу до /api/parse (заголовок X-API-Key)

    # --- Ollama / LLM ---
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:7b-instruct"
    ollama_num_ctx: int = 8192
    ollama_request_timeout: int = 600  # сек. CPU-інференс на 4 ядрах ARM буває повільним
    ollama_temperature: float = 0.2  # низька температура -> стабільніше дотримання формату

    # --- Краулінг (crawl4ai / Playwright) ---
    crawl_timeout_ms: int = 30_000

    # --- Обмеження вхідних даних (проста анти-зловживання гігієна) ---
    max_task_length: int = 4000
    max_url_length: int = 2000
    # Символьний бюджет під markdown-контент. Це грубий (не токенний) ліміт:
    # ~4 символи латиницею на токен, для кирилиці ближче до ~2-3, тож лишаємо запас.
    max_markdown_chars: int = 60_000

    # --- CORS: звідки дозволено запити фронтенду (через кому) ---
    cors_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    # --- Rate limiting (захист від випадкового/навмисного заспамлення LLM) ---
    rate_limit: str = "10/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()