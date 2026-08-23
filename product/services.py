"""
product/services.py

Compatibility proxy re-exporting catalog services from apps.catalog.services.
"""

from apps.catalog.services import (
    STOP_WORDS,
    PRICE_BUDGET_KEYWORDS,
    PRICE_PREMIUM_KEYWORDS,
    CATEGORY_SYNONYMS_ES_EN,
    normalize_and_tokenize_query,
    detect_category_synonym_and_price_intent,
    search_catalog_service,
)

__all__ = [
    'STOP_WORDS',
    'PRICE_BUDGET_KEYWORDS',
    'PRICE_PREMIUM_KEYWORDS',
    'CATEGORY_SYNONYMS_ES_EN',
    'normalize_and_tokenize_query',
    'detect_category_synonym_and_price_intent',
    'search_catalog_service',
]
