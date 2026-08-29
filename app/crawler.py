"""
Crawl4AI wrapper: load a page in headless Chromium (Playwright), drop
script/style/nav/ads/cookie banners, and return clean Markdown of the main content.

BrowserConfig / CrawlerRunConfig below are tuned for a modest server (no GPU):
images and extra Chromium background features are disabled so crawls stay
faster and lighter on RAM.
"""
import logging

from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig
from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger("ai_parser.crawler")

_BROWSER_CONFIG = BrowserConfig(
    # Do not use "chrome": Google Chrome is not supported on Linux ARM64.
    # Bundled Chromium (default) works on ARM64 Ubuntu.
    browser_type="chromium",
    headless=True,
    verbose=False,
    text_mode=True,  # skip images / rich media — faster and cheaper on RAM
    light_mode=True,  # disable extra Chromium background features
    avoid_ads=True,  # block known ad / tracking domains at the browser network layer
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
        cache_mode=CacheMode.BYPASS,  # always fetch a fresh page
        markdown_generator=md_generator,
        excluded_tags=_EXCLUDED_TAGS,
        word_count_threshold=1,  # keep short pages / blocks
        page_timeout=settings.crawl_timeout_ms,
        remove_overlay_elements=True,  # drop modals / popups
        remove_consent_popups=True,  # drop cookie / GDPR banners
        wait_until="domcontentloaded",
        verbose=False,
    )


async def fetch_clean_markdown(url: str) -> str:
    """Fetch `url` and return cleaned Markdown (`fit_markdown`, falling back to `raw_markdown`)."""
    run_config = _build_run_config()

    try:
        async with AsyncWebCrawler(config=_BROWSER_CONFIG) as crawler:
            result = await crawler.arun(url=url, config=run_config)
    except Exception as exc:
        logger.exception("Crawl failed for %s", url)
        raise HTTPException(status_code=502, detail=f"Failed to load the page: {exc}") from exc

    if not result.success:
        raise HTTPException(
            status_code=502,
            detail=f"The crawler could not process the page: {result.error_message or 'unknown error'}",
        )

    md = result.markdown
    fit = (getattr(md, "fit_markdown", "") or "").strip()
    raw = (getattr(md, "raw_markdown", "") or str(md)).strip()

    content = fit or raw
    if not content:
        raise HTTPException(status_code=502, detail="The page had no text content after cleaning")

    return content
