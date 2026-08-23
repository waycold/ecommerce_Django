"""
apps/catalog/services.py

Business logic and service layer for product catalog operations.
Includes English/Spanish synonym-to-category mapping (e.g., "dime un libro barato" -> "Books"),
multi-token fuzzy search, tiered relevance ranking, and inventory/reviews analytics.
"""

import re
from functools import reduce
from typing import Optional, Dict, Any, List, Tuple
from django.db.models import Q, Case, When, Value, IntegerField
from apps.catalog.models import Item

from apps.catalog.inventory_service import get_inventory_health_service
from apps.catalog.reviews_service import get_reviews_summary_service
from apps.catalog.semantic_search_service import semantic_catalog_search_service


# Extended conversational stop words in Spanish and English
STOP_WORDS = {
    'hola', 'me', 'interesa', 'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'en', 'para', 'por', 'con', 'sobre', 'producto', 'precio',
    'the', 'a', 'an', 'of', 'in', 'for', 'with', 'product', 'price',
    'dime', 'decime', 'muestra', 'muestrame', 'muéstrame', 'busca', 'busco', 'buscar',
    'quiero', 'necesito', 'recomienda', 'recomiendame', 'recomiéndame', 'show', 'find',
    'tell', 'recommend', 'give', 'algun', 'alguno', 'alguna', 'algunos', 'algunas',
    'any', 'some', 'please', 'favor',
}

# Price intent keywords for budget / premium sorting
PRICE_BUDGET_KEYWORDS = {
    'barato', 'baratos', 'barata', 'baratas', 'economico', 'económico',
    'economica', 'económica', 'economicos', 'económicos', 'economicas', 'económicas',
    'oferta', 'ofertas', 'descuento', 'descuentos', 'cheap', 'cheapest',
    'budget', 'affordable', 'lowcost', 'inexpensive',
}

PRICE_PREMIUM_KEYWORDS = {
    'caro', 'caros', 'cara', 'caras', 'premium', 'lujo', 'luxury',
    'expensive', 'high-end', 'highend', 'top',
}

# Comprehensive English/Spanish Category Synonym Dictionary mapping to Amazon dataset categories
CATEGORY_SYNONYMS_ES_EN = {
    # Books / Lectura / Literatura -> Amazon Category: "Books"
    'libro': 'Books',
    'libros': 'Books',
    'book': 'Books',
    'books': 'Books',
    'novela': 'Books',
    'novelas': 'Books',
    'novel': 'Books',
    'novels': 'Books',
    'lectura': 'Books',
    'literatura': 'Books',
    'texto': 'Books',
    'textos': 'Books',
    'cuento': 'Books',
    'cuentos': 'Books',
    'comic': 'Books',
    'comics': 'Books',
    'manga': 'Books',
    'tomo': 'Books',
    'tomos': 'Books',
    'ebook': 'Kindle_Store',
    'ebooks': 'Kindle_Store',
    'kindle': 'Kindle_Store',

    # Electronics / Computación / Smartphones -> "Electronics" / "Cell_Phones_and_Accessories"
    'computadora': 'Electronics',
    'computadoras': 'Electronics',
    'computacion': 'Electronics',
    'computación': 'Electronics',
    'computer': 'Electronics',
    'computers': 'Electronics',
    'laptop': 'Electronics',
    'laptops': 'Electronics',
    'notebook': 'Electronics',
    'notebooks': 'Electronics',
    'pc': 'Electronics',
    'monitor': 'Electronics',
    'monitores': 'Electronics',
    'teclado': 'Electronics',
    'teclados': 'Electronics',
    'keyboard': 'Electronics',
    'keyboards': 'Electronics',
    'mouse': 'Electronics',
    'raton': 'Electronics',
    'ratón': 'Electronics',
    'auricular': 'Electronics',
    'auriculares': 'Electronics',
    'headphone': 'Electronics',
    'headphones': 'Electronics',
    'audio': 'Electronics',
    'tablet': 'Electronics',
    'tablets': 'Electronics',
    'electronica': 'Electronics',
    'electrónica': 'Electronics',
    'electronics': 'Electronics',
    'celular': 'Cell_Phones_and_Accessories',
    'celulares': 'Cell_Phones_and_Accessories',
    'telefono': 'Cell_Phones_and_Accessories',
    'teléfono': 'Cell_Phones_and_Accessories',
    'telefonos': 'Cell_Phones_and_Accessories',
    'teléfonos': 'Cell_Phones_and_Accessories',
    'smartphone': 'Cell_Phones_and_Accessories',
    'smartphones': 'Cell_Phones_and_Accessories',
    'phone': 'Cell_Phones_and_Accessories',
    'mobile': 'Cell_Phones_and_Accessories',

    # Video Games / Consolas / Gaming -> "Video_Games"
    'juego': 'Video_Games',
    'juegos': 'Video_Games',
    'videojuego': 'Video_Games',
    'videojuegos': 'Video_Games',
    'videogame': 'Video_Games',
    'videogames': 'Video_Games',
    'gaming': 'Video_Games',
    'gamer': 'Video_Games',
    'consola': 'Video_Games',
    'consolas': 'Video_Games',
    'playstation': 'Video_Games',
    'ps5': 'Video_Games',
    'ps4': 'Video_Games',
    'xbox': 'Video_Games',
    'nintendo': 'Video_Games',

    # Clothing / Apparel / Shoes / Fashion -> "Clothing_Shoes_and_Jewelry" / "Amazon_Fashion"
    'ropa': 'Clothing_Shoes_and_Jewelry',
    'clothing': 'Clothing_Shoes_and_Jewelry',
    'clothes': 'Clothing_Shoes_and_Jewelry',
    'prenda': 'Clothing_Shoes_and_Jewelry',
    'prendas': 'Clothing_Shoes_and_Jewelry',
    'vestido': 'Clothing_Shoes_and_Jewelry',
    'vestidos': 'Clothing_Shoes_and_Jewelry',
    'dress': 'Clothing_Shoes_and_Jewelry',
    'camisa': 'Clothing_Shoes_and_Jewelry',
    'camisas': 'Clothing_Shoes_and_Jewelry',
    'shirt': 'Clothing_Shoes_and_Jewelry',
    'remera': 'Clothing_Shoes_and_Jewelry',
    'remeras': 'Clothing_Shoes_and_Jewelry',
    'tshirt': 'Clothing_Shoes_and_Jewelry',
    'pantalon': 'Clothing_Shoes_and_Jewelry',
    'pantalón': 'Clothing_Shoes_and_Jewelry',
    'pantalones': 'Clothing_Shoes_and_Jewelry',
    'pants': 'Clothing_Shoes_and_Jewelry',
    'zapato': 'Clothing_Shoes_and_Jewelry',
    'zapatos': 'Clothing_Shoes_and_Jewelry',
    'shoes': 'Clothing_Shoes_and_Jewelry',
    'calzado': 'Clothing_Shoes_and_Jewelry',
    'zapatilla': 'Clothing_Shoes_and_Jewelry',
    'zapatillas': 'Clothing_Shoes_and_Jewelry',
    'sneaker': 'Clothing_Shoes_and_Jewelry',
    'sneakers': 'Clothing_Shoes_and_Jewelry',
    'moda': 'Amazon_Fashion',
    'fashion': 'Amazon_Fashion',

    # Beauty & Personal Care -> "Beauty_and_Personal_Care" / "All_Beauty"
    'belleza': 'Beauty_and_Personal_Care',
    'beauty': 'Beauty_and_Personal_Care',
    'maquillaje': 'Beauty_and_Personal_Care',
    'makeup': 'Beauty_and_Personal_Care',
    'cosmetico': 'Beauty_and_Personal_Care',
    'cosmeticos': 'Beauty_and_Personal_Care',
    'cosméticos': 'Beauty_and_Personal_Care',
    'skincare': 'Beauty_and_Personal_Care',
    'crema': 'Beauty_and_Personal_Care',
    'cremas': 'Beauty_and_Personal_Care',
    'perfume': 'Beauty_and_Personal_Care',
    'perfumes': 'Beauty_and_Personal_Care',
    'shampoo': 'Beauty_and_Personal_Care',

    # Home & Kitchen / Appliances -> "Home_and_Kitchen" / "Appliances"
    'hogar': 'Home_and_Kitchen',
    'home': 'Home_and_Kitchen',
    'casa': 'Home_and_Kitchen',
    'cocina': 'Home_and_Kitchen',
    'kitchen': 'Home_and_Kitchen',
    'mueble': 'Home_and_Kitchen',
    'muebles': 'Home_and_Kitchen',
    'furniture': 'Home_and_Kitchen',
    'cama': 'Home_and_Kitchen',
    'sabana': 'Home_and_Kitchen',
    'sábanas': 'Home_and_Kitchen',
    'sarten': 'Home_and_Kitchen',
    'sartén': 'Home_and_Kitchen',
    'olla': 'Home_and_Kitchen',
    'ollas': 'Home_and_Kitchen',
    'electrodomestico': 'Appliances',
    'electrodoméstico': 'Appliances',
    'electrodomesticos': 'Appliances',
    'electrodomésticos': 'Appliances',
    'appliances': 'Appliances',
    'appliance': 'Appliances',

    # Sports & Outdoors -> "Sports_and_Outdoors"
    'deporte': 'Sports_and_Outdoors',
    'deportes': 'Sports_and_Outdoors',
    'sport': 'Sports_and_Outdoors',
    'sports': 'Sports_and_Outdoors',
    'fitness': 'Sports_and_Outdoors',
    'gym': 'Sports_and_Outdoors',
    'gimnasio': 'Sports_and_Outdoors',
    'entrenamiento': 'Sports_and_Outdoors',
    'pelota': 'Sports_and_Outdoors',
    'pesa': 'Sports_and_Outdoors',
    'pesas': 'Sports_and_Outdoors',
    'bicicleta': 'Sports_and_Outdoors',
    'running': 'Sports_and_Outdoors',

    # Toys & Games -> "Toys_and_Games"
    'juguete': 'Toys_and_Games',
    'juguetes': 'Toys_and_Games',
    'toy': 'Toys_and_Games',
    'toys': 'Toys_and_Games',
    'muñeca': 'Toys_and_Games',
    'muñeco': 'Toys_and_Games',
    'lego': 'Toys_and_Games',

    # Pet Supplies -> "Pet_Supplies"
    'mascota': 'Pet_Supplies',
    'mascotas': 'Pet_Supplies',
    'pet': 'Pet_Supplies',
    'pets': 'Pet_Supplies',
    'perro': 'Pet_Supplies',
    'perros': 'Pet_Supplies',
    'gato': 'Pet_Supplies',
    'gatos': 'Pet_Supplies',

    # Music & Instruments -> "Digital_Music" / "CDs_and_Vinyl" / "Musical_Instruments"
    'musica': 'Digital_Music',
    'música': 'Digital_Music',
    'music': 'Digital_Music',
    'cancion': 'Digital_Music',
    'cd': 'CDs_and_Vinyl',
    'vinilo': 'CDs_and_Vinyl',
    'vinyl': 'CDs_and_Vinyl',
    'instrumento': 'Musical_Instruments',
    'instrumentos': 'Musical_Instruments',
    'guitarra': 'Musical_Instruments',

    # Tools & Automotive -> "Tools_and_Home_Improvement" / "Automotive"
    'herramienta': 'Tools_and_Home_Improvement',
    'herramientas': 'Tools_and_Home_Improvement',
    'tool': 'Tools_and_Home_Improvement',
    'tools': 'Tools_and_Home_Improvement',
    'taladro': 'Tools_and_Home_Improvement',
    'destornillador': 'Tools_and_Home_Improvement',
    'martillo': 'Tools_and_Home_Improvement',
    'auto': 'Automotive',
    'autos': 'Automotive',
    'coche': 'Automotive',
    'coches': 'Automotive',
    'car': 'Automotive',
    'cars': 'Automotive',
    'automotriz': 'Automotive',
    'automotive': 'Automotive',
    'moto': 'Automotive',
    'motos': 'Automotive',
}


def normalize_and_tokenize_query(query: Optional[str]) -> Tuple[str, List[str], Optional[str], Optional[str]]:
    """
    Cleans and normalizes query text:
    1. Removes price prefixes like 'Precio:', 'Price:'.
    2. Strips punctuation symbols: () $ , " ' : ; ! ?
    3. Tokenizes into meaningful keywords (length >= 2, non-stop words).
    4. Detects price sorting intent ('asc' for cheap/budget, 'desc' for premium/luxury).
    5. Maps English/Spanish synonyms to standard Amazon Category names (e.g. 'libro' -> 'Books').

    Returns:
        tuple: (cleaned_phrase, list_of_tokens, detected_category_name, price_intent)
    """
    if not query:
        return "", [], None, None

    raw = str(query)

    # 1. Clean prefixes like "Precio:", "Price:" (case-insensitive)
    raw = re.sub(r'(?i)\b(precio|price)\s*:\s*', ' ', raw)

    # 2. Remove punctuation symbols () $ , " ' and common delimiters
    raw = re.sub(r'[\(\)\$,"\'\:\;\!\?]', ' ', raw)

    # 3. Normalize whitespace
    cleaned_phrase = re.sub(r'\s+', ' ', raw).strip()
    if not cleaned_phrase:
        return "", [], None, None

    # 4. Tokenize words
    raw_tokens = cleaned_phrase.split()
    tokens: List[str] = []
    detected_category: Optional[str] = None
    price_intent: Optional[str] = None

    for raw_token in raw_tokens:
        clean_token = raw_token.lower()

        # Check price modifiers
        if clean_token in PRICE_BUDGET_KEYWORDS:
            price_intent = 'asc'
            continue
        elif clean_token in PRICE_PREMIUM_KEYWORDS:
            price_intent = 'desc'
            continue

        # Check category synonym mapping
        if not detected_category and clean_token in CATEGORY_SYNONYMS_ES_EN:
            detected_category = CATEGORY_SYNONYMS_ES_EN[clean_token]

        # Filter stop words and single-character words
        if len(clean_token) >= 2 and clean_token not in STOP_WORDS:
            tokens.append(raw_token)

    return cleaned_phrase, tokens, detected_category, price_intent


def search_catalog_service(
    query: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 10,
    request=None,
) -> Dict[str, Any]:
    """
    Searches active products in the catalog with optimized ORM queries, English/Spanish
    synonym category mapping, budget/premium sorting, and multi-layered relevance ranking.

    Args:
        query (str, optional): Search term across title, description, category name, and brand name.
        category (str/int, optional): Explicit category ID or category name (case-insensitive).
        limit (int): Maximum number of items to return (clamped between 1 and 50).
        request (HttpRequest, optional): Request object to build absolute URLs.

    Returns:
        dict: Structured response with total_found, effective limit, and items list.
    """
    effective_limit = max(1, min(int(limit), 50))

    # Base queryset optimized with select_related to prevent N+1 queries
    queryset = Item.objects.filter(is_active=True).select_related('category', 'brand', 'supplier')

    is_ranked = False
    price_intent: Optional[str] = None
    mapped_category: Optional[str] = None

    # Apply search query filter with intelligent multi-layer matching
    if query is not None:
        raw_cleaned = str(query).strip()
        if raw_cleaned:
            cleaned_phrase, tokens, mapped_category, price_intent = normalize_and_tokenize_query(raw_cleaned)

            filter_conditions = []
            score_expressions = []

            # Layer A: Exact phrase matching on whole cleaned phrase (highest priority)
            if cleaned_phrase:
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

            # Layer B: Mapped Category from English/Spanish synonyms (e.g. "libro" -> "Books")
            if mapped_category and not category:
                cat_normalized = mapped_category.replace('_', ' ')
                cat_synonym_q = (
                    Q(category__name__iexact=mapped_category) |
                    Q(category__name__icontains=mapped_category) |
                    Q(category__name__icontains=cat_normalized)
                )
                filter_conditions.append(cat_synonym_q)
                score_expressions.extend([
                    Case(When(category__name__iexact=mapped_category, then=Value(95)), default=Value(0), output_field=IntegerField()),
                    Case(When(category__name__icontains=mapped_category, then=Value(85)), default=Value(0), output_field=IntegerField()),
                    Case(When(category__name__icontains=cat_normalized, then=Value(85)), default=Value(0), output_field=IntegerField()),
                ])

            # Layer C: Keyword phrase matching
            keywords_phrase = " ".join(tokens)
            if keywords_phrase and keywords_phrase.lower() != cleaned_phrase.lower():
                score_expressions.extend([
                    Case(When(title__icontains=keywords_phrase, then=Value(90)), default=Value(0), output_field=IntegerField()),
                    Case(When(brand__name__icontains=keywords_phrase, then=Value(70)), default=Value(0), output_field=IntegerField()),
                    Case(When(category__name__icontains=keywords_phrase, then=Value(50)), default=Value(0), output_field=IntegerField()),
                    Case(When(description__icontains=keywords_phrase, then=Value(30)), default=Value(0), output_field=IntegerField()),
                ])

            # Layer D: Individual token matching with OR combination
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
            if filter_conditions:
                combined_q = reduce(lambda a, b: a | b, filter_conditions)
                queryset = queryset.filter(combined_q)

                # Calculate total relevance rank and order results
                if score_expressions:
                    relevance_rank = reduce(lambda a, b: a + b, score_expressions)
                    queryset = queryset.annotate(search_rank=relevance_rank)
                    
                    if price_intent == 'asc':
                        queryset = queryset.order_by('-search_rank', 'price', '-id')
                    elif price_intent == 'desc':
                        queryset = queryset.order_by('-search_rank', '-price', '-id')
                    else:
                        queryset = queryset.order_by('-search_rank', '-id')
                    
                    is_ranked = True
            else:
                queryset = queryset.filter(title__icontains=raw_cleaned)

    # Layer E: Apply explicit category filter if provided
    if category is not None:
        cat_str = str(category).strip()
        if cat_str:
            if cat_str.isdigit():
                queryset = queryset.filter(category_id=int(cat_str))
            else:
                queryset = queryset.filter(category__name__iexact=cat_str)

    if not is_ranked:
        if price_intent == 'asc':
            queryset = queryset.order_by('price', '-id')
        elif price_intent == 'desc':
            queryset = queryset.order_by('-price', '-id')
        else:
            queryset = queryset.order_by('-id')

    queryset = queryset.distinct()

    total_found = queryset.count()
    items_page = queryset[:effective_limit]

    items_data: List[Dict[str, Any]] = []
    for item in items_page:
        rel_url = item.get_absolute_url()
        item_url = request.build_absolute_uri(rel_url) if request else rel_url

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
        'mapped_category': mapped_category,
        'price_intent': price_intent,
    }
