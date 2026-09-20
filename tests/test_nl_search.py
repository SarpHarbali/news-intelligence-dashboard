from datetime import date

import pytest
from openai import OpenAIError

import nl_search
from config import settings
from models import SearchParams


class FakeResponse:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed


class FakeResponses:
    def __init__(self, output_parsed=None, exc=None):
        self._output_parsed = output_parsed
        self._exc = exc

    async def parse(self, **kwargs):
        if self._exc:
            raise self._exc
        return FakeResponse(self._output_parsed)


class FakeClient:
    def __init__(self, output_parsed=None, exc=None):
        self.responses = FakeResponses(output_parsed, exc)


@pytest.fixture(autouse=True)
def openai_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")


@pytest.mark.asyncio
async def test_valid_output_produces_expected_filters(monkeypatch):
    parsed = nl_search.ParsedQuery(
        query="uk politics", from_date="2026-09-12", to_date="2026-09-19", source="BBC"
    )
    monkeypatch.setattr(nl_search, "AsyncOpenAI", lambda **kwargs: FakeClient(output_parsed=parsed))

    result = await nl_search.parse_natural_language("find me news from bbc about uk politics last week", date(2026, 9, 19))

    assert result == parsed
    assert nl_search.to_search_params(result, page=1) == SearchParams(
        query="uk politics", from_date="2026-09-12", to_date="2026-09-19", source="BBC", page=1
    )


def test_invalid_date_range_is_dropped():
    parsed = nl_search.ParsedQuery.model_construct(
        query="bank news", from_date="2026-09-19", to_date="2026-09-01", source=None
    )

    validated = nl_search._validate(parsed)

    assert validated.from_date is None
    assert validated.to_date is None


@pytest.mark.asyncio
async def test_malformed_output_falls_back_to_none(monkeypatch):
    monkeypatch.setattr(nl_search, "AsyncOpenAI", lambda **kwargs: FakeClient(output_parsed=None))

    result = await nl_search.parse_natural_language("gibberish", date(2026, 9, 19))

    assert result is None


@pytest.mark.asyncio
async def test_api_error_falls_back_to_none(monkeypatch):
    monkeypatch.setattr(nl_search, "AsyncOpenAI", lambda **kwargs: FakeClient(exc=OpenAIError("timed out")))

    result = await nl_search.parse_natural_language("bank news", date(2026, 9, 19))

    assert result is None


@pytest.mark.asyncio
async def test_missing_api_key_skips_parsing_without_creating_a_client(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")

    def fail_if_called(**kwargs):
        raise AssertionError("AsyncOpenAI should not be constructed without an API key")

    monkeypatch.setattr(nl_search, "AsyncOpenAI", fail_if_called)

    result = await nl_search.parse_natural_language("bank news", date(2026, 9, 19))

    assert result is None
