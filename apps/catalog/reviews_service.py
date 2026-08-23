"""
apps/catalog/reviews_service.py

Product customer sentiment, rating distributions, praise & negative feedback analytics.
"""

from typing import Optional, Dict, Any, List
from django.db.models import Avg, Count, Q
from apps.catalog.models import Comments, Item


def get_reviews_summary_service(
    item_id: Optional[int] = None,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    min_rating: Optional[int] = None,
    max_rating: Optional[int] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Computes aggregated rating distributions, average customer score, and recent sentiment feedback.

    Args:
        item_id (int, optional): Filter reviews for specific product ID.
        category (str|int, optional): Category ID or category name.
        brand (str|int, optional): Brand ID or brand name.
        min_rating (int, optional): Minimum rating stars (1-5).
        max_rating (int, optional): Maximum rating stars (1-5).
        limit (int): Max latest reviews to return (clamped between 1 and 100).

    Returns:
        dict: {
            summary: {total_reviews, average_rating, rating_distribution},
            recent_negative_feedback: List[...],
            recent_positive_feedback: List[...],
            reviews: List[...]
        }
    """
    effective_limit = max(1, min(int(limit), 100))

    comments_qs = Comments.objects.select_related('user', 'item', 'item__category', 'item__brand')

    # Apply filters
    if item_id is not None:
        try:
            comments_qs = comments_qs.filter(item_id=int(item_id))
        except (ValueError, TypeError):
            pass

    if category is not None:
        cat_str = str(category).strip()
        if cat_str.isdigit():
            comments_qs = comments_qs.filter(item__category_id=int(cat_str))
        else:
            comments_qs = comments_qs.filter(item__category__name__iexact=cat_str)

    if brand is not None:
        brand_str = str(brand).strip()
        if brand_str.isdigit():
            comments_qs = comments_qs.filter(item__brand_id=int(brand_str))
        else:
            comments_qs = comments_qs.filter(item__brand__name__iexact=brand_str)

    if min_rating is not None:
        try:
            comments_qs = comments_qs.filter(rating__gte=int(min_rating))
        except (ValueError, TypeError):
            pass

    if max_rating is not None:
        try:
            comments_qs = comments_qs.filter(rating__lte=int(max_rating))
        except (ValueError, TypeError):
            pass

    total_reviews = comments_qs.count()
    avg_rating_agg = comments_qs.aggregate(avg=Avg('rating'))
    average_rating = float(round(avg_rating_agg['avg'] or 0.0, 2))

    # Star distribution
    star_dist_qs = comments_qs.values('rating').annotate(count=Count('id'))
    dist_map = {row['rating']: row['count'] for row in star_dist_qs}
    rating_distribution = {
        '5_stars': dist_map.get(5, 0),
        '4_stars': dist_map.get(4, 0),
        '3_stars': dist_map.get(3, 0),
        '2_stars': dist_map.get(2, 0),
        '1_star': dist_map.get(1, 0),
    }

    # Negative feedback (ratings 1 and 2)
    negative_qs = (
        comments_qs.filter(rating__lte=2)
        .order_by('-date_added')[:5]
    )
    recent_negatives: List[Dict[str, Any]] = []
    for c in negative_qs:
        recent_negatives.append({
            'comment_id': c.id,
            'item_id': c.item_id,
            'item_title': c.item.title if c.item else 'Unknown',
            'username': c.user.username if c.user else 'Anonymous',
            'rating': c.rating,
            'body': c.body,
            'date_added': c.date_added.strftime('%Y-%m-%d %H:%M') if c.date_added else None,
            'likes': c.likes,
        })

    # Positive feedback (ratings 4 and 5)
    positive_qs = (
        comments_qs.filter(rating__gte=4)
        .order_by('-date_added')[:5]
    )
    recent_positives: List[Dict[str, Any]] = []
    for c in positive_qs:
        recent_positives.append({
            'comment_id': c.id,
            'item_id': c.item_id,
            'item_title': c.item.title if c.item else 'Unknown',
            'username': c.user.username if c.user else 'Anonymous',
            'rating': c.rating,
            'body': c.body,
            'date_added': c.date_added.strftime('%Y-%m-%d %H:%M') if c.date_added else None,
            'likes': c.likes,
        })

    # Latest reviews list
    reviews_list: List[Dict[str, Any]] = []
    for c in comments_qs.order_by('-date_added')[:effective_limit]:
        reviews_list.append({
            'comment_id': c.id,
            'item_id': c.item_id,
            'item_title': c.item.title if c.item else 'Unknown',
            'category': c.item.category.name if (c.item and c.item.category) else 'Uncategorized',
            'brand': c.item.brand.name if (c.item and c.item.brand) else 'Generic',
            'username': c.user.username if c.user else 'Anonymous',
            'rating': c.rating,
            'body': c.body,
            'date_added': c.date_added.strftime('%Y-%m-%d %H:%M') if c.date_added else None,
            'likes': c.likes,
        })

    return {
        'filter_applied': {
            'item_id': item_id,
            'category': category,
            'brand': brand,
            'min_rating': min_rating,
            'max_rating': max_rating,
            'limit': effective_limit,
        },
        'summary': {
            'total_reviews': total_reviews,
            'average_rating': average_rating,
            'rating_distribution': rating_distribution,
        },
        'recent_negative_feedback': recent_negatives,
        'recent_positive_feedback': recent_positives,
        'reviews': reviews_list,
    }
