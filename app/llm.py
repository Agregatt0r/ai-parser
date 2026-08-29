"""Google Gemini client used for structured extraction."""
import logging

from fastapi import HTTPException
from google import genai
from google.genai import types

from app.config import settings
from app.prompts import SYSTEM_PROMPT

logger = logging.getLogger("ai_parser.llm")

ai_client = genai.Client(api_key=settings.gemini_api_key)


async def run_llm(user_prompt: str) -> str:
    """Call Gemini and return JSON text."""
    try:
        response = await ai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )

        if not response.text:
            raise HTTPException(status_code=502, detail="Gemini returned an empty response")

        return response.text

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Gemini API request failed: %s", exc)
        raise HTTPException(
            status_code=502,
            detail=f"Gemini API request failed: {exc}",
        ) from exc


async def check_gemini_health() -> dict:
    """Lightweight reachability check for the Gemini API."""
    try:
        await ai_client.aio.models.generate_content(
            model=settings.gemini_model,
            contents="ping",
        )
        return {"reachable": True, "status": "ok"}
    except Exception as exc:
        return {"reachable": False, "error": str(exc)}
