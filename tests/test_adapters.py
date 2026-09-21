from datetime import datetime, timedelta, timezone

import httpx
import pytest

from adapters.guardian import GuardianAdapter
from adapters.newsapi import NewsAPIAdapter
from adapters.nyt import NYTAdapter
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

    recent_from = (datetime.now(timezone.utc) - timedelta(days=5)).date().isoformat()
    recent_to = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

    adapter = NewsAPIAdapter()
    params = SearchParams(query="bny", from_date=recent_from, to_date=recent_to)
    articles = await adapter.search(params)

    assert captured["url"].endswith("/everything")
    assert captured["params"]["from"] == recent_from
    assert captured["params"]["to"] == recent_to
    assert captured["headers"]["X-Api-Key"] == "test-news-key"
    assert len(articles) == 1
    article = articles[0]
    assert article.title == "Title"
    assert article.source_name == "Example"
    assert article.provider == "newsapi"
    assert article.published_at is not None


@pytest.mark.asyncio
async def test_newsapi_clamps_from_date_beyond_plan_history(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {"articles": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NewsAPIAdapter()
    params = SearchParams(query="bny", from_date="2020-01-01")
    await adapter.search(params)

    expected_cutoff = (
        datetime.now(timezone.utc) - timedelta(days=NewsAPIAdapter.history_limit_days)
    ).date().isoformat()
    assert captured["params"]["from"] == expected_cutoff


@pytest.mark.asyncio
async def test_newsapi_skips_request_when_range_entirely_out_of_reach(monkeypatch):
    called = False

    async def fake_get(self, url, **kwargs):
        nonlocal called
        called = True
        return make_response(200, {"articles": []})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NewsAPIAdapter()
    params = SearchParams(query="bny", from_date="2020-01-01", to_date="2020-02-01")
    articles = await adapter.search(params)

    assert articles == []
    assert called is False


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
@pytest.mark.parametrize(
    "category, expected_section",
    [("sports", "sport"), ("entertainment", "culture|film|music|stage"), ("business", "business")],
)
async def test_guardian_remaps_categories_to_matching_sections(monkeypatch, category, expected_section):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {"response": {"results": []}})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = GuardianAdapter()
    await adapter.search(SearchParams(query="bny", category=category))

    assert captured["params"]["section"] == expected_section


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


@pytest.mark.asyncio
async def test_nyt_search_normalizes_articles(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {
            "response": {
                "docs": [{
                    "web_url": "https://nytimes.com/a",
                    "snippet": "Summary",
                    "headline": {"main": "NYT Title"},
                    "byline": {"original": "By Jane Doe"},
                    "pub_date": "2024-01-01T12:00:00+0000",
                    "section_name": "Business",
                }]
            }
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    articles = await adapter.search(SearchParams(query="bny"))

    assert captured["params"]["api-key"] == "test-nyt-key"
    assert len(articles) == 1
    article = articles[0]
    assert article.title == "NYT Title"
    assert article.url == "https://nytimes.com/a"
    assert article.source_name == "The New York Times"
    assert article.description == "Summary"
    assert article.author == "Jane Doe"
    assert article.section == "Business"
    assert article.provider == "nyt"
    assert article.published_at is not None


@pytest.mark.asyncio
async def test_nyt_search_sends_date_range_and_zero_based_page(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {"response": {"docs": []}})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    params = SearchParams(query="bny", from_date="2024-01-01", to_date="2024-01-31", page=2)
    await adapter.search(params)

    assert captured["params"]["begin_date"] == "20240101"
    assert captured["params"]["end_date"] == "20240131"
    assert captured["params"]["page"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "category, expected_fq",
    [("business", 'section.name:"Business"'), ("science", 'section.name:"Science"')],
)
async def test_nyt_maps_categories_to_section_fq(monkeypatch, category, expected_fq):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {"response": {"docs": []}})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    await adapter.search(SearchParams(query="bny", category=category))

    assert captured["params"]["fq"] == expected_fq


@pytest.mark.asyncio
async def test_nyt_unsupported_category_is_dropped_without_fq(monkeypatch):
    captured = {}

    async def fake_get(self, url, **kwargs):
        captured["params"] = kwargs.get("params")
        return make_response(200, {"response": {"docs": []}})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    await adapter.search(SearchParams(query="bny", category="entertainment"))

    assert "fq" not in captured["params"]


@pytest.mark.asyncio
async def test_nyt_rate_limit_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return make_response(429)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    with pytest.raises(ProviderError) as exc_info:
        await adapter.search(SearchParams(query="bny"))
    assert exc_info.value.provider == "nyt"


@pytest.mark.asyncio
async def test_nyt_unauthorized_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return make_response(401)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    with pytest.raises(ProviderError) as exc_info:
        await adapter.search(SearchParams(query="bny"))
    assert exc_info.value.provider == "nyt"


@pytest.mark.asyncio
async def test_nyt_timeout_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    with pytest.raises(ProviderError):
        await adapter.search(SearchParams(query="bny"))


@pytest.mark.asyncio
async def test_nyt_malformed_response_raises_provider_error(monkeypatch):
    async def fake_get(self, url, **kwargs):
        return make_response(200, {"unexpected": "shape"})

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    adapter = NYTAdapter()
    with pytest.raises(ProviderError):
        await adapter.search(SearchParams(query="bny"))
