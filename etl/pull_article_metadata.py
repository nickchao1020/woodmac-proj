from enum import Enum
import asyncio
import logging
import os
from pathlib import Path
import json

import aiohttp
from bs4 import BeautifulSoup
from pydantic import BaseModel


LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_FILE = Path(__file__).parent / "data" / "article_metadata.json"
OUTPUT_FILE = Path(os.getenv("OUTPUT_FILE", DEFAULT_OUTPUT_FILE))

BASE_URL = "https://www.eia.gov/todayinenergy"
DATE_FORMAT = "%B %d, %Y"

class ArticleTag(Enum):
    LIQUID_FUELS = "liquid%20fuels"
    NATURAL_GAS = "natural%20gas"
    ELECTRICITY = "electricity"
    OIL_PETROLEUM = "oil/petroleum"
    PRODUCTION_SUPPLY = "production/supply"
    CRUDE_OIL = "crude%20oil"
    CONSUMPTION_DEMAND = "consumption/demand"
    GENERATION = "generation"
    PRICES = "prices"
    MAP = "map"
    STATES = "states"
    EXPORTS_IMPORTS = "exports/imports"
    INTERNATIONAL = "international"
    COAL = "coal"
    RENEWABLES = "renewables"
    WEATHER = "weather"
    GASOLINE = "gasoline"
    FORECASTS_PROJECTIONS = "forecasts/projections"
    CAPACITY = "capacity"
    STEO = "steo%20(short-term%20energy%20outlook)"


class ArticleMetadata(BaseModel):
    title: str
    date: str
    path: str


def _dedupe_articles(articles: list[ArticleMetadata]) -> list[ArticleMetadata]:
    seen = set()
    deduped = []
    for a in articles:
        if a.path not in seen:
            seen.add(a.path)
            deduped.append(a)
    return deduped


def _extract_articles(html_content: str) -> list[ArticleMetadata]:
    soup = BeautifulSoup(html_content, "html.parser")
    articles_div = soup.find("div", class_="tie-article tag-view")
    if not articles_div:
        return []
    articles = []
    # Find all date spans and h2 elements containing article titles
    date_spans = articles_div.find_all('span', class_='date')
    for date_span in date_spans:
        # Get the date
        date = date_span.text.strip()
        # Get the next h2 element which contains the article title and URL
        h2_element = date_span.find_next('h2')
        if h2_element:
            a_element = h2_element.find('a')
            if a_element:
                title = a_element.text.strip()
                url = a_element['href']
                articles.append(ArticleMetadata(title=title, date=date, path=url))
    return articles


async def _fetch_article_list(session: aiohttp.ClientSession, tag: ArticleTag) -> list[ArticleMetadata]:
    url = f"{BASE_URL}/index.php?tg={tag.value}"
    logger.debug(f"Fetching articles for {tag} at {url}")
    async with session.get(url) as response:
        raw_articles = await response.text()
        return _extract_articles(raw_articles)


async def _fetch_all_articles() -> list[str]:
    async with aiohttp.ClientSession() as session:
        articles = []
        for tag in ArticleTag:
            logger.debug(f"Fetching articles for tag: {tag}")
            articles += await _fetch_article_list(session, tag)
        return articles


if __name__ == "__main__":
    articles = asyncio.run(_fetch_all_articles())
    # Since we are pulling article IDs by tag, we need to dedupe
    # as articles can have many tags, resulting in tags overlapping tags.
    articles = _dedupe_articles(articles)
    articles = [article.model_dump(mode="json") for article in articles]
    with open(OUTPUT_FILE, "w") as f:
        json.dump(articles, f, indent=4)
