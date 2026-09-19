from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

import db
from adapters.newsapi import NewsAPIAdapter
from models import NEWSAPI_CATEGORIES, PROVIDER_NAMES, SearchParams
from search import run_search


@asynccontextmanager
async def lifespan(_app: FastAPI):
    db.init_db()
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


def _format_date(value):
    if not value:
        return ""
    if isinstance(value, str):
        return value[:10]
    return value.strftime("%Y-%m-%d")


templates.env.filters["date"] = _format_date
templates.env.filters["provider_name"] = lambda value: PROVIDER_NAMES.get(value, value)


@app.get("/")
async def index(
    request: Request,
    q: str | None = None,
    from_date: str = "",
    to_date: str = "",
    source: str = "",
    category: str = "",
    page: int = 1,
):
    page = max(page, 1)
    context = {
        "categories": NEWSAPI_CATEGORIES,
        "form": {"q": q or "", "from_date": from_date, "to_date": to_date, "source": source, "category": category},
        "articles": None,
        "errors": [],
        "validation_error": None,
        "newsapi_date_warning": None,
        "newsapi_cap_warning": None,
        "page": page,
        "has_more": False,
        "recent_searches": db.get_recent_searches(limit=10),
        "bookmarked_urls": db.get_bookmarked_urls(),
    }

    if q is not None:
        query = q.strip()
        if not query:
            context["validation_error"] = "Please enter a search term."
        elif from_date and to_date and from_date > to_date:
            context["validation_error"] = "Start date must be before end date."
        else:
            params = SearchParams(
                query=query,
                from_date=from_date or None,
                to_date=to_date or None,
                source=source or None,
                category=category or None,
                page=page,
            )

            if params.from_date and not params.category:
                history_limit_days = NewsAPIAdapter.history_limit_days
                cutoff = (datetime.now(timezone.utc) - timedelta(days=history_limit_days)).date().isoformat()
                if params.from_date < cutoff:
                    context["newsapi_date_warning"] = (
                        f"NewsAPI's plan only covers the last {history_limit_days} days, so results "
                        f"before {cutoff} will only include Guardian articles."
                    )

            if params.page * params.page_size > NewsAPIAdapter.max_results:
                context["newsapi_cap_warning"] = (
                    f"NewsAPI's plan caps total results at {NewsAPIAdapter.max_results} articles per search, "
                    "so further pages will only include Guardian articles."
                )

            result = await run_search(params)
            context["articles"] = result.articles
            context["errors"] = result.errors
            context["has_more"] = result.has_more
            db.save_recent_search(params.query, params.from_date, params.to_date, params.source, params.category)
            context["recent_searches"] = db.get_recent_searches(limit=10)

    return templates.TemplateResponse(request, "index.html", context)


@app.get("/bookmarks")
async def bookmarks_page(request: Request):
    return templates.TemplateResponse(request, "bookmarks.html", {"bookmarks": db.list_bookmarks()})


@app.post("/bookmarks")
async def create_bookmark(
    request: Request,
    title: str = Form(...),
    url: str = Form(...),
    source_name: str = Form(...),
    provider: str = Form(...),
    author: str = Form(""),
    published_at: str = Form(""),
    description: str = Form(""),
    image_url: str = Form(""),
):
    db.add_bookmark(title, url, source_name, author or None, published_at or None, description or None, image_url or None, provider)
    return RedirectResponse(url=request.headers.get("referer") or "/", status_code=303)


@app.post("/bookmarks/{bookmark_id}/delete")
async def delete_bookmark(bookmark_id: int, request: Request):
    db.remove_bookmark(bookmark_id)
    return RedirectResponse(url=request.headers.get("referer") or "/bookmarks", status_code=303)
