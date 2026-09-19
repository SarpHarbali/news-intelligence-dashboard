import sqlite3
from contextlib import contextmanager

from config import settings


@contextmanager
def _connect():
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recent_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                from_date TEXT,
                to_date TEXT,
                source TEXT,
                category TEXT,
                searched_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                source_name TEXT,
                author TEXT,
                published_at TEXT,
                description TEXT,
                image_url TEXT,
                provider TEXT,
                bookmarked_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)


def save_recent_search(query, from_date, to_date, source, category):
    with _connect() as conn:
        last = conn.execute(
            "SELECT query, from_date, to_date, source, category FROM recent_searches ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if last and tuple(last) == (query, from_date, to_date, source, category):
            return
        conn.execute(
            "INSERT INTO recent_searches (query, from_date, to_date, source, category) VALUES (?, ?, ?, ?, ?)",
            (query, from_date, to_date, source, category),
        )


def get_recent_searches(limit=10):
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM recent_searches ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(row) for row in rows]


def add_bookmark(title, url, source_name, author, published_at, description, image_url, provider):
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO bookmarks
               (title, url, source_name, author, published_at, description, image_url, provider)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (title, url, source_name, author, published_at, description, image_url, provider),
        )


def remove_bookmark(bookmark_id):
    with _connect() as conn:
        conn.execute("DELETE FROM bookmarks WHERE id = ?", (bookmark_id,))


def list_bookmarks():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM bookmarks ORDER BY id DESC").fetchall()
        return [dict(row) for row in rows]


def get_bookmarked_urls():
    with _connect() as conn:
        rows = conn.execute("SELECT url FROM bookmarks").fetchall()
        return {row["url"] for row in rows}
