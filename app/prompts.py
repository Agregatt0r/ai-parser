"""
Побудова промпту, який іде в LLM.

Фінальний промпт = SYSTEM_PROMPT (дефолтна інструкція "як поводитись") +
завдання користувача (що саме витягнути) + інструкція формату виводу +
очищений markdown сторінки.
"""
from app.config import settings

OutputFormat = str  # "json" | "csv" | "txt" | "summary"

SYSTEM_PROMPT = """You are a precise data extraction and formatting assistant.

You receive:
1. MARKDOWN - cleaned Markdown content extracted from a single webpage.
2. TASK - a description, written by the user, of exactly what to extract or do with that content.
3. OUTPUT FORMAT - the exact format the final answer must be returned in.

Rules you must always follow:
- Base your answer ONLY on the provided MARKDOWN. Never invent facts that are not present in it.
- If the requested information is not present in the content, say so explicitly
  (e.g. null / empty value / "not found in source") instead of guessing or hallucinating.
- Follow the TASK precisely - it defines what to extract, filter, or summarize, and how.
- Output ONLY the final result in the requested OUTPUT FORMAT. No explanations, no preamble,
  no apologies, no markdown code fences around it, unless the format itself requires them.
"""

FORMAT_INSTRUCTIONS: dict[str, str] = {
    "json": (
        "OUTPUT FORMAT: valid JSON only. Return a single JSON value (object or array) that "
        "best represents the requested data, using field names inferred from the TASK. "
        "Do not wrap it in markdown code fences. Do not add comments. "
        "The output must be syntactically valid JSON and nothing else."
    ),
    "csv": (
        "OUTPUT FORMAT: CSV only. The first line must be the header row with column names. "
        "Use a comma as the delimiter and double quotes to escape values containing commas, "
        "quotes, or newlines. Do not wrap it in markdown code fences and do not add any text "
        "before or after the CSV data."
    ),
    "txt": (
        "OUTPUT FORMAT: plain text. Structure it clearly with line breaks and simple '- ' lists "
        "where helpful, but do not use Markdown syntax (#, **, etc.) and do not wrap it in code fences."
    ),
    "summary": (
        "OUTPUT FORMAT: a concise, well-organized prose summary that directly addresses the TASK. "
        "Plain text, no Markdown syntax, no code fences."
    ),
}

# Формати, для яких є сенс просити Ollama форсувати синтаксично валідний JSON
# на рівні grammar-constrained decoding (параметр format="json" в Ollama API).
JSON_CONSTRAINED_FORMATS = {"json"}


def truncate_markdown(markdown: str, max_chars: int) -> tuple[str, bool]:
    """Грубе обрізання markdown під символьний бюджет контексту моделі.
    Повертає (текст, чи_було_обрізано)."""
    if len(markdown) <= max_chars:
        return markdown, False
    return markdown[:max_chars], True


def build_user_prompt(task: str, output_format: OutputFormat, markdown: str) -> tuple[str, bool]:
    """Формує фінальне user-повідомлення для LLM. Повертає (текст_промпту, чи_обрізано_контент)."""
    truncated_markdown, was_truncated = truncate_markdown(markdown, settings.max_markdown_chars)

    format_instruction = FORMAT_INSTRUCTIONS[output_format]
    truncation_note = (
        "\n\n[NOTE: the MARKDOWN content below was truncated because it exceeded the processing "
        "budget. Work only with what is provided below.]"
        if was_truncated
        else ""
    )

    prompt = (
        f"TASK: {task.strip()}\n\n"
        f"{format_instruction}{truncation_note}\n\n"
        "--- MARKDOWN CONTENT START ---\n"
        f"{truncated_markdown}\n"
        "--- MARKDOWN CONTENT END ---\n"
    )
    return prompt, was_truncated