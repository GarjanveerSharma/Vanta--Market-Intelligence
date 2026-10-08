from __future__ import annotations

import asyncio
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

from config.settings import get_settings
from ingestion.publisher import publish_news

logger = logging.getLogger(__name__)


def parse_feed(xml_content: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(xml_content)
    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        url = (item.findtext("link") or "").strip()
        if not title or not url:
            continue
        raw_date = item.findtext("pubDate")
        published = ""
        if raw_date:
            try:
                published = parsedate_to_datetime(raw_date).astimezone(timezone.utc).isoformat()
            except (TypeError, ValueError, OverflowError):
                logger.warning("Ignoring invalid RSS publication date: %r", raw_date)
        items.append({
            "title": title,
            "url": url,
            "published_at": published,
            "summary": (item.findtext("description") or "").strip(),
        })
    return items


async def fetch_once() -> int:
    url = get_settings().news_feed_url
    if not url:
        logger.info("NEWS_FEED_URL is empty; news ingestion is disabled")
        return 0
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
    articles = parse_feed(response.content)
    for article in articles:
        await publish_news(article)
    return len(articles)


async def run_news_fetcher(poll_seconds: int = 300) -> None:
    if poll_seconds < 30:
        raise ValueError("poll_seconds must be at least 30")
    while True:
        try:
            logger.info("Published %d news headlines", await fetch_once())
        except asyncio.CancelledError:
            raise
        except (httpx.HTTPError, ET.ParseError):
            logger.exception("News feed fetch failed")
        await asyncio.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=get_settings().log_level)
    asyncio.run(run_news_fetcher())