"""Build the user prompt that forces JSON output from the model."""
from app.config import settings

SYSTEM_PROMPT = """You are a precise data extraction assistant.
You receive cleaned Markdown content from a webpage and a TASK describing what to extract.

Rules:
- Base your answer ONLY on the provided MARKDOWN. Never invent facts.
- If information is missing, use null or empty values.
- Output MUST be a valid JSON object or array answering the TASK. No explanations or conversational fillers.
"""


def truncate_markdown(markdown: str, max_chars: int) -> tuple[str, bool]:
    if len(markdown) <= max_chars:
        return markdown, False
    return markdown[:max_chars], True


def build_user_prompt(task: str, markdown: str) -> tuple[str, bool]:
    truncated_markdown, was_truncated = truncate_markdown(markdown, settings.max_markdown_chars)

    truncation_note = (
        "\n\n[NOTE: MARKDOWN content was truncated due to length limits.]"
        if was_truncated
        else ""
    )

    prompt = (
        f"TASK: {task.strip()}\n"
        f"{truncation_note}\n\n"
        "--- MARKDOWN CONTENT START ---\n"
        f"{truncated_markdown}\n"
        "--- MARKDOWN CONTENT END ---\n"
    )
    return prompt, was_truncated
