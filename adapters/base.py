from abc import ABC, abstractmethod

from models import Article, SearchParams


class NewsProvider(ABC):
    name: str

    @abstractmethod
    async def search(self, params: SearchParams) -> list[Article]: ...
