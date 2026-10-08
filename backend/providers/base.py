from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..models import Post


class ProviderError(RuntimeError):
    pass


class DataProvider(ABC):
    name: str

    @abstractmethod
    def fetch(self, hashtag: str, since: datetime) -> list[Post]:
        """Return posts tagged with `hashtag` published at or after `since`."""
