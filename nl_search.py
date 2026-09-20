from datetime import date

from openai import AsyncOpenAI, OpenAIError
from pydantic import BaseModel

from config import settings
from models import SearchParams

MODEL = "gpt-4o-mini"
TIMEOUT_SECONDS = 8.0


class ParsedQuery(BaseModel):
    query: str
    from_date: str | None = None
    to_date: str | None = None
    source: str | None = None


def _valid_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _validate(parsed: ParsedQuery) -> ParsedQuery | None:
    query = parsed.query.strip()
    if not query:
        return None

    from_date = _valid_date(parsed.from_date)
    to_date = _valid_date(parsed.to_date)
    if from_date and to_date and from_date > to_date:
        from_date = to_date = None

    source = (parsed.source or "").strip() or None

    return ParsedQuery(query=query, from_date=from_date, to_date=to_date, source=source)


async def parse_natural_language(raw_query: str, today: date) -> ParsedQuery | None:
    if not settings.openai_api_key:
        return None

    prompt = (
        f"Today's date is {today.isoformat()}. Convert the user's news search request into structured "
        "search filters. "
        "Set query to the core search topic only, dropping conversational filler such as 'find me', "
        "'show me', 'news about' or 'articles on' — e.g. 'find me news from the BBC about american "
        "politics' has the query 'american politics'. "
        "Resolve any relative dates (e.g. 'last week', 'since March') into absolute from_date/to_date "
        "values in YYYY-MM-DD format, relative to today, using today's year unless the user names a "
        "different one. "
        "Set source to the specific news outlet or publication the user names (e.g. 'BBC', 'Reuters', "
        "'The Guardian'), if any, leaving it unset otherwise. "
        "Leave any other detail (e.g. country, company, topic, sector) as part of the query keywords."
    )

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=TIMEOUT_SECONDS)
    try:
        response = await client.responses.parse(
            model=MODEL,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": raw_query},
            ],
            text_format=ParsedQuery,
        )
    except OpenAIError:
        return None

    if response.output_parsed is None:
        return None

    return _validate(response.output_parsed)


def to_search_params(parsed: ParsedQuery, page: int) -> SearchParams:
    return SearchParams(
        query=parsed.query,
        from_date=parsed.from_date,
        to_date=parsed.to_date,
        source=parsed.source,
        page=page,
    )
