"""
product/services.py

Business logic and service layer for product catalog operations.
Decoupled from HTTP controllers to facilitate reusability, testing, and clean architecture.
"""

from typing import Optional, Dict, Any, List
from django.db.models import Q
from product.models import Item


def search_catalog_service(
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
    request=None,
) -> Dict[str, Any]:
    """
    Searches active products in the catalog with optimized ORM queries.

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

    # Apply search query filter if provided
    if query:
        cleaned_query = str(query).strip()
        if cleaned_query:
            queryset = queryset.filter(
                Q(title__icontains=cleaned_query) |
                Q(description__icontains=cleaned_query) |
                Q(category__name__icontains=cleaned_query) |
                Q(brand__name__icontains=cleaned_query)
            ).distinct()

    # Apply category filter if provided
    if category is not None:
        cat_str = str(category).strip()
        if cat_str:
            if cat_str.isdigit():
                queryset = queryset.filter(category_id=int(cat_str))
            else:
                queryset = queryset.filter(category__name__iexact=cat_str)

    # Order by ID descending for consistent pagination / latest products first
    queryset = queryset.order_by('-id')

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
