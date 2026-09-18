from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from models import NEWSAPI_CATEGORIES, SearchParams
from search import run_search

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def index(
    request: Request,
    q: str | None = None,
    from_date: str = "",
    to_date: str = "",
    source: str = "",
    category: str = "",
):
    context = {
        "categories": NEWSAPI_CATEGORIES,
        "form": {"q": q or "", "from_date": from_date, "to_date": to_date, "source": source, "category": category},
        "articles": None,
        "errors": [],
        "validation_error": None,
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
            )
            result = await run_search(params)
            context["articles"] = result.articles
            context["errors"] = result.errors

    return templates.TemplateResponse(request, "index.html", context)
