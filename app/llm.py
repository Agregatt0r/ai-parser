"""
Клієнт для звернення до Ollama.

Ollama віддає власний простий REST API (/api/chat). Тут ми звертаємось до нього
напряму через httpx, без офіційної ollama-python бібліотеки - на один ендпоінт
вона не потрібна, а так менше залежностей у Docker-образі.

Для output_format == "json" використовуємо вбудовану в Ollama можливість
structured outputs (параметр "format": "json"), яка форсує синтаксично
валідний JSON constrained-декодуванням на рівні runtime моделі - це суттєво
надійніше за прохання "поверни JSON" у самому тексті промпту.
"""
import logging

import httpx
from fastapi import HTTPException

from app.config import settings
from app.prompts import SYSTEM_PROMPT

logger = logging.getLogger("ai_parser.llm")


async def run_llm(user_prompt: str) -> str:
    """Викликає Ollama /api/chat і гарантовано повертає JSON-текст."""
    payload: dict = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "format": "json",       # Гарантує відповідь у форматі JSON на рівні Ollama runtime
        "keep_alive": "1h",     # Тримати модель в RAM, щоб не завантажувати повторно
        "options": {
            "temperature": settings.ollama_temperature,
            "num_ctx": settings.ollama_num_ctx,
            "num_thread": 4,    # Жорстко прив'язуємо під 4 ядра CPU
        },
    }

    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"

    try:
        async with httpx.AsyncClient(timeout=settings.ollama_request_timeout) as client:
            response = await client.post(url, json=payload)
    except httpx.ConnectError as exc:
        logger.error("Не вдалося з'єднатись з Ollama на %s: %s", url, exc)
        raise HTTPException(
            status_code=503,
            detail="LLM-сервіс (Ollama) недоступний. Перевірте, чи запущений контейнер ollama.",
        ) from exc
    except httpx.TimeoutException as exc:
        logger.error("Тайм-аут запиту до Ollama: %s", exc)
        raise HTTPException(
            status_code=504,
            detail="LLM не встигла відповісти за відведений час.",
        ) from exc

    if response.status_code != 200:
        logger.error("Ollama повернула помилку %s: %s", response.status_code, response.text[:500])
        raise HTTPException(
            status_code=502,
            detail=f"Ollama повернула помилку {response.status_code}: {response.text[:300]}",
        )

    data = response.json()
    content = data.get("message", {}).get("content", "")
    if not content:
        raise HTTPException(status_code=502, detail="Ollama повернула порожню відповідь")

    return content


async def check_ollama_health() -> dict:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(url)
        response.raise_for_status()
        models = [m.get("name") for m in response.json().get("models", [])]
        model_ready = any(
            m == settings.ollama_model or (m and m.split(":")[0] == settings.ollama_model.split(":")[0])
            for m in models
        )
        return {"reachable": True, "model_ready": model_ready, "available_models": models}
    except Exception as exc:
        return {"reachable": False, "model_ready": False, "error": str(exc)}