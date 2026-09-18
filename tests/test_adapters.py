import httpx
import pytest

from adapters.guardian import GuardianAdapter
from adapters.newsapi import NewsAPIAdapter
from models import ProviderError, SearchParams


def make_response(status_code, json_data=None):
    return httpx.Response(status_code, json=json_data if json_data is not None else {})


@pytest.mark.asyncio
async def test_newsapi_everything_search_normalizes_articles(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        captured["headers"] = kwargs.get("headers")
        return make_response(200, {
            "articles": [{
                "title": "Title",
                "description": "Desc",
                "url": "https://example.com/a",
                "source": {"name": "Example"},
                "author": "Jane",
                "publishedAt": "2024-01-01T12:00:00Z",
                "urlToImage": "https://example.com/img.png",
            }]
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NewsAPIAdapter()
    params = SearchParams(query="bny", from_date="2024-01-01", to_date="2024-01-02")
    articles = await adapter.search(params)

    assert captured["url"].endswith("/everything")
    assert captured["params"]["from"] == "2024-01-01"
    assert captured["params"]["to"] == "2024-01-02"
    assert captured["headers"]["X-Api-Key"] == "test-news-key"
    assert len(articles) == 1
    article = articles[0]
    assert article.title == "Title"
    assert article.source_name == "Example"
    assert article.provider == "newsapi"
    assert article.published_at is not None


@pytest.mark.asyncio
async def test_newsapi_uses_top_headlines_for_category(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return make_response(200, {"articles": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NewsAPIAdapter()
    params = SearchParams(query="bny", category="business", from_date="2024-01-01")
    await adapter.search(params)

    assert captured["url"].endswith("/top-headlines")
    assert captured["params"]["category"] == "business"
    assert "from" not in captured["params"]


@pytest.mark.asyncio
async def test_newsapi_rate_limit_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return make_response(429)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NewsAPIAdapter()
    with pytest.raises(ProviderError) as exc_info:
        await adapter.search(SearchParams(query="bny"))
    assert exc_info.value.provider == "newsapi"


@pytest.mark.asyncio
async def test_newsapi_timeout_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NewsAPIAdapter()
    with pytest.raises(ProviderError):
        await adapter.search(SearchParams(query="bny"))


@pytest.mark.asyncio
async def test_guardian_search_normalizes_articles(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {
            "response": {
                "results": [{
                    "webTitle": "Guardian Title",
                    "webUrl": "https://guardian.com/a",
                    "webPublicationDate": "2024-01-01T12:00:00Z",
                    "sectionName": "Business",
                    "fields": {
                        "trailText": "Summary",
                        "byline": "John Smith",
                        "thumbnail": "https://guardian.com/img.png",
                    },
                }]
            }
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = GuardianAdapter()
    params = SearchParams(query="bny", category="business")
    articles = await adapter.search(params)

    assert captured["params"]["section"] == "business"
    assert len(articles) == 1
    article = articles[0]
    assert article.title == "Guardian Title"
    assert article.source_name == "The Guardian"
    assert article.author == "John Smith"
    assert article.section == "Business"
    assert article.provider == "guardian"


@pytest.mark.asyncio
async def test_guardian_rate_limit_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return make_response(429)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = GuardianAdapter()
    with pytest.raises(ProviderError) as exc_info:
        await adapter.search(SearchParams(query="bny"))
    assert exc_info.value.provider == "guardian"


@pytest.mark.asyncio
async def test_guardian_timeout_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = GuardianAdapter()
    with pytest.raises(ProviderError):
        await adapter.search(SearchParams(query="bny"))
