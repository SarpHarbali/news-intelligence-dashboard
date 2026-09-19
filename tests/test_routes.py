import pytest
from fastapi.testclient import TestClient

import db
import main
from config import settings
from models import Article, ProviderError, SearchResult


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    with TestClient(main.app) as c:
        yield c


def test_search_renders_articles_and_errors(client, monkeypatch):
    async def fake_run_search(params):
        return SearchResult(
            articles=[
                Article(title="Hello World", url="https://example.com/a", source_name="Example", provider="newsapi")
            ],
            errors=[ProviderError("guardian", "service unavailable")],
        )

    monkeypatch.setattr(main, "run_search", fake_run_search)

    response = client.get("/", params={"q": "bny"})

    assert response.status_code == 200
    assert "Hello World" in response.text
    assert "Guardian: service unavailable" in response.text


def test_empty_query_shows_validation_error(client):
    response = client.get("/", params={"q": "   "})

    assert response.status_code == 200
    assert "Please enter a search term." in response.text


def test_invalid_date_range_shows_validation_error(client):
    response = client.get("/", params={"q": "bny", "from_date": "2024-02-01", "to_date": "2024-01-01"})

    assert response.status_code == 200
    assert "Start date must be before end date." in response.text


def test_search_saves_recent_search(client, monkeypatch):
    async def fake_run_search(params):
        return SearchResult(articles=[], errors=[])

    monkeypatch.setattr(main, "run_search", fake_run_search)

    client.get("/", params={"q": "bny mellon"})

    recents = db.get_recent_searches()
    assert any(r["query"] == "bny mellon" for r in recents)


def test_already_bookmarked_article_can_be_removed_from_search_results(client, monkeypatch):
    async def fake_run_search(params):
        return SearchResult(
            articles=[
                Article(title="Hello World", url="https://example.com/a", source_name="Example", provider="newsapi")
            ],
            errors=[],
        )

    monkeypatch.setattr(main, "run_search", fake_run_search)
    db.add_bookmark("Hello World", "https://example.com/a", "Example", None, None, None, None, "newsapi")
    bookmark_id = db.list_bookmarks()[0]["id"]

    response = client.get("/", params={"q": "bny"})
    assert f"/bookmarks/{bookmark_id}/delete" in response.text

    delete_response = client.post(f"/bookmarks/{bookmark_id}/delete", follow_redirects=False)
    assert delete_response.status_code == 303
    assert db.list_bookmarks() == []


def test_bookmark_add_list_and_delete(client):
    response = client.post(
        "/bookmarks",
        data={"title": "Test Article", "url": "https://example.com/test", "source_name": "Example", "provider": "newsapi"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get("/bookmarks")
    assert "Test Article" in page.text

    bookmarks = db.list_bookmarks()
    assert len(bookmarks) == 1
    bookmark_id = bookmarks[0]["id"]

    delete_response = client.post(f"/bookmarks/{bookmark_id}/delete", follow_redirects=False)
    assert delete_response.status_code == 303

    page_after = client.get("/bookmarks")
    assert "Test Article" not in page_after.text
