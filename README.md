# News Intelligence Dashboard

A small FastAPI web app that searches news across multiple providers, normalizes the results, and shows them in a single dashboard.

## Features

- Search by keyword, date, source, and category
- Combined, normalized results from multiple news providers
- Graceful handling of individual provider failures
- Recent searches and bookmarks stored in SQLite
- Optional natural-language search ("find news about US politics from Reuters last week") and sentiment tagging (positive/negative/neutral), powered by OpenAI.

## Architecture

Each news source is wrapped in an adapter (`adapters/`) implementing a common `NewsProvider` interface and returning results normalized into a shared `Article` model (`models.py`). `search.py` fans out to all adapters concurrently, merges and sorts results, and isolates per-provider failures so one broken source doesn't take down the others. `db.py` handles SQLite persistence for recent searches, bookmarks, and cached sentiment labels.


## Setup

Requires Python 3.10+ and API keys for [NewsAPI](https://newsapi.org/), [The Guardian](https://open-platform.theguardian.com/), and [The New York Times](https://developer.nytimes.com/).

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Add your API keys to `.env`. `OPENAI_API_KEY` is optional and can be created on the [OpenAI API keys page](https://platform.openai.com/api-keys).

## Run

```bash
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Tests

```bash
pytest
```
