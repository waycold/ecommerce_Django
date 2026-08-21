"""
product/services.py

Business logic and service layer for product catalog operations.
Decoupled from HTTP controllers to facilitate reusability, testing, and clean architecture.
"""

import re
from functools import reduce
from typing import Optional, Dict, Any, List, Tuple
from django.db.models import Q, Case, When, Value, IntegerField
from product.models import Item

# Common stop words in Spanish and English to filter out from tokenized catalog searches
STOP_WORDS = {
    'hola', 'me', 'interesa', 'el', 'la', 'los', 'las', 'un', 'una',
    'de', 'en', 'para', 'por', 'con', 'sobre', 'producto', 'precio',
    'the', 'a', 'an', 'of', 'in', 'for', 'with', 'product',
}


def normalize_and_tokenize_query(query: Optional[str]) -> Tuple[str, List[str]]:
    """
    Cleans and normalizes query text:
    1. Removes price prefixes like 'Precio:', 'Price:'.
    2. Strips punctuation symbols: () $ , " ' : ; ! ?
    3. Tokenizes into meaningful keywords (length >= 2, non-stop words).

    Returns:
        tuple: (cleaned_phrase, list_of_tokens)
    """
    if not query:
        return "", []

    raw = str(query)

    # 1. Clean prefixes like "Precio:", "Price:" (case-insensitive)
    raw = re.sub(r'(?i)\b(precio|price)\s*:\s*', ' ', raw)

    # 2. Remove punctuation symbols () $ , " ' and common delimiters
    raw = re.sub(r'[\(\)\$,"\'\:\;\!\?]', ' ', raw)

    # 3. Normalize whitespace
    cleaned_phrase = re.sub(r'\s+', ' ', raw).strip()
    if not cleaned_phrase:
        return "", []

    # 4. Tokenize and filter tokens (length >= 2, not in STOP_WORDS)
    raw_tokens = cleaned_phrase.split()
    tokens = [
        t for t in raw_tokens
        if len(t) >= 2 and t.lower() not in STOP_WORDS
    ]

    return cleaned_phrase, tokens


def search_catalog_service(
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
    request=None,
) -> Dict[str, Any]:
    """
    Searches active products in the catalog with optimized ORM queries and multi-layered relevance ranking.

    Args:
        query (str, optional): Search term across title, description, category name, and brand name.
        category (str/int, optional): Category ID or category name (case-insensitive).
        limit (int): Maximum number of items to return (clamped between 1 and 50).
        request (HttpRequest, optional): Request object to build absolute URLs.

    Returns:
        dict: Structured response with total_found, effective limit, and items list.
    """
    # Sanitize and clamp limit
    effective_limit = max(1, min(int(limit), 50))

    # Base queryset optimized with select_related to prevent N+1 queries
    queryset = Item.objects.filter(is_active=True).select_related('category', 'brand', 'supplier')

    is_ranked = False

    # Apply search query filter with intelligent multi-layer matching
    if query is not None:
        raw_cleaned = str(query).strip()
        if raw_cleaned:
            cleaned_phrase, tokens = normalize_and_tokenize_query(raw_cleaned)
            if cleaned_phrase:
                filter_conditions = []
                score_expressions = []

                # Layer A: Exact phrase matching on whole cleaned phrase (highest priority)
                exact_phrase_q = (
                    Q(title__icontains=cleaned_phrase) |
                    Q(brand__name__icontains=cleaned_phrase) |
                    Q(category__name__icontains=cleaned_phrase) |
                    Q(description__icontains=cleaned_phrase)
                )
                filter_conditions.append(exact_phrase_q)
                score_expressions.extend([
                    Case(When(title__icontains=cleaned_phrase, then=Value(100)), default=Value(0), output_field=IntegerField()),
                    Case(When(brand__name__icontains=cleaned_phrase, then=Value(80)), default=Value(0), output_field=IntegerField()),
                    Case(When(category__name__icontains=cleaned_phrase, then=Value(60)), default=Value(0), output_field=IntegerField()),
                    Case(When(description__icontains=cleaned_phrase, then=Value(40)), default=Value(0), output_field=IntegerField()),
                ])

                # If tokens form a keyword phrase, also score exact matches for keyword phrase
                keywords_phrase = " ".join(tokens)
                if keywords_phrase and keywords_phrase.lower() != cleaned_phrase.lower():
                    score_expressions.extend([
                        Case(When(title__icontains=keywords_phrase, then=Value(90)), default=Value(0), output_field=IntegerField()),
                        Case(When(brand__name__icontains=keywords_phrase, then=Value(70)), default=Value(0), output_field=IntegerField()),
                        Case(When(category__name__icontains=keywords_phrase, then=Value(50)), default=Value(0), output_field=IntegerField()),
                        Case(When(description__icontains=keywords_phrase, then=Value(30)), default=Value(0), output_field=IntegerField()),
                    ])

                # Layer B & C: Individual token matching with OR combination
                if tokens:
                    token_or_q = Q()
                    for token in tokens:
                        token_q = (
                            Q(title__icontains=token) |
                            Q(brand__name__icontains=token) |
                            Q(category__name__icontains=token) |
                            Q(description__icontains=token)
                        )
                        token_or_q |= token_q
                        score_expressions.extend([
                            Case(When(title__icontains=token, then=Value(10)), default=Value(0), output_field=IntegerField()),
                            Case(When(brand__name__icontains=token, then=Value(8)), default=Value(0), output_field=IntegerField()),
                            Case(When(category__name__icontains=token, then=Value(5)), default=Value(0), output_field=IntegerField()),
                            Case(When(description__icontains=token, then=Value(2)), default=Value(0), output_field=IntegerField()),
                        ])
                    filter_conditions.append(token_or_q)

                # Combine all search filter conditions with OR
                combined_q = reduce(lambda a, b: a | b, filter_conditions)
                queryset = queryset.filter(combined_q)

                # Calculate total relevance rank and order results
                relevance_rank = reduce(lambda a, b: a + b, score_expressions)
                queryset = queryset.annotate(search_rank=relevance_rank).order_by('-search_rank', '-id')
                is_ranked = True
            else:
                # Query contained only punctuation symbols or delimiters with no words
                queryset = queryset.filter(title__icontains=raw_cleaned)

    # Layer D: Apply category filter if provided
    if category is not None:
        cat_str = str(category).strip()
        if cat_str:
            if cat_str.isdigit():
                queryset = queryset.filter(category_id=int(cat_str))
            else:
                queryset = queryset.filter(category__name__iexact=cat_str)

    if not is_ranked:
        # Order by ID descending for consistent pagination / latest products first if no query ranking
        queryset = queryset.order_by('-id')

    queryset = queryset.distinct()

    total_found = queryset.count()
    items_page = queryset[:effective_limit]

    items_data: List[Dict[str, Any]] = []
    for item in items_page:
        # Build item URL (absolute if request is present)
        rel_url = item.get_absolute_url()
        item_url = request.build_absolute_uri(rel_url) if request else rel_url

        # Build image URL if image exists
        image_url = None
        if item.img:
            image_url = request.build_absolute_uri(item.img.url) if request else item.img.url

        items_data.append({
            'id': item.id,
            'title': item.title,
            'description': item.description or '',
            'price': float(item.price),
            'stock': item.stock,
            'is_available': bool(item.stock > 0 and item.is_active),
            'category': item.category.name if item.category else None,
            'brand': item.brand.name if item.brand else None,
            'url': item_url,
            'image_url': image_url,
        })

    return {
        'total_found': total_found,
        'limit': effective_limit,
        'items': items_data,
    }
