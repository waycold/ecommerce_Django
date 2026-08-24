"""
tests/test_chatbot_emulation_postman.py

Comprehensive Chatbot Emulation Test Suite mirroring the Postman Collection:
'AI Database Query Endpoints - Chatbot Emulation Test' (UID: 57530649-14b1a007-c236-4b9b-aa86-914003398e7b)

Validates the 11 user/executive natural language and database query scenarios:
1. Query 1: Sales & Margins by Category Q1-Q2 2025 (GET /api/v1/internal/analytics/query/?date_from=2025-01-01&date_to=2025-06-30&group_by=category&metrics=revenue,orders,margin)
2. Query 2: Inventory Health & Stockout Runout Rate (GET /api/v1/internal/inventory/health/)
3. Query 3: Margins & Profitability Ranking (GET /api/v1/internal/analytics/margins/?dimension=category&order_by=margin_desc)
4. Query 4: Funnel & Cart Metrics (GET /api/v1/internal/analytics/funnel/?period=last_30_days)
5. Query 5: Reviews Sentiment & Negative Feedback (GET /api/v1/internal/catalog/reviews-summary/?max_rating=2)
6. Query 6: Customer Insights RFM & LTV (GET /api/v1/internal/customers/insights/)
7. Query 7: Natural Language Search with Synonyms 'dime un libro barato' (GET /api/v1/internal/catalog/search/?q=dime+un+libro+barato)
8. Query 8: Semantic Intent Search 'atuendo casual comodo para verano' (POST /api/v1/internal/catalog/semantic-search/)
9. Query 9: Safe Read-Only SQL Sandbox (POST /api/v1/internal/query/raw-read/)
10. Query 10: Security Defense Injection Block (POST /api/v1/internal/query/raw-read/ with DROP TABLE)
11. Query 11: Security Defense Missing Secret Header (GET /api/v1/internal/inventory/health/ without secret)
"""

import json
import time
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from typing import Dict, Any, Tuple

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.utils import timezone

from apps.catalog.models import Category, Brand, Supplier, Item, Comments
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentMethod, Profile


@pytest.fixture
def postman_emulation_dataset(db):
    """
    Creates a rich, multi-category, historical dataset covering all 11 Postman test scenarios:
    - Categories: 'Books', 'Clothing_Shoes_and_Jewelry', 'Electronics', 'Digital_Music', 'Amazon_Fashion'
    - Items: Books, Apparel, Laptops, Headphones with varying stock, prices, costs
    - Historical Orders in Q1 2025, Q2 2025, and recent 30 days
    - Reviews with negative (1-2 stars) and positive (4-5 stars) ratings
    - Customer profiles in multiple countries (US, Spain, France)
    """
    now = timezone.now()

    # 1. Categories
    cat_books = Category.objects.create(name="Books")
    cat_clothing = Category.objects.create(name="Clothing_Shoes_and_Jewelry")
    cat_electronics = Category.objects.create(name="Electronics")
    cat_music = Category.objects.create(name="Digital_Music")
    cat_fashion = Category.objects.create(name="Amazon_Fashion")

    # 2. Brands
    brand_penguin = Brand.objects.create(name="Penguin Classics")
    brand_nike = Brand.objects.create(name="Nike")
    brand_asus = Brand.objects.create(name="Asus ROG")
    brand_sony = Brand.objects.create(name="Sony")

    # 3. Suppliers
    sup_usa = Supplier.objects.create(name="US Express Supply", country="United States")
    sup_eu = Supplier.objects.create(name="EuroLogistics", country="Spain")

    # 4. Items
    # Books (for Query 7)
    item_book_1 = Item.objects.create(
        title="Python Data Science Handbook",
        description="Essential tools for working with data and machine learning",
        price=Decimal("25.00"),
        cost=Decimal("12.00"),
        stock=50,
        minimum_stock=10,
        category=cat_books,
        brand=brand_penguin,
        supplier=sup_usa,
        is_active=True,
    )
    item_book_2 = Item.objects.create(
        title="Django for Professionals",
        description="Production web development with Python and Django",
        price=Decimal("39.99"),
        cost=Decimal("18.00"),
        stock=30,
        minimum_stock=5,
        category=cat_books,
        brand=brand_penguin,
        supplier=sup_usa,
        is_active=True,
    )

    # Apparel / Summer Fashion (for Query 8)
    item_shirt = Item.objects.create(
        title="Casual Summer Linen Shirt",
        description="Lightweight comfortable cotton linen shirt for hot summer days",
        price=Decimal("45.00"),
        cost=Decimal("18.00"),
        stock=40,
        minimum_stock=10,
        category=cat_clothing,
        brand=brand_nike,
        supplier=sup_eu,
        is_active=True,
    )
    item_shoes = Item.objects.create(
        title="Breathable Casual Summer Sneakers",
        description="Comfortable walking shoes with cushioned sole",
        price=Decimal("75.00"),
        cost=Decimal("35.00"),
        stock=20,
        minimum_stock=5,
        category=cat_fashion,
        brand=brand_nike,
        supplier=sup_eu,
        is_active=True,
    )

    # High-end Laptop & Headphones (for Inventory, Margins, Reviews)
    item_laptop = Item.objects.create(
        title="ROG Zephyrus G14 Gaming Laptop",
        description="Ultra-slim high performance gaming laptop with Ryzen 9",
        price=Decimal("1800.00"),
        cost=Decimal("1100.00"),
        stock=8,
        minimum_stock=5,
        category=cat_electronics,
        brand=brand_asus,
        supplier=sup_usa,
        is_active=True,
    )
    # Low stock item (Critical)
    item_headphones = Item.objects.create(
        title="Sony Noise Cancelling Earbuds",
        description="True wireless earbuds with active noise cancellation",
        price=Decimal("199.99"),
        cost=Decimal("110.00"),
        stock=1,
        minimum_stock=5,
        category=cat_music,
        brand=brand_sony,
        supplier=sup_usa,
        is_active=True,
    )
    # Out of stock item
    item_mouse = Item.objects.create(
        title="ROG Wireless Gaming Mouse",
        description="Lightweight wireless gaming mouse",
        price=Decimal("89.99"),
        cost=Decimal("35.00"),
        stock=0,
        minimum_stock=10,
        category=cat_electronics,
        brand=brand_asus,
        supplier=sup_usa,
        is_active=True,
    )

    # 5. Users & Profiles
    u1 = User.objects.create_user(username="elena_analyst", email="elena@company.com", password="password123")
    Profile.objects.create(user=u1, country="United States", city="Seattle", province="Washington")

    u2 = User.objects.create_user(username="marco_buyer", email="marco@buyer.es", password="password123")
    Profile.objects.create(user=u2, country="Spain", city="Barcelona", province="Catalunya")

    u3 = User.objects.create_user(username="chloe_paris", email="chloe@france.fr", password="password123")
    Profile.objects.create(user=u3, country="France", city="Paris", province="Ile-de-France")

    # 6. Orders
    # Historical Q1 2025 Order (2025-02-15)
    dt_q1 = datetime(2025, 2, 15, 12, 0, 0, tzinfo=dt_timezone.utc)
    ord_q1 = Order.objects.create(
        user=u1,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        discount_code="PROMO10",
        discount=Decimal("180.00"),
        shipping_cost=Decimal("0.00"),
        total=Decimal("1620.00"),
        ordered_date=dt_q1,
        start_date=dt_q1,
    )
    oi_q1 = OrderItem.objects.create(
        order=ord_q1,
        item=item_laptop,
        quantity=1,
        unit_price=Decimal("1800.00"),
        unit_cost=Decimal("1100.00"),
        subtotal=Decimal("1800.00"),
    )
    ord_q1.items.add(oi_q1)

    # Historical Q2 2025 Order (2025-05-10)
    dt_q2 = datetime(2025, 5, 10, 14, 30, 0, tzinfo=dt_timezone.utc)
    ord_q2 = Order.objects.create(
        user=u2,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        shipping_cost=Decimal("25.00"),
        total=Decimal("114.99"),
        ordered_date=dt_q2,
        start_date=dt_q2,
    )
    oi_q2_1 = OrderItem.objects.create(
        order=ord_q2,
        item=item_book_1,
        quantity=2,
        unit_price=Decimal("25.00"),
        unit_cost=Decimal("12.00"),
        subtotal=Decimal("50.00"),
    )
    oi_q2_2 = OrderItem.objects.create(
        order=ord_q2,
        item=item_book_2,
        quantity=1,
        unit_price=Decimal("39.99"),
        unit_cost=Decimal("18.00"),
        subtotal=Decimal("39.99"),
    )
    ord_q2.items.add(oi_q2_1, oi_q2_2)

    # Recent Order (Within 30 days)
    ord_recent = Order.objects.create(
        user=u3,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.TRANSFER,
        shipping_cost=Decimal("25.00"),
        total=Decimal("224.99"),
        ordered_date=now - timedelta(days=5),
        start_date=now - timedelta(days=5),
    )
    oi_rec = OrderItem.objects.create(
        order=ord_recent,
        item=item_headphones,
        quantity=1,
        unit_price=Decimal("199.99"),
        unit_cost=Decimal("110.00"),
        subtotal=Decimal("199.99"),
    )
    ord_recent.items.add(oi_rec)

    # Abandoned Cart Order (Within 30 days, status=PENDING)
    ord_abandoned = Order.objects.create(
        user=u1,
        status=OrderStatus.PENDING,
        total=Decimal("1800.00"),
        start_date=now - timedelta(days=2),
    )
    oi_ab = OrderItem.objects.create(
        order=ord_abandoned,
        item=item_laptop,
        quantity=1,
        unit_price=Decimal("1800.00"),
        unit_cost=Decimal("1100.00"),
        subtotal=Decimal("1800.00"),
    )
    ord_abandoned.items.add(oi_ab)

    # 7. Reviews & Ratings
    Comments.objects.create(
        user=u1,
        item=item_laptop,
        rating=5,
        body="Super fast, exceptional display and build!",
        likes=10,
    )
    Comments.objects.create(
        user=u2,
        item=item_book_1,
        rating=5,
        body="Clear explanations and great code examples.",
        likes=4,
    )
    # Negative review for headphones (Rating: 1)
    Comments.objects.create(
        user=u3,
        item=item_headphones,
        rating=1,
        body="Battery drains quickly and connection drops randomly.",
        likes=2,
    )
    # Negative review for shirt (Rating: 2)
    Comments.objects.create(
        user=u2,
        item=item_shirt,
        rating=2,
        body="Fabric feels too rough and shrinks after first wash.",
        likes=1,
    )

    return {
        'items': {
            'book_1': item_book_1,
            'book_2': item_book_2,
            'shirt': item_shirt,
            'shoes': item_shoes,
            'laptop': item_laptop,
            'headphones': item_headphones,
            'mouse': item_mouse,
        }
    }


# ==============================================================================
# 11 POSTMAN CHATBOT EMULATION TESTS
# ==============================================================================

@pytest.mark.django_db
class TestChatbotEmulationPostmanCollection:
    """
    Executes the 11 exact Postman collection scenarios, asserting response schemas,
    status codes, values, and measuring endpoint latency.
    """

    AUTH_HEADER = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

    def _execute_and_time(self, client, method: str, path: str, data: Any = None, headers: Dict = None) -> Tuple[Any, float]:
        """Helper to send HTTP request and record exact latency in milliseconds."""
        req_headers = headers if headers is not None else self.AUTH_HEADER
        start = time.perf_counter()
        if method == 'GET':
            res = client.get(path, **req_headers)
        elif method == 'POST':
            if isinstance(data, (dict, list)):
                res = client.post(path, data=json.dumps(data), content_type='application/json', **req_headers)
            else:
                res = client.post(path, data=data, **req_headers)
        else:
            raise ValueError(f"Unsupported test method: {method}")
        latency_ms = (time.perf_counter() - start) * 1000.0
        return res, round(latency_ms, 2)

    # --------------------------------------------------------------------------
    # Scenario 1: Sales & Margins by Category (Q1-Q2 2025)
    # --------------------------------------------------------------------------
    def test_query_1_sales_margins_q1_q2_2025(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/analytics/query/?date_from=2025-01-01&date_to=2025-06-30&group_by=category&metrics=revenue,orders,margin'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 2500  # Initial query cold start + schema load (< 2500ms)
        data = response.json()

        # Metadata validation
        assert data['query_metadata']['group_by'] == 'category'
        assert data['query_metadata']['date_from'] == '2025-01-01'
        assert data['query_metadata']['date_to'] == '2025-06-30'

        # Summary validation
        summary = data['summary']
        assert summary['total_revenue'] > 0
        assert summary['total_orders'] == 2  # Q1 order + Q2 order
        assert summary['total_gross_profit'] > 0
        assert summary['avg_order_value'] > 0

        # Categories data array
        categories = [row['dimension'] for row in data['data']]
        assert any("Books" in c or "Electronics" in c for c in categories)

    # --------------------------------------------------------------------------
    # Scenario 2: Inventory Health & Stockout Runout Rate
    # --------------------------------------------------------------------------
    def test_query_2_inventory_health(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/inventory/health/'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        # Metrics structure
        metrics = data['metrics']
        assert metrics['total_active_skus'] == 7
        assert metrics['out_of_stock_count'] == 1  # Gaming Mouse has stock=0
        assert metrics['low_stock_count'] == 1     # Earbuds has stock=1 <= minimum_stock=5
        assert metrics['healthy_stock_count'] == 5
        assert metrics['stockout_rate_pct'] == round((1 / 7) * 100, 2)

        # Inventory valuation
        valuation = data['inventory_valuation']
        assert valuation['total_cost_value'] > 0
        assert valuation['total_retail_value'] > valuation['total_cost_value']
        assert valuation['projected_profit_potential'] > 0

        # Critical items list
        critical_items = data['critical_items']
        assert len(critical_items) >= 2
        oos_item = next(i for i in critical_items if i['stock'] == 0)
        assert oos_item['stock_status'] == 'OUT_OF_STOCK'
        assert oos_item['estimated_days_to_stockout'] == 0.0

    # --------------------------------------------------------------------------
    # Scenario 3: Category Profitability & Margin Ranking
    # --------------------------------------------------------------------------
    def test_query_3_margins_ranking(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/analytics/margins/?dimension=category&order_by=margin_desc'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        assert data['dimension'] == 'category'
        assert data['order_by'] == 'margin_desc'
        assert data['overall_margin']['total_revenue'] > 0
        assert data['overall_margin']['overall_margin_pct'] > 0

        results = data['results']
        assert len(results) >= 2
        # Verify descending order of gross_margin_pct
        for idx in range(len(results) - 1):
            assert results[idx]['gross_margin_pct'] >= results[idx + 1]['gross_margin_pct']

    # --------------------------------------------------------------------------
    # Scenario 4: Cart Abandonment Funnel & Promotions ROI
    # --------------------------------------------------------------------------
    def test_query_4_funnel_and_promotions(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/analytics/funnel/?period=last_30_days'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        assert data['period'] == 'last_30_days'
        funnel = data['funnel_metrics']
        assert funnel['total_orders'] >= 2  # 1 Recent paid + 1 Abandoned pending
        assert funnel['completed_orders'] >= 1
        assert funnel['pending_orders'] >= 1
        assert funnel['cart_abandonment_rate_pct'] > 0
        assert funnel['conversion_rate_pct'] > 0

        # Abandoned products ranking
        abandoned = data['abandoned_products_ranking']
        assert len(abandoned) >= 1
        assert "ROG Zephyrus" in abandoned[0]['title']

    # --------------------------------------------------------------------------
    # Scenario 5: Customer Reviews & Negative Feedback
    # --------------------------------------------------------------------------
    def test_query_5_reviews_negative_feedback(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/catalog/reviews-summary/?max_rating=2'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        # All returned reviews must have rating <= 2
        reviews = data['reviews']
        assert len(reviews) == 2  # 1 star earbuds + 2 star shirt
        assert all(r['rating'] <= 2 for r in reviews)

        # Recent negative feedback array
        negatives = data['recent_negative_feedback']
        assert len(negatives) == 2
        assert any("Battery drains" in n['body'] for n in negatives)
        assert any("Fabric feels too rough" in n['body'] for n in negatives)

    # --------------------------------------------------------------------------
    # Scenario 6: CRM RFM Segmentation & Customer Lifetime Value
    # --------------------------------------------------------------------------
    def test_query_6_customer_insights_rfm_ltv(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/customers/insights/'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        summary = data['summary']
        assert summary['total_customers'] == 3
        assert summary['avg_customer_ltv'] > 0
        assert 'segment_counts' in summary

        # Geographic distribution
        geo = data['geographic_distribution']
        countries = [c['country'] for c in geo['by_country']]
        assert "United States" in countries
        assert "Spain" in countries
        assert "France" in countries

        # Top customers ranked by spend
        top = data['top_customers']
        assert len(top) == 3
        assert top[0]['total_spend'] >= top[1]['total_spend'] >= top[2]['total_spend']
        assert top[0]['username'] == 'elena_analyst'
        assert top[0]['total_spend'] == 1620.0

    # --------------------------------------------------------------------------
    # Scenario 7: Natural Language Search with Synonyms (Dime un libro barato)
    # --------------------------------------------------------------------------
    def test_query_7_nl_search_synonyms(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/catalog/search/?q=dime+un+libro+barato'
        response, latency_ms = self._execute_and_time(client, 'GET', path)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        # Key expectations: mapped_category == 'Books', price_intent == 'asc'
        assert data['mapped_category'] == 'Books'
        assert data['price_intent'] == 'asc'
        assert data['total_found'] >= 2

        items = data['items']
        assert len(items) >= 2
        # Verify cheaper book comes first ($25.00 before $39.99)
        assert items[0]['price'] <= items[1]['price']
        assert items[0]['title'] == "Python Data Science Handbook"
        assert items[1]['title'] == "Django for Professionals"

    # --------------------------------------------------------------------------
    # Scenario 8: Semantic Intent Search (Atuendo casual comodo para verano)
    # --------------------------------------------------------------------------
    def test_query_8_semantic_intent_search(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/catalog/semantic-search/'
        payload = {"query_text": "atuendo casual comodo para verano", "limit": 10}
        response, latency_ms = self._execute_and_time(client, 'POST', path, data=payload)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        assert "fashion_clothing" in data['intents_detected']
        assert data['total_found'] >= 2

        items = data['items']
        titles = [i['title'] for i in items]
        assert any("Casual Summer Linen Shirt" in t for t in titles)
        assert any("Summer Sneakers" in t for t in titles)
        assert items[0]['relevance_score'] > 0

    # --------------------------------------------------------------------------
    # Scenario 9: Safe Read-Only SQL Sandbox (Orders by Status)
    # --------------------------------------------------------------------------
    def test_query_9_safe_sql_sandbox(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/query/raw-read/'
        payload = {"query": "SELECT status, count(*) as count FROM product_order GROUP BY status"}
        response, latency_ms = self._execute_and_time(client, 'POST', path, data=payload)

        assert response.status_code == 200
        assert latency_ms < 500
        data = response.json()

        assert data['status'] == 'success'
        assert 'status' in data['columns']
        assert 'count' in data['columns']
        assert data['row_count'] >= 2  # PAID and PENDING
        assert data['row_count'] <= 50  # Enforced maximum 50 rows limit
        assert data['execution_time_ms'] >= 0.0

    # --------------------------------------------------------------------------
    # Scenario 10: Security Defense: Reject DDL / Mutation Injections
    # --------------------------------------------------------------------------
    def test_query_10_security_reject_mutation(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/query/raw-read/'
        payload = {"query": "DROP TABLE product_order;"}
        response, latency_ms = self._execute_and_time(client, 'POST', path, data=payload)

        assert response.status_code == 400
        assert latency_ms < 500
        data = response.json()

        assert data['error'] in ('Forbidden SQL Keyword', 'Bad Request')
        assert 'Only SELECT' in data['detail'] or 'DROP' in data['detail'] or 'Disallowed' in data['detail']

    # --------------------------------------------------------------------------
    # Scenario 11: Security Defense: Reject Requests Without Internal Secret
    # --------------------------------------------------------------------------
    def test_query_11_security_reject_missing_secret(self, client, postman_emulation_dataset):
        path = '/api/v1/internal/inventory/health/'
        # Send request with NO headers (missing X-Internal-Secret)
        response, latency_ms = self._execute_and_time(client, 'GET', path, headers={})

        assert response.status_code == 401
        assert latency_ms < 500
        data = response.json()

        assert data.get('error') == 'Unauthorized'
        assert 'Invalid or missing X-Internal-Secret' in data.get('detail', '')

    # --------------------------------------------------------------------------
    # End-to-End Sequential Emulation Pipeline
    # --------------------------------------------------------------------------
    def test_full_chatbot_emulation_sequential_pipeline(self, client, postman_emulation_dataset):
        """
        Executes all 11 chatbot queries in continuous sequence, validating
        performance, status codes, and zero drift across the complete collection.
        """
        scenarios = [
            ("Q1: Sales & Margins", 'GET', '/api/v1/internal/analytics/query/?date_from=2025-01-01&date_to=2025-06-30&group_by=category&metrics=revenue,orders,margin', None, self.AUTH_HEADER, 200),
            ("Q2: Inventory Health", 'GET', '/api/v1/internal/inventory/health/', None, self.AUTH_HEADER, 200),
            ("Q3: Margins Ranking", 'GET', '/api/v1/internal/analytics/margins/?dimension=category&order_by=margin_desc', None, self.AUTH_HEADER, 200),
            ("Q4: Funnel & Cart", 'GET', '/api/v1/internal/analytics/funnel/?period=last_30_days', None, self.AUTH_HEADER, 200),
            ("Q5: Reviews Negative", 'GET', '/api/v1/internal/catalog/reviews-summary/?max_rating=2', None, self.AUTH_HEADER, 200),
            ("Q6: Customer Insights", 'GET', '/api/v1/internal/customers/insights/', None, self.AUTH_HEADER, 200),
            ("Q7: NL Search Synonyms", 'GET', '/api/v1/internal/catalog/search/?q=dime+un+libro+barato', None, self.AUTH_HEADER, 200),
            ("Q8: Semantic Search", 'POST', '/api/v1/internal/catalog/semantic-search/', {"query_text": "atuendo casual comodo para verano", "limit": 10}, self.AUTH_HEADER, 200),
            ("Q9: Safe SQL Sandbox", 'POST', '/api/v1/internal/query/raw-read/', {"query": "SELECT status, count(*) as count FROM product_order GROUP BY status"}, self.AUTH_HEADER, 200),
            ("Q10: Injection Block", 'POST', '/api/v1/internal/query/raw-read/', {"query": "DROP TABLE product_order;"}, self.AUTH_HEADER, 400),
            ("Q11: Missing Secret", 'GET', '/api/v1/internal/inventory/health/', None, {}, 401),
        ]

        results_report = []
        for name, method, path, data, headers, expected_status in scenarios:
            res, lat = self._execute_and_time(client, method, path, data, headers)
            assert res.status_code == expected_status, f"Scenario '{name}' failed with HTTP {res.status_code}"
            results_report.append({
                'scenario': name,
                'status_code': res.status_code,
                'latency_ms': lat,
            })

        # All 11 scenarios successfully executed in under 200ms avg latency
        avg_latency = sum(r['latency_ms'] for r in results_report) / len(results_report)
        assert avg_latency < 250.0


# ==============================================================================
# DECEMBER 2025 AUDITED DATASET & TOP 5 CATEGORIES TEST SUITE
# ==============================================================================

@pytest.fixture
def december_2025_categories_dataset(db):
    """
    Creates a calibrated multi-category dataset covering December 2025 (2025-12-01 to 2025-12-31)
    and surrounding baseline periods to rigorously test temporal filtering and Top 5 category rankings.

    Expected December 2025 Revenue Ranking:
    1. Industrial_and_Scientific: $95,000.00
    2. Cell_Phones_and_Accessories: $78,500.00
    3. Electronics: $54,200.00
    4. Home_and_Kitchen: $36,800.00
    5. Automotive: $22,100.00
    6. Beauty_and_Personal_Care: $9,400.00 (Excluded by limit=5)
    7. Sports_and_Outdoors: $4,500.00 (Excluded by limit=5)

    Out-of-period noise:
    - November 2025: $150,000.00 in Beauty_and_Personal_Care (must be excluded)
    - January 2026: $200,000.00 in Sports_and_Outdoors (must be excluded)
    - December 2025 (PENDING): $500,000.00 in Sports_and_Outdoors (must be excluded from paid queries)
    """
    user = User.objects.create_user(username="dec_buyer", email="dec@example.com", password="password123")
    supplier = Supplier.objects.create(name="DecSupplyGlobal", country="United States")
    brand = Brand.objects.create(name="UniversalBrand")

    categories_config = [
        ("Industrial_and_Scientific", Decimal("95000.00"), Decimal("50000.00"), datetime(2025, 12, 5, 10, 0, 0, tzinfo=dt_timezone.utc)),
        ("Cell_Phones_and_Accessories", Decimal("78500.00"), Decimal("45000.00"), datetime(2025, 12, 12, 14, 0, 0, tzinfo=dt_timezone.utc)),
        ("Electronics", Decimal("54200.00"), Decimal("32000.00"), datetime(2025, 12, 18, 11, 30, 0, tzinfo=dt_timezone.utc)),
        ("Home_and_Kitchen", Decimal("36800.00"), Decimal("22000.00"), datetime(2025, 12, 22, 16, 15, 0, tzinfo=dt_timezone.utc)),
        ("Automotive", Decimal("22100.00"), Decimal("14000.00"), datetime(2025, 12, 28, 9, 45, 0, tzinfo=dt_timezone.utc)),
        ("Beauty_and_Personal_Care", Decimal("9400.00"), Decimal("5000.00"), datetime(2025, 12, 29, 12, 0, 0, tzinfo=dt_timezone.utc)),
        ("Sports_and_Outdoors", Decimal("4500.00"), Decimal("2500.00"), datetime(2025, 12, 30, 15, 0, 0, tzinfo=dt_timezone.utc)),
    ]

    created_items = {}
    for cat_name, rev, cost, order_dt in categories_config:
        cat_obj = Category.objects.create(name=cat_name)
        item_obj = Item.objects.create(
            title=f"Sample Item for {cat_name}",
            description=f"Product description for {cat_name}",
            price=rev,
            cost=cost,
            stock=100,
            minimum_stock=10,
            category=cat_obj,
            brand=brand,
            supplier=supplier,
            is_active=True,
        )
        created_items[cat_name] = item_obj

        # Create Paid Order in December 2025
        order = Order.objects.create(
            user=user,
            status=OrderStatus.PAID,
            payment_method=PaymentMethod.CREDIT_CARD,
            shipping_cost=Decimal("0.00"),
            total=rev,
            ordered_date=order_dt,
            start_date=order_dt,
        )
        oi = OrderItem.objects.create(
            order=order,
            item=item_obj,
            quantity=1,
            unit_price=rev,
            unit_cost=cost,
            subtotal=rev,
        )
        order.items.add(oi)

    # 1. Out-of-period order: November 2025 (2025-11-15) -> Beauty ($150,000)
    dt_nov = datetime(2025, 11, 15, 12, 0, 0, tzinfo=dt_timezone.utc)
    ord_nov = Order.objects.create(
        user=user,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        shipping_cost=Decimal("0.00"),
        total=Decimal("150000.00"),
        ordered_date=dt_nov,
        start_date=dt_nov,
    )
    oi_nov = OrderItem.objects.create(
        order=ord_nov,
        item=created_items["Beauty_and_Personal_Care"],
        quantity=1,
        unit_price=Decimal("150000.00"),
        unit_cost=Decimal("80000.00"),
        subtotal=Decimal("150000.00"),
    )
    ord_nov.items.add(oi_nov)

    # 2. Out-of-period order: January 2026 (2026-01-10) -> Sports ($200,000)
    dt_jan = datetime(2026, 1, 10, 12, 0, 0, tzinfo=dt_timezone.utc)
    ord_jan = Order.objects.create(
        user=user,
        status=OrderStatus.PAID,
        payment_method=PaymentMethod.CREDIT_CARD,
        shipping_cost=Decimal("0.00"),
        total=Decimal("200000.00"),
        ordered_date=dt_jan,
        start_date=dt_jan,
    )
    oi_jan = OrderItem.objects.create(
        order=ord_jan,
        item=created_items["Sports_and_Outdoors"],
        quantity=1,
        unit_price=Decimal("200000.00"),
        unit_cost=Decimal("100000.00"),
        subtotal=Decimal("200000.00"),
    )
    ord_jan.items.add(oi_jan)

    # 3. In-period but unpaid order: December 2025 (2025-12-20, PENDING) -> Sports ($500,000)
    dt_pending = datetime(2025, 12, 20, 12, 0, 0, tzinfo=dt_timezone.utc)
    ord_pending = Order.objects.create(
        user=user,
        status=OrderStatus.PENDING,
        total=Decimal("500000.00"),
        ordered_date=dt_pending,
        start_date=dt_pending,
    )
    oi_pending = OrderItem.objects.create(
        order=ord_pending,
        item=created_items["Sports_and_Outdoors"],
        quantity=1,
        unit_price=Decimal("500000.00"),
        unit_cost=Decimal("250000.00"),
        subtotal=Decimal("500000.00"),
    )
    ord_pending.items.add(oi_pending)

    return created_items


@pytest.mark.django_db
class TestDecember2025CategoryRanking:
    """
    Validates audited December 2025 Top 5 category rankings across dynamic sales query
    and margin calculation internal endpoints and services.
    """
    AUTH_HEADER = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

    EXPECTED_TOP_5_CATEGORIES = [
        'Industrial_and_Scientific',
        'Cell_Phones_and_Accessories',
        'Electronics',
        'Home_and_Kitchen',
        'Automotive',
    ]

    EXPECTED_REVENUES = [
        95000.0,
        78500.0,
        54200.0,
        36800.0,
        22100.0,
    ]

    def test_dynamic_sales_query_endpoint_december_2025_top_5_categories(self, client, december_2025_categories_dataset):
        """
        Tests GET /api/v1/internal/analytics/query/?date_from=2025-12-01&date_to=2025-12-31&group_by=category&limit=5
        Verifies:
        1. HTTP 200 response with correct query metadata.
        2. Exactly 5 records returned.
        3. Correct descending order matching the audited December 2025 ranking.
        4. Excludes out-of-period orders (Nov 2025, Jan 2026) and unpaid orders (Pending).
        """
        url = '/api/v1/internal/analytics/query/?date_from=2025-12-01&date_to=2025-12-31&group_by=category&limit=5'
        response = client.get(url, **self.AUTH_HEADER)

        assert response.status_code == 200
        data = response.json()

        # Metadata validation
        assert data['query_metadata']['date_from'] == '2025-12-01'
        assert data['query_metadata']['date_to'] == '2025-12-31'
        assert data['query_metadata']['group_by'] == 'category'
        assert data['query_metadata']['limit'] == 5

        # Data rows validation
        rows = data['data']
        assert len(rows) == 5, f"Expected 5 records, got {len(rows)}"

        returned_categories = [r['dimension'] for r in rows]
        assert returned_categories == self.EXPECTED_TOP_5_CATEGORIES, (
            f"Category ranking mismatch! Got {returned_categories}, expected {self.EXPECTED_TOP_5_CATEGORIES}"
        )

        returned_revenues = [r['revenue'] for r in rows]
        assert returned_revenues == self.EXPECTED_REVENUES, (
            f"Revenue mismatch! Got {returned_revenues}, expected {self.EXPECTED_REVENUES}"
        )

        # Summary check (Total December 2025 paid revenue across all 7 categories = 300,500.0)
        assert data['summary']['total_revenue'] == 300500.0
        assert data['summary']['total_orders'] == 7

        # Ensure excluded categories are not in the top 5
        assert 'Beauty_and_Personal_Care' not in returned_categories
        assert 'Sports_and_Outdoors' not in returned_categories

    def test_margins_endpoint_december_2025_top_5_categories(self, client, december_2025_categories_dataset):
        """
        Tests GET /api/v1/internal/analytics/margins/?dimension=category&date_from=2025-12-01&date_to=2025-12-31&order_by=revenue_desc&limit=5
        Verifies:
        1. HTTP 200 response with correct date_from and date_to.
        2. Exactly 5 category margin records in expected revenue ranking order.
        """
        url = '/api/v1/internal/analytics/margins/?dimension=category&date_from=2025-12-01&date_to=2025-12-31&order_by=revenue_desc&limit=5'
        response = client.get(url, **self.AUTH_HEADER)

        assert response.status_code == 200
        data = response.json()

        assert data['dimension'] == 'category'
        assert data['order_by'] == 'revenue_desc'
        assert data['date_from'] == '2025-12-01'
        assert data['date_to'] == '2025-12-31'
        assert data['limit'] == 5

        results = data['results']
        assert len(results) == 5

        returned_categories = [r['category'] for r in results]
        assert returned_categories == self.EXPECTED_TOP_5_CATEGORIES

        returned_revenues = [r['revenue'] for r in results]
        assert returned_revenues == self.EXPECTED_REVENUES

    def test_services_direct_december_2025_filtering(self, december_2025_categories_dataset):
        """
        Direct service layer test validating dynamic_sales_query_service and calculate_margins_service.
        """
        from apps.analytics.services import dynamic_sales_query_service, calculate_margins_service

        query_res = dynamic_sales_query_service(
            date_from='2025-12-01',
            date_to='2025-12-31',
            group_by='category',
            limit=5,
        )
        assert [r['dimension'] for r in query_res['data']] == self.EXPECTED_TOP_5_CATEGORIES

        margin_res = calculate_margins_service(
            dimension='category',
            order_by='revenue_desc',
            date_from='2025-12-01',
            date_to='2025-12-31',
            limit=5,
        )
        assert [r['category'] for r in margin_res['results']] == self.EXPECTED_TOP_5_CATEGORIES

