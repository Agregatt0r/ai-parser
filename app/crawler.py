"""
Обгортка над crawl4ai: завантажує сторінку headless Chromium (через Playwright),
прибирає script/style/навігацію/рекламу/cookie-банери і повертає чистий markdown
основного контенту сторінки.

Параметри BrowserConfig/CrawlerRunConfig нижче підібрані під ресурсно-обмежений
сервер (4 OCPU / 24GB, без GPU): вимикаємо завантаження зображень і зайвих
фонових фіч Chromium, щоб краулінг був швидшим і легшим по пам'яті.
"""
import logging

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger("ai_parser.crawler")

_BROWSER_CONFIG = BrowserConfig(
    browser_type="chromium",  # НЕ "chrome": офіційний Google Chrome не підтримується на Linux ARM64,
                               # тоді як bundled Chromium (default) на ARM64 Ubuntu підтримується.
    headless=True,
    verbose=False,
    text_mode=True,     # не завантажувати зображення/rich-контент - швидше й економніше по RAM
    light_mode=True,    # вимкнути частину фонових фіч Chromium заради продуктивності
    avoid_ads=True,     # блокувати відомі рекламні/трекінгові домени на рівні мережі браузера
)

_EXCLUDED_TAGS = ["script", "style", "nav", "footer", "form", "iframe", "noscript"]


def _build_run_config() -> CrawlerRunConfig:
    md_generator = DefaultMarkdownGenerator(
        content_filter=PruningContentFilter(
            threshold=0.48,
            threshold_type="fixed",
            min_word_threshold=0,
        ),
        options={"ignore_links": True, "body_width": 0},
    )
    return CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,       # завжди свіжий краулінг, без кешу попередніх запусків
        markdown_generator=md_generator,
        excluded_tags=_EXCLUDED_TAGS,
        word_count_threshold=1,            # не відкидати короткі сторінки/блоки
        page_timeout=settings.crawl_timeout_ms,
        remove_overlay_elements=True,      # прибрати модалки/попапи
        remove_consent_popups=True,        # прибрати cookie/GDPR-банери
        wait_until="domcontentloaded",
        verbose=False,
    )


async def fetch_clean_markdown(url: str) -> str:
    """Завантажує url і повертає очищений markdown (fit_markdown, з фолбеком на raw_markdown)."""
    run_config = _build_run_config()

    try:
        async with AsyncWebCrawler(config=_BROWSER_CONFIG) as crawler:
            result = await crawler.arun(url=url, config=run_config)
    except Exception as exc:  # crawl4ai/Playwright можуть кидати різні типи винятків
        logger.exception("Помилка краулінгу %s", url)
        raise HTTPException(status_code=502, detail=f"Не вдалося завантажити сторінку: {exc}") from exc

    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"Краулер не зміг обробити сторінку: {result.error_message or 'невідома помилка'}",
        )

    md = result.markdown
    fit = (getattr(md, "fit_markdown", "") or "").strip()
    raw = (getattr(md, "raw_markdown", "") or str(md)).strip()

    content = fit or raw
    if not content:
        raise HTTPException(status_code=502, detail="Сторінка не містить текстового контенту після очищення")

    return content