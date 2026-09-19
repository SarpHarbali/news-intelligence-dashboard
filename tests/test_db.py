import pytest

import db
from config import settings


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    db.init_db()


def test_save_and_get_recent_searches():
    db.save_recent_search("bny", "2024-01-01", "2024-01-02", "bbc", "business")
    db.save_recent_search("mellon", None, None, None, None)

    recents = db.get_recent_searches(limit=10)

    assert len(recents) == 2
    assert recents[0]["query"] == "mellon"
    assert recents[1]["source"] == "bbc"


def test_save_recent_search_skips_consecutive_duplicate():
    db.save_recent_search("bny", "2024-01-01", "2024-01-02", "bbc", "business")
    db.save_recent_search("bny", "2024-01-01", "2024-01-02", "bbc", "business")

    recents = db.get_recent_searches(limit=10)

    assert len(recents) == 1


def test_recent_searches_respects_limit():
    for i in range(5):
        db.save_recent_search(f"q{i}", None, None, None, None)

    recents = db.get_recent_searches(limit=3)

    assert len(recents) == 3
    assert recents[0]["query"] == "q4"


def test_add_list_and_remove_bookmark():
    db.add_bookmark("Title", "https://example.com/a", "Example", "Author", None, "Desc", None, "newsapi")

    bookmarks = db.list_bookmarks()

    assert len(bookmarks) == 1
    assert bookmarks[0]["title"] == "Title"

    db.remove_bookmark(bookmarks[0]["id"])

    assert db.list_bookmarks() == []


def test_bookmark_url_is_unique():
    db.add_bookmark("Title", "https://example.com/a", "Example", None, None, None, None, "newsapi")
    db.add_bookmark("Title Again", "https://example.com/a", "Example", None, None, None, None, "newsapi")

    assert len(db.list_bookmarks()) == 1
