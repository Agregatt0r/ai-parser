"""
AI-парсер: FastAPI застосунок.
"""
import logging
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from app.config import settings
from app.crawler import fetch_clean_markdown
from app.formatters import format_llm_output
from app.llm import check_ollama_health, run_llm
from app.prompts import build_user_prompt
from app.security import validate_public_url, verify_api_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("ai_parser.main")

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="AI Parser", version="2.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["POST", "GET"],
    allow_headers=["Content-Type", "X-API-Key"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Необроблена помилка на %s", request.url.path)
    return JSONResponse(status_code=500, content={"success": False, "error": "Внутрішня помилка сервера"})


class ParseRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=settings.max_url_length)
    task: str = Field(..., min_length=1, max_length=settings.max_task_length)


class ParseMeta(BaseModel):
    url: str
    model: str
    markdown_chars: int
    truncated: bool
    processing_time_seconds: float


class ParseResponse(BaseModel):
    success: bool
    output_format: str = "json"
    content: str
    filename: str
    mime_type: str
    warning: str | None = None
    meta: ParseMeta


@app.get("/api/health", dependencies=[Depends(verify_api_key)])
async def health():
    ollama_status = await check_ollama_health()
    return {"status": "ok", "ollama": ollama_status}


@app.post("/api/parse", response_model=ParseResponse, dependencies=[Depends(verify_api_key)])
@limiter.limit(settings.rate_limit)
async def parse(request: Request, body: ParseRequest):
    safe_url = validate_public_url(body.url)

    started = time.monotonic()

    markdown = await fetch_clean_markdown(safe_url)
    user_prompt, truncated = build_user_prompt(body.task, markdown)
    raw_llm_output = await run_llm(user_prompt)
    result = format_llm_output(raw_llm_output)

    elapsed = time.monotonic() - started
    logger.info("parse OK url=%s format=json elapsed=%.1fs", safe_url, elapsed)

    return ParseResponse(
        success=True,
        output_format="json",
        content=result.content,
        filename=result.filename,
        mime_type=result.mime_type,
        warning=result.warning,
        meta=ParseMeta(
            url=safe_url,
            model=settings.ollama_model,
            markdown_chars=len(markdown),
            truncated=truncated,
            processing_time_seconds=round(elapsed, 2),
        ),
    )