from datetime import datetime

import httpx

from adapters.base import NewsProvider
from config import settings
from models import Article, ProviderError, SearchParams

BASE_URL = "https://content.guardianapis.com/search"


class GuardianAdapter(NewsProvider):
    name = "guardian"

    async def search(self, params: SearchParams) -> list[Article]:
        query = {
            "q": params.query,
            "api-key": settings.guardian_api_key,
            "page-size": min(params.page_size, 50),
            "page": params.page,
            "order-by": "relevance",
            "show-fields": "trailText,byline,thumbnail",
        }
        if params.from_date:
            query["from-date"] = params.from_date
        if params.to_date:
            query["to-date"] = params.to_date
        if params.category:
            query["section"] = params.category

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(BASE_URL, params=query)
        except httpx.TimeoutException:
            raise ProviderError(self.name, "request timed out")
        except httpx.ConnectError:
            raise ProviderError(self.name, "service unavailable")

        if response.status_code == 429:
            raise ProviderError(self.name, "rate limit reached")
        if response.status_code != 200:
            raise ProviderError(self.name, f"request failed with status {response.status_code}")

        try:
            data = response.json()["response"]
            return [self._to_article(item) for item in data["results"]]
        except (KeyError, TypeError, ValueError):
            raise ProviderError(self.name, "unexpected response format")

    def _to_article(self, item: dict) -> Article:
        fields = item.get("fields") or {}
        published_at = None
        if item.get("webPublicationDate"):
            published_at = datetime.fromisoformat(item["webPublicationDate"].replace("Z", "+00:00"))

        return Article(
            title=item["webTitle"],
            description=fields.get("trailText"),
            url=item["webUrl"],
            source_name="The Guardian",
            author=fields.get("byline"),
            published_at=published_at,
            image_url=fields.get("thumbnail"),
            section=item.get("sectionName"),
            provider=self.name,
        )
