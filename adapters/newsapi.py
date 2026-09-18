from datetime import datetime

import httpx

from adapters.base import NewsProvider
from config import settings
from models import Article, ProviderError, SearchParams

BASE_URL = "https://newsapi.org/v2"


class NewsAPIAdapter(NewsProvider):
    name = "newsapi"

    async def search(self, params: SearchParams) -> list[Article]:
        headers = {"X-Api-Key": settings.news_api_key}
        # top-headlines is the only NewsAPI endpoint that supports category, but it doesn't accept date-range params, so date filters are dropped when it's used.
        if params.category:
            url = f"{BASE_URL}/top-headlines"
            query = {"q": params.query, "category": params.category, "pageSize": params.page_size}
        else:
            url = f"{BASE_URL}/everything"
            query = {"q": params.query, "pageSize": params.page_size}
            if params.from_date:
                query["from"] = params.from_date
            if params.to_date:
                query["to"] = params.to_date

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=query, headers=headers)
        except httpx.TimeoutException:
            raise ProviderError(self.name, "request timed out")
        except httpx.ConnectError:
            raise ProviderError(self.name, "service unavailable")

        if response.status_code == 429:
            raise ProviderError(self.name, "rate limit reached")
        if response.status_code != 200:
            raise ProviderError(self.name, f"request failed with status {response.status_code}")

        try:
            data = response.json()
            return [self._to_article(item, params.category) for item in data["articles"]]
        except (KeyError, TypeError, ValueError):
            raise ProviderError(self.name, "unexpected response format")

    def _to_article(self, item: dict, category: str | None) -> Article:
        published_at = None
        if item.get("publishedAt"):
            published_at = datetime.fromisoformat(item["publishedAt"].replace("Z", "+00:00"))

        return Article(
            title=item["title"],
            description=item.get("description"),
            url=item["url"],
            source_name=(item.get("source") or {}).get("name") or "Unknown",
            author=item.get("author"),
            published_at=published_at,
            image_url=item.get("urlToImage"),
            section=category,
            provider=self.name,
        )
