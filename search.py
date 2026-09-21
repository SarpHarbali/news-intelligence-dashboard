import asyncio
from datetime import datetime, timezone

from adapters.guardian import GuardianAdapter
from adapters.newsapi import NewsAPIAdapter
from adapters.nyt import NYTAdapter
from models import ProviderError, SearchParams, SearchResult

PROVIDERS = [NewsAPIAdapter(), GuardianAdapter(), NYTAdapter()]


async def _fetch_page(provider, params: SearchParams, page: int):
    max_results = getattr(provider, "max_results", None)
    if max_results and page * params.page_size > max_results:
        return []
    page_params = params.model_copy(update={"page": page})
    try:
        return await provider.search(page_params)
    except ProviderError as exc:
        return exc
    except Exception as exc:
        return ProviderError(provider.name, str(exc))


async def run_search(params: SearchParams) -> SearchResult:
    pages = range(1, params.page + 1)
    tasks = [_fetch_page(provider, params, page) for provider in PROVIDERS for page in pages]
    results = await asyncio.gather(*tasks)

    articles = []
    prior_page_articles = []
    errors = []
    seen_urls = set()
    last_page_counts = {}
    result_iter = iter(results)
    for provider in PROVIDERS:
        for page in pages:
            result = next(result_iter)
            if isinstance(result, ProviderError):
                errors.append(result)
                continue
            if page == params.page:
                last_page_counts[provider.name] = len(result)
            for article in result:
                if article.url in seen_urls:
                    continue
                seen_urls.add(article.url)
                articles.append(article)
                if page < params.page:
                    prior_page_articles.append(article)

    if params.source:
        needle = params.source.lower()

        def matches_source(article):
            return needle in article.source_name.lower() or needle == article.provider

        articles = [a for a in articles if matches_source(a)]
        prior_page_articles = [a for a in prior_page_articles if matches_source(a)]

    articles.sort(key=lambda a: a.published_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    has_more = any(count >= params.page_size for count in last_page_counts.values())
    no_new_results = params.page > 1 and len(articles) == len(prior_page_articles)
    if no_new_results:
        has_more = False

    return SearchResult(articles=articles, errors=errors, has_more=has_more, no_new_results=no_new_results)
