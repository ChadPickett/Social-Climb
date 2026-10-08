from ..config import Settings
from .base import DataProvider, ProviderError


def build_provider(settings: Settings) -> DataProvider:
    if settings.data_provider == "apify":
        from .apify import ApifyProvider
        return ApifyProvider(settings.apify_token, settings.apify_actor, settings.apify_results_per_tag)
    if settings.data_provider == "graph":
        from .graph_api import GraphApiProvider
        return GraphApiProvider(settings.ig_graph_token, settings.ig_user_id, settings.ig_graph_version)
    if settings.data_provider == "mock":
        from .mock import MockProvider
        return MockProvider()
    raise ProviderError(f"Unknown DATA_PROVIDER '{settings.data_provider}' (use mock, apify or graph)")


__all__ = ["DataProvider", "ProviderError", "build_provider"]
