"""
Пост-обробка відповіді LLM: прибираємо випадкові ```code fences```, які модель
іноді додає всупереч інструкції, валідуємо синтаксис для json/csv, і визначаємо
ім'я файлу та MIME-тип для віддачі на фронтенд.
"""
import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

_CODE_FENCE_RE = re.compile(r"^```(?:[a-zA-Z0-9_-]*)\n(.*)\n```$", re.DOTALL)

_EXTENSIONS = {"json": "json", "csv": "csv", "txt": "txt", "summary": "txt"}
_MIME_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "txt": "text/plain",
    "summary": "text/plain",
}


@dataclass
class FormattedResult:
    content: str
    filename: str
    mime_type: str
    is_valid: bool
    warning: str | None = None


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = _CODE_FENCE_RE.match(text)
    if match:
        return match.group(1).strip()
    return text


def _make_filename(output_format: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    ext = _EXTENSIONS[output_format]
    return f"parsed_{ts}.{ext}"


def format_llm_output(raw: str, output_format: str) -> FormattedResult:
    cleaned = _strip_code_fences(raw)
    filename = _make_filename(output_format)
    mime_type = _MIME_TYPES[output_format]

    if output_format == "json":
        try:
            parsed = json.loads(cleaned)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            return FormattedResult(pretty, filename, mime_type, is_valid=True)
        except json.JSONDecodeError as exc:
            return FormattedResult(
                cleaned,
                filename,
                mime_type,
                is_valid=False,
                warning=f"Модель повернула невалідний JSON ({exc}). Показано сирий текст відповіді.",
            )

    if output_format == "csv":
        try:
            rows = list(csv.reader(io.StringIO(cleaned)))
            if not rows or not any(rows):
                raise csv.Error("порожній результат")
            return FormattedResult(cleaned, filename, mime_type, is_valid=True)
        except csv.Error as exc:
            return FormattedResult(
                cleaned,
                filename,
                mime_type,
                is_valid=False,
                warning=f"Модель повернула не зовсім коректний CSV ({exc}). Перевірте вивід вручну.",
            )

    # txt / summary - валідація не потрібна, просто повертаємо очищений текст
    return FormattedResult(cleaned, filename, mime_type, is_valid=True)