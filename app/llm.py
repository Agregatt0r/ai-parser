"""
Клієнт для звернення до Google Gemini API.
"""
import logging
from google import genai
from google.genai import types
from fastapi import HTTPException

from app.config import settings
from app.prompts import SYSTEM_PROMPT

logger = logging.getLogger("ai_parser.llm")

# Ініціалізація Gemini клієнта
ai_client = genai.Client(api_key=settings.gemini_api_key)


async def run_llm(user_prompt: str) -> str:
    """Викликає Google Gemini API і повертає JSON-текст."""
    try:
        # Асинхронний виклик Gemini
        response = await ai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",  # Гарантує відповідь у суворому JSON
                temperature=0.1,
            ),
        )

        if not response.text:
            raise HTTPException(status_code=502, detail="Gemini повернула порожню відповідь")

        return response.text

    except Exception as exc:
        logger.error("Помилка під час запиту до Gemini API: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Помилка при виконанні запиту до Gemini API: {str(exc)}",
        ) from exc


async def check_gemini_health() -> dict:
    """Перевірка доступності Gemini API."""
    try:
        # Простий легкий тест
        response = await ai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents="ping",
        )
        return {"reachable": True, "status": "ok"}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}