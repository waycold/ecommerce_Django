"""
apps/catalog/semantic_search_service.py

Semantic and conceptual catalog search engine.
Expands search intent using synonym taxonomies, shopping goals,
and multi-tier relevance scoring across catalog metadata.
"""

import re
from functools import reduce
from typing import Optional, Dict, Any, List
from django.db.models import Q, Case, When, Value, IntegerField

from apps.catalog.models import Item


# Semantic Intent Taxonomy and Synonym Mappings
INTENT_TAXONOMY = {
    'gaming': {
        'keywords': ['gamer', 'gaming', 'juego', 'juegos', 'rog', 'rgb', 'strix', 'play', 'consola', 'switch', 'videojuego', 'fps'],
        'synonyms': ['laptop', 'mouse', 'keyboard', 'monitor', 'headset', 'mechanical', 'gpu', 'sensor'],
        'categories': ['Electronics', 'Video_Games', 'Cell_Phones_and_Accessories']
    },
    'programming': {
        'keywords': ['programar', 'programacion', 'desarrollo', 'developer', 'coding', 'software', 'codigo', 'engineer'],
        'synonyms': ['laptop', 'processor', 'core', 'intel', 'ram', 'desktop', 'keyboard', 'monitor', 'powerhouse'],
        'categories': ['Electronics', 'Software', 'Computers', 'Office_Products']
    },
    'audio_music': {
        'keywords': ['audio', 'sonido', 'musica', 'escuchar', 'sound', 'music', 'cancion', 'podcast'],
        'synonyms': ['auriculares', 'headphone', 'headset', 'earphone', 'speaker', 'parlante', 'mic', 'microphone'],
        'categories': ['Digital_Music', 'CDs_and_Vinyl', 'Musical_Instruments', 'Electronics']
    },
    'office_work': {
        'keywords': ['oficina', 'trabajo', 'homeoffice', 'escritorio', 'office', 'ergonomico', 'productividad'],
        'synonyms': ['keyboard', 'mouse', 'chair', 'desk', 'laptop', 'paper', 'printer', 'cable', 'dock'],
        'categories': ['Office_Products', 'Electronics', 'Home_and_Kitchen']
    },
    'fashion_clothing': {
        'keywords': ['ropa', 'moda', 'vestir', 'outfit', 'camisa', 'pantalon', 'zapato', 'zapatilla', 'casual', 'verano', 'invierno', 'fashion'],
        'synonyms': ['shirt', 'pants', 'shoes', 'dress', 't-shirt', 'jacket', 'cotton', 'sneakers'],
        'categories': ['Clothing_Shoes_and_Jewelry', 'Amazon_Fashion']
    },
    'beauty_care': {
        'keywords': ['belleza', 'cuidado', 'piel', 'facial', 'crema', 'beauty', 'skin', 'skincare', 'maquillaje'],
        'synonyms': ['lotion', 'cream', 'serum', 'mask', 'oil', 'shampoo', 'hair', 'soap'],
        'categories': ['All_Beauty', 'Beauty_and_Personal_Care', 'Health_and_Personal_Care']
    },
    'home_kitchen': {
        'keywords': ['hogar', 'casa', 'cocina', 'electrodomestico', 'comida', 'home', 'kitchen', 'cook', 'bano'],
        'synonyms': ['blender', 'pan', 'knife', 'pot', 'appliance', 'tool', 'organizer', 'lamp'],
        'categories': ['Home_and_Kitchen', 'Appliances', 'Grocery_and_Gourmet_Food']
    },
    'budget_cheap': {
        'keywords': ['barato', 'economico', 'oferta', 'descuento', 'cheap', 'budget', 'accessible', 'lowcost'],
        'synonyms': ['deal', 'basic', 'entry', 'affordable'],
        'categories': []
    },
    'premium_high_end': {
        'keywords': ['premium', 'gama alta', 'lujo', 'pro', 'flagship', 'exclusive', 'highend', 'top'],
        'synonyms': ['ultra', 'max', 'flagship', 'powerhouse', 'titanium', 'deluxe'],
        'categories': []
    }
}


def semantic_catalog_search_service(
    query_text: str,
    limit: int = 10,
    request=None,
) -> Dict[str, Any]:
    """
    Performs conceptual intent-expanded search across active items.

    Args:
        query_text (str): Free-form user or LLM search query.
        limit (int): Max results to return (clamped between 1 and 50).
        request (HttpRequest, optional): Request object to build absolute URLs.

    Returns:
        dict: {
            query,
            cleaned_query,
            intents_detected,
            expanded_keywords,
            total_found,
            items: List[...]
        }
    """
    effective_limit = max(1, min(int(limit), 50))
    raw_query = str(query_text or "").strip()
    if not raw_query:
        return {
            'query': '',
            'cleaned_query': '',
            'intents_detected': [],
            'expanded_keywords': [],
            'total_found': 0,
            'items': [],
        }

    # Clean raw string
    cleaned_query = re.sub(r'[\(\)\$,"\'\:\;\!\?]', ' ', raw_query)
    cleaned_query = re.sub(r'\s+', ' ', cleaned_query).strip()
    tokens = [t.lower() for t in cleaned_query.split() if len(t) >= 2]

    # Detect intents and collect expansion synonyms
    intents_detected: List[str] = []
    expanded_synonyms: set = set()
    target_categories: set = set()

    for intent_name, intent_data in INTENT_TAXONOMY.items():
        matched = False
        for kw in intent_data['keywords']:
            if any(kw in token or token in kw for token in tokens) or kw in cleaned_query.lower():
                matched = True
                break
        if matched:
            intents_detected.append(intent_name)
            for syn in intent_data['synonyms']:
                expanded_synonyms.add(syn.lower())
            for cat in intent_data['categories']:
                target_categories.add(cat)

    # Base active products queryset
    queryset = Item.objects.filter(is_active=True).select_related('category', 'brand', 'supplier')

    score_exprs = []
    filter_q = Q(title__icontains=cleaned_query) | Q(brand__name__icontains=cleaned_query) | Q(category__name__icontains=cleaned_query)

    # 1. Exact cleaned phrase match
    score_exprs.append(
        Case(When(title__icontains=cleaned_query, then=Value(100)), default=Value(0), output_field=IntegerField())
    )

    # 2. Query Tokens (High priority: +40 for title match)
    for token in tokens:
        score_exprs.append(
            Case(When(title__icontains=token, then=Value(40)), default=Value(0), output_field=IntegerField())
        )
        score_exprs.append(
            Case(When(description__icontains=token, then=Value(20)), default=Value(0), output_field=IntegerField())
        )
        filter_q |= Q(title__icontains=token) | Q(description__icontains=token)

    # 3. Expanded Synonyms (+15 for title match)
    for syn in list(expanded_synonyms)[:8]:
        score_exprs.append(
            Case(When(title__icontains=syn, then=Value(15)), default=Value(0), output_field=IntegerField())
        )
        filter_q |= Q(title__icontains=syn) | Q(description__icontains=syn)

    # 4. Target categories (+20)
    for cat in list(target_categories)[:4]:
        score_exprs.append(
            Case(When(category__name__iexact=cat, then=Value(20)), default=Value(0), output_field=IntegerField())
        )
        filter_q |= Q(category__name__iexact=cat)

    relevance_rank = reduce(lambda a, b: a + b, score_exprs)

    queryset = (
        queryset.filter(filter_q)
        .annotate(relevance_score=relevance_rank)
        .order_by('-relevance_score', '-id')
        .distinct()
    )

    total_found = queryset.count()
    items_page = queryset[:effective_limit]

    items_data: List[Dict[str, Any]] = []
    for item in items_page:
        rel_url = item.get_absolute_url()
        item_url = request.build_absolute_uri(rel_url) if request else rel_url
        image_url = request.build_absolute_uri(item.img.url) if (request and item.img) else (item.img.url if item.img else None)

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
            'relevance_score': getattr(item, 'relevance_score', 0),
        })

    all_expanded_keywords = sorted(list(set(tokens) | expanded_synonyms))

    return {
        'query': raw_query,
        'cleaned_query': cleaned_query,
        'intents_detected': intents_detected,
        'expanded_keywords': all_expanded_keywords,
        'total_found': total_found,
        'items': items_data,
    }
