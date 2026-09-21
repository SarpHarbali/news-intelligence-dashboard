import pytest
from openai import OpenAIError

import db
import sentiment
from config import settings
from models import Article


class FakeResponse:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed


class FakeResponses:
    def __init__(self, output_parsed=None, exc=None):
        self._output_parsed = output_parsed
        self._exc = exc
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc:
            raise self._exc
        return FakeResponse(self._output_parsed)


class FakeClient:
    def __init__(self, output_parsed=None, exc=None):
        self.responses = FakeResponses(output_parsed, exc)


def make_articles(n):
    return [
        Article(title=f"Title {i}", description=f"Description {i}", url=f"https://example.com/{i}", source_name="Example", provider="newsapi")
        for i in range(1, n + 1)
    ]


@pytest.fixture(autouse=True)
def openai_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")


@pytest.fixture(autouse=True)
def sentiment_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    db.init_db()


@pytest.mark.asyncio
async def test_valid_output_tags_articles_by_id(monkeypatch):
    articles = make_articles(2)
    parsed = sentiment.SentimentBatch(
        items=[sentiment.SentimentItem(id=1, label="positive"), sentiment.SentimentItem(id=2, label="negative")]
    )
    monkeypatch.setattr(sentiment, "AsyncOpenAI", lambda **kwargs: FakeClient(output_parsed=parsed))

    failed = await sentiment.tag_articles(articles)

    assert failed is False
    assert articles[0].sentiment == "positive"
    assert articles[1].sentiment == "negative"


@pytest.mark.asyncio
async def test_unknown_ids_and_invalid_labels_are_dropped(monkeypatch):
    articles = make_articles(2)
    parsed = sentiment.SentimentBatch(
        items=[
            sentiment.SentimentItem(id=1, label="positive"),
            sentiment.SentimentItem(id=2, label="furious"),
            sentiment.SentimentItem(id=99, label="negative"),
        ]
    )
    monkeypatch.setattr(sentiment, "AsyncOpenAI", lambda **kwargs: FakeClient(output_parsed=parsed))

    failed = await sentiment.tag_articles(articles)

    assert failed is False
    assert articles[0].sentiment == "positive"
    assert articles[1].sentiment is None


@pytest.mark.parametrize(
    "output_parsed, error",
    [(None, None), (None, OpenAIError("timed out"))],
    ids=["missing-output", "api-error"],
)
@pytest.mark.asyncio
async def test_failed_response_leaves_articles_untagged(monkeypatch, output_parsed, error):
    articles = make_articles(1)
    monkeypatch.setattr(
        sentiment,
        "AsyncOpenAI",
        lambda **kwargs: FakeClient(output_parsed=output_parsed, exc=error),
    )

    failed = await sentiment.tag_articles(articles)

    assert failed is True
    assert articles[0].sentiment is None


@pytest.mark.asyncio
async def test_missing_api_key_skips_tagging_without_creating_a_client(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    articles = make_articles(1)

    def fail_if_called(**kwargs):
        raise AssertionError("AsyncOpenAI should not be constructed without an API key")

    monkeypatch.setattr(sentiment, "AsyncOpenAI", fail_if_called)

    failed = await sentiment.tag_articles(articles)

    assert failed is False
    assert articles[0].sentiment is None


@pytest.mark.asyncio
async def test_cache_hit_skips_the_llm_call(monkeypatch):
    articles = make_articles(1)
    db.cache_sentiments({articles[0].url: "positive"})

    def fail_if_called(**kwargs):
        raise AssertionError("AsyncOpenAI should not be constructed when all articles are cached")

    monkeypatch.setattr(sentiment, "AsyncOpenAI", fail_if_called)

    failed = await sentiment.tag_articles(articles)

    assert failed is False
    assert articles[0].sentiment == "positive"


@pytest.mark.asyncio
async def test_mixed_batch_sends_only_uncached_articles(monkeypatch):
    articles = make_articles(2)
    db.cache_sentiments({articles[0].url: "neutral"})
    requested = []

    async def fake_request_labels(batch):
        requested.extend(batch)
        return {1: "negative"}

    monkeypatch.setattr(sentiment, "_request_labels", fake_request_labels)

    failed = await sentiment.tag_articles(articles)

    assert failed is False
    assert articles[0].sentiment == "neutral"
    assert articles[1].sentiment == "negative"
    assert requested == [articles[1]]
