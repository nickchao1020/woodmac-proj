from enum import Enum
import asyncio
import logging
import os
from pathlib import Path
import json
from datetime import datetime
import random
from time import sleep
from typing import Optional

import aiohttp
from aiohttp_retry import RetryClient, ExponentialRetry
from bs4 import BeautifulSoup
from pydantic import BaseModel


LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

DEFAULT_ARTICLE_METADATA_FILE = Path(__file__).parent / "data" / "article_metadata.json"
ARTICLE_METADATA_FILE = Path(os.getenv("ARTICLE_METADATA_FILE", DEFAULT_ARTICLE_METADATA_FILE))

DEFAULT_OUTPUT_FILE = Path(__file__).parent / "data" / "articles.json"
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", DEFAULT_OUTPUT_FILE))

BASE_URL = "https://www.eia.gov/todayinenergy"
DATE_FORMAT = "%B %d, %Y"

MAX_CONCURRENT_REQUESTS = os.getenv("MAX_CONCURRENT_REQUESTS", 1)


class Article(BaseModel):
    title: str
    date: str
    content: str
    path: str


def _extract_article_content(html_content: str) -> str:
    soup = BeautifulSoup(html_content, "html.parser")
    article_div = soup.find("div", class_="tie-article")
    return "\n".join(p.get_text() for p in article_div.find_all("p"))


async def _fetch_article(
        session: aiohttp.ClientSession,
        article: Article,
        semaphore: asyncio.Semaphore
) -> Article:
    async with semaphore:
        retry_options = ExponentialRetry(attempts=5)
        retry_client = RetryClient(client_session=session, retry_options=retry_options)
        async with retry_client.get(f"{BASE_URL}/{article['path']}") as response:
            logger.debug(f"Fetching article {article['title']} at {response.url}")
            sleep(random.uniform(0.1, 0.7))
            try:
                raw_content = await response.text()
                content = _extract_article_content(raw_content)
                return Article(title=article["title"], date=article["date"], content=content, path=article["path"])
            except UnicodeDecodeError as e:
                logger.error(f"Error fetching article {article['title']}: {e}")
                return None


async def _fetch_all_articles(articles: list[dict]) -> list[Article]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    async with aiohttp.ClientSession() as session:
        return await asyncio.gather(*(_fetch_article(session, article, semaphore) for article in articles))


if __name__ == "__main__":
    with open(ARTICLE_METADATA_FILE, "r") as f:
        article_metadata = json.load(f)
    article_metadata_filtered = []
    for article in article_metadata:
        article_date = datetime.strptime(article["date"], DATE_FORMAT)
        if article_date >= datetime(2024, 1, 1):
            article_metadata_filtered.append(article)
    articles = asyncio.run(_fetch_all_articles(article_metadata_filtered))
    with open(OUTPUT_FILE, "w") as f:
        json.dump([a.model_dump(mode="json") for a in articles if a is not None], f, indent=4)
