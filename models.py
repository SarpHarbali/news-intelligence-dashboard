from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

NEWSAPI_CATEGORIES = ("business", "entertainment", "general", "health", "science", "sports", "technology")
PROVIDER_NAMES = {"newsapi": "NewsAPI", "guardian": "Guardian", "nyt": "The New York Times"}


class Article(BaseModel):
    title: str
    description: str | None = None
    url: str
    source_name: str
    author: str | None = None
    published_at: datetime | None = None
    image_url: str | None = None
    section: str | None = None
    provider: Literal["newsapi", "guardian", "nyt"]


class SearchParams(BaseModel):
    query: str
    from_date: str | None = None
    to_date: str | None = None
    source: str | None = None
    category: str | None = None
    page_size: int = 50
    page: int = 1


class ProviderError(Exception):
    def __init__(self, provider: str, message: str):
        self.provider = provider
        self.message = message
        super().__init__(f"{provider}: {message}")


@dataclass
class SearchResult:
    articles: list[Article]
    errors: list[ProviderError]
    has_more: bool = False
