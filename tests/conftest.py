import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("NEWS_API_KEY", "test-news-key")
os.environ.setdefault("GUARDIAN_API_KEY", "test-guardian-key")
os.environ.setdefault("NYT_API_KEY", "test-nyt-key")


@pytest.fixture(autouse=True)
def _clear_search_cache():
    import search

    search._PAGE_CACHE.clear()
    yield
    search._PAGE_CACHE.clear()
