"""
Валідація та форматування результату у валідний JSON.
"""
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\n(.*)\n```$", re.DOTALL)


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


def format_llm_output(raw: str) -> FormattedResult:
    cleaned = _strip_code_fences(raw)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"parsed_{ts}.json"
    mime_type = "application/json"

    try:
        parsed = json.loads(cleaned)
        pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
        return FormattedResult(pretty, filename, mime_type, is_valid=True)
    except json.JSONDecodeError as exc:
        return FormattedResult(
            content=cleaned,
            filename=filename,
            mime_type=mime_type,
            is_valid=False,
            warning=f"Модель повернула невалідний JSON ({exc}). Показано сирий текст.",
        )