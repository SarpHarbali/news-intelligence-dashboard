import asyncio
from datetime import datetime, timezone

from adapters.guardian import GuardianAdapter
from adapters.newsapi import NewsAPIAdapter
from models import ProviderError, SearchParams, SearchResult

PROVIDERS = [NewsAPIAdapter(), GuardianAdapter()]


async def run_search(params: SearchParams) -> SearchResult:
    results = await asyncio.gather(
        *(provider.search(params) for provider in PROVIDERS),
        return_exceptions=True,
    )

    articles = []
    errors = []
    for provider, result in zip(PROVIDERS, results):
        if isinstance(result, ProviderError):
            errors.append(result)
        elif isinstance(result, Exception):
            errors.append(ProviderError(provider.name, str(result)))
        else:
            articles.extend(result)

    if params.source:
        needle = params.source.lower()
        articles = [a for a in articles if needle in a.source_name.lower()]

    articles.sort(key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return SearchResult(articles=articles, errors=errors)
