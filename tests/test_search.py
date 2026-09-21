from datetime import datetime, timezone

import pytest

import search
from models import Article, ProviderError, SearchParams


def make_article(title, provider, source_name="Example", published_at=None):
    return Article(
        title=title,
        url=f"https://example.com/{title}",
        source_name=source_name,
        provider=provider,
        published_at=published_at,
    )


class FakeProvider:
    def __init__(self, name, articles=None, error=None):
        self.name = name
        self._articles = articles or []
        self._error = error

    async def search(self, params):
        if self._error:
            raise self._error
        return self._articles


@pytest.mark.asyncio
async def test_partial_failure_returns_other_providers_results(monkeypatch):
    ok = FakeProvider("newsapi", articles=[make_article("A", "newsapi")])
    failing = FakeProvider("guardian", error=ProviderError("guardian", "service unavailable"))
    monkeypatch.setattr(search, "PROVIDERS", [ok, failing])

    result = await search.run_search(SearchParams(query="bny"))

    assert len(result.articles) == 1
    assert result.articles[0].title == "A"
    assert len(result.errors) == 1
    assert result.errors[0].provider == "guardian"


@pytest.mark.asyncio
async def test_both_providers_succeed_merges_and_sorts_by_date(monkeypatch):
    older = make_article("Old", "newsapi", published_at=datetime(2024, 1, 1, tzinfo=timezone.utc))
    newer = make_article("New", "guardian", published_at=datetime(2024, 6, 1, tzinfo=timezone.utc))
    provider_a = FakeProvider("newsapi", articles=[older])
    provider_b = FakeProvider("guardian", articles=[newer])
    monkeypatch.setattr(search, "PROVIDERS", [provider_a, provider_b])

    result = await search.run_search(SearchParams(query="bny"))

    assert [a.title for a in result.articles] == ["New", "Old"]
    assert result.errors == []


@pytest.mark.asyncio
async def test_unexpected_exception_is_isolated_as_provider_error(monkeypatch):
    ok = FakeProvider("newsapi", articles=[make_article("A", "newsapi")])
    broken = FakeProvider("guardian", error=ValueError("boom"))
    monkeypatch.setattr(search, "PROVIDERS", [ok, broken])

    result = await search.run_search(SearchParams(query="bny"))

    assert len(result.articles) == 1
    assert len(result.errors) == 1
    assert result.errors[0].provider == "guardian"


@pytest.mark.asyncio
async def test_source_filter_matches_substring_case_insensitively(monkeypatch):
    bbc = make_article("A", "newsapi", source_name="BBC News")
    cnn = make_article("B", "guardian", source_name="CNN")
    provider_a = FakeProvider("newsapi", articles=[bbc])
    provider_b = FakeProvider("guardian", articles=[cnn])
    monkeypatch.setattr(search, "PROVIDERS", [provider_a, provider_b])

    result = await search.run_search(SearchParams(query="bny", source="bbc"))

    assert len(result.articles) == 1
    assert result.articles[0].source_name == "BBC News"


@pytest.mark.asyncio
async def test_source_filter_matches_provider_id_when_display_name_differs(monkeypatch):
    nyt = make_article("A", "nyt", source_name="The New York Times")
    guardian = make_article("B", "guardian", source_name="The Guardian")
    provider_a = FakeProvider("nyt", articles=[nyt])
    provider_b = FakeProvider("guardian", articles=[guardian])
    monkeypatch.setattr(search, "PROVIDERS", [provider_a, provider_b])

    result = await search.run_search(SearchParams(query="usa", source="nyt"))

    assert len(result.articles) == 1
    assert result.articles[0].source_name == "The New York Times"


@pytest.mark.asyncio
async def test_loading_next_page_with_no_new_articles_reports_no_new_results(monkeypatch):
    bbc = make_article("A", "newsapi", source_name="BBC News")
    provider = FakeProvider("newsapi", articles=[bbc])
    monkeypatch.setattr(search, "PROVIDERS", [provider])

    result = await search.run_search(SearchParams(query="bny", source="bbc", page=2))

    assert len(result.articles) == 1
    assert result.no_new_results is True
    assert result.has_more is False
