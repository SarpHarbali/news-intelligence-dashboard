from datetime import datetime

import httpx

from adapters.base import NewsProvider
from config import settings
from models import Article, ProviderError, SearchParams

BASE_URL = "https://api.nytimes.com/svc/search/v2/articlesearch.json"

CATEGORY_TO_SECTION = {
    "business": "Business",
    "health": "Health",
    "science": "Science",
    "sports": "Sports",
    "technology": "Technology",
}


class NYTAdapter(NewsProvider):
    name = "nyt"

    async def search(self, params: SearchParams) -> list[Article]:
        query = {
            "api-key": settings.nyt_api_key,
            "q": params.query,
            "page": params.page - 1,
            "sort": "relevance",
        }
        if params.from_date:
            query["begin_date"] = params.from_date.replace("-", "")
        if params.to_date:
            query["end_date"] = params.to_date.replace("-", "")
        if params.category:
            section = CATEGORY_TO_SECTION.get(params.category)
            if section:
                query["fq"] = f'section.name:"{section}"'

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(BASE_URL, params=query)
        except httpx.TimeoutException:
            raise ProviderError(self.name, "request timed out")
        except httpx.ConnectError:
            raise ProviderError(self.name, "service unavailable")

        if response.status_code == 429:
            raise ProviderError(self.name, "rate limit reached (max 5 requests per minute)")
        if response.status_code == 401:
            raise ProviderError(self.name, "invalid API key")
        if response.status_code != 200:
            raise ProviderError(self.name, f"request failed with status {response.status_code}")

        try:
            data = response.json()["response"]
            return [self._to_article(item) for item in data["docs"] or []]
        except (KeyError, TypeError, ValueError):
            raise ProviderError(self.name, "unexpected response format")

    def _to_article(self, item: dict) -> Article:
        published_at = None
        if item.get("pub_date"):
            published_at = datetime.strptime(item["pub_date"], "%Y-%m-%dT%H:%M:%S%z")

        byline = ((item.get("byline") or {}).get("original") or "").strip()
        if byline.startswith("By "):
            byline = byline[3:].strip()

        return Article(
            title=item["headline"]["main"],
            description=item.get("snippet"),
            url=item["web_url"],
            source_name="The New York Times",
            author=byline or None,
            published_at=published_at,
            section=item.get("section_name"),
            provider=self.name,
        )
