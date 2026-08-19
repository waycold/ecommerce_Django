"""
analytics/services.py

Services and Data Processing Layer (Data Engineering, Business Logic & Data Simulator).
Includes KPI calculations, Excel ETL pipeline, Forecast & Trends analytics engine,
and the synthetic dataset generator engine with real-time status tracking and memory chunking.
"""

import io
import os
import gc
import json
import math
import random
import time
import threading
from datetime import datetime, timedelta
from openpyxl import Workbook

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Sum, Count, F, Q, DecimalField, Case, When, Value, ExpressionWrapper, Avg
from django.db.models.functions import Round, TruncMonth
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth.models import User
from faker import Faker

from product.models import (
    OrderItem, Order, Comments, Item, Category, Brand, Supplier, Profile,
    OrderStatus, PaymentMethod
)
from analytics.data_ingestion import get_amazon_data

CATEGORIES_LIST = [
    "All_Beauty", "Amazon_Fashion", "Appliances", "Arts_Crafts_and_Sewing", "Automotive",
    "Baby_Products", "Beauty_and_Personal_Care", "Books", "CDs_and_Vinyl", "Cell_Phones_and_Accessories",
    "Clothing_Shoes_and_Jewelry", "Digital_Music", "Electronics", "Gift_Cards", "Grocery_and_Gourmet_Food",
    "Handmade_Products", "Health_and_Household", "Health_and_Personal_Care", "Home_and_Kitchen", "Industrial_and_Scientific",
    "Kindle_Store", "Magazine_Subscriptions", "Movies_and_TV", "Musical_Instruments", "Office_Products",
    "Patio_Lawn_and_Garden", "Pet_Supplies", "Software", "Sports_and_Outdoors", "Subscription_Boxes",
    "Tools_and_Home_Improvement", "Toys_and_Games", "Video_Games", "Unknown"
]

# Thread-safe dataset generation status tracker
GENERATION_LOCK = threading.Lock()
GENERATION_STATUS = {
    "is_running": False,
    "progress_pct": 0,
    "current_step": "Idle",
    "logs": [],
    "error": None,
    "completed_at": None,
    "stats": {}
}


def is_production_environment() -> bool:
    """
    Detects if the application is running in Production / Cloud (e.g. Render).
    Checks RENDER environment variable, PRODUCTION variable, or settings.DEBUG.
    """
    return bool(os.environ.get('RENDER') or os.environ.get('PRODUCTION') or not settings.DEBUG)


def get_dashboard_kpis() -> dict:
    """
    Calculates key performance indicators (KPIs) in real-time for the Managerial Dashboard.
    """
    now = timezone.now()
    current_year = now.year
    current_month = now.month

    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    
    monthly_revenue_agg = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).aggregate(
        total_revenue=Sum('total')
    )
    monthly_revenue = monthly_revenue_agg['total_revenue'] or 0.0

    monthly_orders_count = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).count()

    avg_order_value = float(monthly_revenue) / float(monthly_orders_count) if monthly_orders_count > 0 else 0.0

    active_customers_count = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).values('user').distinct().count()

    abandoned_carts_count = Order.objects.filter(
        status=OrderStatus.PENDING
    ).count()

    top_products_qs = OrderItem.objects.filter(
        order__status__in=paid_statuses
    ).values(
        'item__id',
        'item__title',
        'item__category__name',
        'item__price'
    ).annotate(
        total_units_sold=Sum('quantity'),
        total_revenue_generated=Sum('subtotal')
    ).order_by('-total_units_sold')[:8]

    top_products = list(top_products_qs)

    return {
        'current_month_name': now.strftime('%B %Y'),
        'monthly_revenue': float(monthly_revenue),
        'monthly_orders_count': monthly_orders_count,
        'avg_order_value': round(avg_order_value, 2),
        'active_customers_count': active_customers_count,
        'abandoned_carts_count': abandoned_carts_count,
        'top_products': top_products,
        'top_product_star': top_products[0] if top_products else None,
    }


def export_sales_to_excel() -> HttpResponse:
    """
    ETL pipeline using openpyxl to export sales records to Excel format.
    """
    cost_total_expr = ExpressionWrapper(
        F('unit_cost') * F('quantity'),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    
    net_profit_expr = ExpressionWrapper(
        F('subtotal') - (F('unit_cost') * F('quantity')),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    
    margin_expr = Case(
        When(subtotal__gt=0, then=Round((net_profit_expr / F('subtotal')) * 100, 2)),
        default=Value(0.0),
        output_field=DecimalField(max_digits=5, decimal_places=2)
    )

    sales_queryset = OrderItem.objects.annotate(
        total_cost=cost_total_expr,
        net_profit=net_profit_expr,
        margin=margin_expr
    ).values_list(
        'order__id',
        'order__ordered_date',
        'order__status',
        'order__payment_method',
        'order__user__username',
        'item__title',
        'item__category__name',
        'quantity',
        'unit_price',
        'unit_cost',
        'subtotal',
        'net_profit',
        'margin'
    )

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title='Sales_Report_ETL')
    
    headers = [
        'Order ID', 'Order Date', 'Order Status', 'Payment Method', 'Customer',
        'Product', 'Category', 'Quantity', 'Historical Unit Price',
        'Historical Unit Cost', 'Subtotal ($)', 'Net Profit ($)', 'Margin (%)'
    ]
    ws.append(headers)

    for row in sales_queryset.iterator(chunk_size=2000):
        row_list = list(row)
        if row_list[1]:
            row_list[1] = row_list[1].replace(tzinfo=None)
        if row_list[4] is None:
            row_list[4] = 'Guest/Anonymous'
        if row_list[6] is None:
            row_list[6] = 'Uncategorized'
        ws.append(row_list)
        
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    
    file_name = f"sales_report_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response


# ==============================================================================
# FORECAST & TRENDS ANALYTICS SERVICE
# ==============================================================================

def get_forecast_data() -> dict:
    """
    Computes time-series sales trend, linear demand forecasting for the next 3 months,
    category distribution, and cross-category market basket co-occurrences.
    """
    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    
    monthly_sales = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__isnull=False
    ).annotate(
        month=TruncMonth('ordered_date')
    ).values('month').annotate(
        revenue=Sum('total'),
        orders_count=Count('id')
    ).order_by('month')

    months_labels = []
    historical_revenue = []
    historical_orders = []

    for entry in monthly_sales:
        if entry['month']:
            months_labels.append(entry['month'].strftime('%b %Y'))
            historical_revenue.append(round(float(entry['revenue'] or 0.0), 2))
            historical_orders.append(entry['orders_count'])

    forecast_months = []
    forecast_revenue = []
    forecast_upper = []
    forecast_lower = []

    n = len(historical_revenue)
    if n > 1:
        x = list(range(n))
        y = historical_revenue
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x[i] ** 2 for i in range(n))

        slope = (n * sum_xy - sum_x * sum_y) / max(1.0, (n * sum_x2 - sum_x ** 2))
        intercept = (sum_y - slope * sum_x) / n

        residuals = [y[i] - (slope * x[i] + intercept) for i in range(n)]
        std_err = math.sqrt(sum(r ** 2 for r in residuals) / max(1, n - 2)) if n > 2 else sum(y) * 0.05

        last_date = monthly_sales[n - 1]['month'] if n > 0 and monthly_sales[n - 1]['month'] else timezone.now()
        
        for step in range(1, 4):
            future_date = last_date + timedelta(days=30 * step)
            forecast_months.append(future_date.strftime('%b %Y (F)'))
            
            proj_val = max(0.0, slope * (n - 1 + step) + intercept)
            margin = std_err * (1.0 + 0.15 * step)
            
            forecast_revenue.append(round(proj_val, 2))
            forecast_upper.append(round(proj_val + margin, 2))
            forecast_lower.append(round(max(0.0, proj_val - margin), 2))
    else:
        now = timezone.now()
        for step in range(1, 4):
            future_date = now + timedelta(days=30 * step)
            forecast_months.append(future_date.strftime('%b %Y (F)'))
            forecast_revenue.append(0.0)
            forecast_upper.append(0.0)
            forecast_lower.append(0.0)

    cat_sales = OrderItem.objects.filter(
        order__status__in=paid_statuses
    ).values(
        'item__category__name'
    ).annotate(
        total_revenue=Sum('subtotal'),
        units_sold=Sum('quantity')
    ).order_by('-total_revenue')[:8]

    category_labels = [c['item__category__name'] or 'Uncategorized' for c in cat_sales]
    category_revenues = [round(float(c['total_revenue'] or 0.0), 2) for c in cat_sales]

    next_month_projected = forecast_revenue[0] if forecast_revenue else 0.0
    last_revenue = historical_revenue[-1] if historical_revenue else 0.0
    prev_revenue = historical_revenue[-2] if len(historical_revenue) > 1 else last_revenue
    mom_growth = round(((last_revenue - prev_revenue) / max(1.0, prev_revenue)) * 100, 1)

    avg_monthly_rev = sum(historical_revenue) / max(1, len(historical_revenue)) if historical_revenue else 1.0
    max_rev = max(historical_revenue) if historical_revenue else 1.0
    seasonality_index = round(max_rev / max(1.0, avg_monthly_rev), 2)

    return {
        'months_labels': months_labels,
        'historical_revenue': historical_revenue,
        'forecast_months': forecast_months,
        'forecast_revenue': forecast_revenue,
        'forecast_upper': forecast_upper,
        'forecast_lower': forecast_lower,
        'category_labels': category_labels,
        'category_revenues': category_revenues,
        'next_month_projected': next_month_projected,
        'mom_growth': mom_growth,
        'seasonality_index': seasonality_index,
    }


# ==============================================================================
# DATA SIMULATOR & CONFIGURATION SERVICE
# ==============================================================================

def get_config_filepath():
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, 'data', 'weights_config.json')


def get_simulator_config() -> dict:
    """
    Reads dataset generation weights and simulation parameters from weights_config.json.
    """
    filepath = get_config_filepath()
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if 'simulation_params' not in config:
                    config['simulation_params'] = {
                        "num_users": 5000,
                        "monthly_inflation": 0.04,
                        "foreign_ratio": 0.20,
                        "seed": 42
                    }
                return config
        except Exception as e:
            print(f"[Error] Reading weights_config.json: {e}")

    return {
        "simulation_params": {
            "num_users": 5000,
            "monthly_inflation": 0.04,
            "foreign_ratio": 0.20,
            "seed": 42
        },
        "product_tiers": {
            "tier_1_best_sellers": {"percentage_of_catalog": 0.01, "sales_weight": 0.50},
            "tier_2_steady_sellers": {"percentage_of_catalog": 0.09, "sales_weight": 0.30},
            "tier_3_slow_sellers": {"percentage_of_catalog": 0.30, "sales_weight": 0.15},
            "tier_4_long_tail": {"percentage_of_catalog": 0.60, "sales_weight": 0.05}
        },
        "category_weights": {cat: 0.5 for cat in CATEGORIES_LIST}
    }


def save_simulator_config(new_config: dict) -> dict:
    """
    Updates and saves the simulation parameters and weights to weights_config.json.
    """
    filepath = get_config_filepath()
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    current_config = get_simulator_config()

    if 'simulation_params' in new_config:
        current_config['simulation_params'].update(new_config['simulation_params'])
    if 'product_tiers' in new_config:
        current_config['product_tiers'].update(new_config['product_tiers'])
    if 'category_weights' in new_config:
        current_config['category_weights'].update(new_config['category_weights'])

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(current_config, f, ensure_ascii=False, indent=2)

    return current_config


def get_generation_progress() -> dict:
    """
    Returns a safe copy of current dataset generation status for frontend polling.
    """
    with GENERATION_LOCK:
        return dict(GENERATION_STATUS)


def update_progress(pct: int, step: str, log_msg: str = None, error: str = None):
    with GENERATION_LOCK:
        GENERATION_STATUS["progress_pct"] = pct
        GENERATION_STATUS["current_step"] = step
        if log_msg:
            timestamp = datetime.now().strftime("%H:%M:%S")
            GENERATION_STATUS["logs"].append(f"[{timestamp}] {log_msg}")
        if error:
            GENERATION_STATUS["error"] = error
            GENERATION_STATUS["is_running"] = False


def generate_dataset_pipeline(config_override: dict = None, seed: int = None, console_callback=None):
    """
    Core dataset generator engine based on Amazon Reviews 2023 metadata.
    Includes adaptive server guardrails and memory-chunking insertions to keep RAM < 120 MB.
    """
    with GENERATION_LOCK:
        if GENERATION_STATUS["is_running"]:
            raise RuntimeError("Dataset generation is already in progress.")
        GENERATION_STATUS["is_running"] = True
        GENERATION_STATUS["progress_pct"] = 0
        GENERATION_STATUS["current_step"] = "Initializing generation engine..."
        GENERATION_STATUS["logs"] = []
        GENERATION_STATUS["error"] = None
        GENERATION_STATUS["completed_at"] = None

    def log(msg):
        if console_callback:
            console_callback(msg)

    try:
        if config_override:
            config = save_simulator_config(config_override)
        else:
            config = get_simulator_config()

        sim_params = config.get("simulation_params", {})
        num_users = int(sim_params.get("num_users", 5000))
        monthly_inflation = float(sim_params.get("monthly_inflation", 0.04))
        foreign_ratio = float(sim_params.get("foreign_ratio", 0.20))
        
        # Adaptive Server Guardrail Limit for Web / Production Environments
        if is_production_environment() and num_users > 1000:
            log(f"[Server Guardrail] Capping web user generation from {num_users} to 1,000 for server RAM optimization.")
            num_users = 1000
        
        if seed is None:
            seed = int(sim_params.get("seed", 42))

        update_progress(5, "Setting up random seed and loading parameters", f"Engine started with Seed: {seed} (Users: {num_users})")
        log(f"Generating data using seed: {seed}")
        
        random.seed(seed)
        Faker.seed(seed)
        fake = Faker(['es_ES', 'es_AR'])

        data_dir = os.path.dirname(get_config_filepath())
        
        update_progress(10, "Ingesting Amazon Reviews dataset cache...", "Loading product catalog metadata...")
        amazon_data = get_amazon_data(data_dir, limit_meta=65, limit_reviews=100)
        products = amazon_data["products"]
        reviews = amazon_data["reviews"]

        update_progress(18, "Clearing previous database records...", "Purging old sales, items, users & profiles...")
        log("1. Purging existing database records...")

        models_to_purge = [OrderItem, Order, Comments, Item, Category, Brand, Supplier, Profile]
        db_tables = [m._meta.db_table for m in models_to_purge]

        with transaction.atomic():
            with connection.cursor() as cursor:
                if connection.vendor == 'postgresql':
                    tbl_str = ', '.join([f'"{t}"' for t in db_tables])
                    cursor.execute(f'TRUNCATE TABLE {tbl_str} RESTART IDENTITY CASCADE;')
                    cursor.execute('DELETE FROM auth_user WHERE is_superuser = false;')
                elif connection.vendor == 'sqlite':
                    cursor.execute('PRAGMA foreign_keys = OFF;')
                    for tbl in db_tables:
                        cursor.execute(f'DELETE FROM {tbl};')
                    cursor.execute('DELETE FROM auth_user WHERE is_superuser = 0;')
                    cursor.execute('PRAGMA foreign_keys = ON;')
                else:
                    for m in models_to_purge:
                        m.objects.all().delete()
                    User.objects.exclude(is_superuser=True).delete()

        gc.collect()

        update_progress(25, "Creating Categories & Suppliers...", f"Generating {len(CATEGORIES_LIST)} categories...")
        log(f"2. Creating Categories & Suppliers...")
        Category.objects.bulk_create([Category(name=name) for name in CATEGORIES_LIST])
        cats_db = {c.name: c for c in Category.objects.all()}
        
        unique_brands = sorted(list(set(p["brand"][:100] for p in products)))
        if "Generic" not in unique_brands:
            unique_brands.append("Generic")
            
        Brand.objects.bulk_create([Brand(name=name[:100]) for name in unique_brands])
        brands_db = {b.name: b for b in Brand.objects.all()}
        
        num_suppliers = 50
        countries_pool = ['United States'] * 6 + ['Canada', 'United Kingdom', 'Germany', 'China', 'Japan']
        Supplier.objects.bulk_create([Supplier(name=fake.company(), country=random.choice(countries_pool)) for _ in range(num_suppliers)])
        suppliers_db = list(Supplier.objects.all())
        
        supplier_weights = [1.0 / (i**1.5) for i in range(1, num_suppliers + 1)]

        update_progress(35, "Generating Catalog Items from Amazon metadata...", f"Processing {len(products)} products...")
        log(f"3. Generating Catalog Items from Amazon metadata...")
        item_objs = []
        for idx, p in enumerate(products):
            price = p["price"]
            if price is None or price <= 0:
                price = round(math.exp(random.gauss(8, 1.5)), 2)
                price = max(100.0, min(price, 50000.0))
                
            cost = round(price * random.uniform(0.45, 0.80), 2)
            cat = cats_db.get(p["category"], cats_db["Unknown"])
            brand = brands_db.get(p["brand"][:100], brands_db["Generic"])
            sup = random.choices(suppliers_db, weights=supplier_weights)[0]
            
            item_objs.append(Item(
                title=p["title"][:100],
                description=p["description"][:200] if p["description"] else "No description",
                price=price,
                cost=cost,
                stock=random.randint(0, 500),
                minimum_stock=random.randint(10, 50),
                category=cat,
                supplier=sup,
                brand=brand,
                slug=f"item-{idx}-{random.randint(1000, 9999)}",
                is_active=random.choices([True, False], weights=[0.95, 0.05])[0]
            ))
            
        Item.objects.bulk_create(item_objs, batch_size=500)
        items_db = list(Item.objects.select_related('category').order_by('id'))
        asin_to_item = {products[idx]["parent_asin"]: item for idx, item in enumerate(items_db)}

        # Shuffle items so top sellers & best-selling categories vary across random seeds
        random.shuffle(items_db)

        num_items = len(items_db)
        tier_configs = config.get("product_tiers", {})
        cat_weights = config.get("category_weights", {})
        
        t1_pct = float(tier_configs.get("tier_1_best_sellers", {}).get("percentage_of_catalog", 0.01))
        t2_pct = float(tier_configs.get("tier_2_steady_sellers", {}).get("percentage_of_catalog", 0.09))
        t3_pct = float(tier_configs.get("tier_3_slow_sellers", {}).get("percentage_of_catalog", 0.30))
        
        t1_count = int(num_items * t1_pct)
        t2_count = int(num_items * t2_pct)
        t3_count = int(num_items * t3_pct)
        t4_count = num_items - t1_count - t2_count - t3_count
        
        t1_w = float(tier_configs.get("tier_1_best_sellers", {}).get("sales_weight", 0.50)) / max(1, t1_count)
        t2_w = float(tier_configs.get("tier_2_steady_sellers", {}).get("sales_weight", 0.30)) / max(1, t2_count)
        t3_w = float(tier_configs.get("tier_3_slow_sellers", {}).get("sales_weight", 0.15)) / max(1, t3_count)
        t4_w = float(tier_configs.get("tier_4_long_tail", {}).get("sales_weight", 0.05)) / max(1, t4_count)
        
        items_sales_weights = []
        for idx, item in enumerate(items_db):
            if idx < t1_count:
                base_w = t1_w
            elif idx < t1_count + t2_count:
                base_w = t2_w
            elif idx < t1_count + t2_count + t3_count:
                base_w = t3_w
            else:
                base_w = t4_w
                
            cat_multiplier = float(cat_weights.get(item.category.name if item.category else "Unknown", 1.0))
            items_sales_weights.append(base_w * max(0.01, cat_multiplier))

        update_progress(50, f"Generating {num_users} Users & Profiles...", f"Creating user base with {foreign_ratio*100:.0f}% international ratio...")
        log(f"4. Generating Users & Profiles...")
        end_date = timezone.now()
        user_objs = []
        username_to_gender = {}
        for i in range(num_users):
            uname = f"user_{i}_{random.randint(10000,99999)}"
            # User registration date prior to simulation horizon (730-900 days ago)
            user_joined = end_date - timedelta(days=random.randint(730, 900), hours=random.randint(0, 23))
            
            # Determine gender and generate matching first name
            gender = random.choices(['M', 'F', 'O'], weights=[0.48, 0.48, 0.04])[0]
            if gender == 'M':
                first_name = fake.first_name_male()[:30]
            elif gender == 'F':
                first_name = fake.first_name_female()[:30]
            else:
                first_name = fake.first_name()[:30]
                
            u = User(
                username=uname,
                email=fake.email(),
                first_name=first_name,
                last_name=fake.last_name()[:30],
                date_joined=user_joined
            )
            user_objs.append(u)
            username_to_gender[uname] = gender
            
        User.objects.bulk_create(user_objs, batch_size=1000)
        users_db = list(User.objects.exclude(is_superuser=True).order_by('id'))
        
        profile_objs = []
        for user in users_db:
            is_foreign = random.random() < foreign_ratio
            if is_foreign:
                country = random.choice(['Canada', 'United Kingdom', 'Germany', 'Australia', 'Japan', 'Argentina', 'Brazil'])
                province = fake.state()
            else:
                country = 'United States'
                province = random.choice(['California', 'New York', 'Texas', 'Florida', 'Illinois'])
                
            gender = username_to_gender.get(user.username)
            profile_objs.append(Profile(
                user=user,
                phone=fake.phone_number()[:30],
                address_line=fake.street_address()[:255],
                city=fake.city()[:100],
                province=province[:100],
                zip_code=fake.postcode()[:20],
                country=country[:100],
                birth_date=fake.date_of_birth(minimum_age=18, maximum_age=80),
                gender=gender
            ))
            
        Profile.objects.bulk_create(profile_objs, batch_size=1000)
        profile_dict = {p.user_id: p for p in profile_objs}

        # MEMORY CHUNKING FOR ORDERS AND ORDERITEMS
        update_progress(65, "Simulating Orders with Memory Chunking...", f"Inserting in streaming chunks of 500 orders...")
        log(f"5. Simulating Orders with Memory Chunking...")
        
        # User Conversion Funnel: ~25% inactive registered users (0 orders)
        user_order_counts = []
        for _ in range(num_users):
            if random.random() < 0.25:
                user_order_counts.append(0)
            else:
                user_order_counts.append(int(random.paretovariate(2.2)))
        
        total_orders_counter = 0
        total_items_counter = 0
        units_sold_per_item = {}
        
        chunk_orders = []
        chunk_items_data = []
        
        def flush_order_chunk():
            nonlocal chunk_orders, chunk_items_data, total_orders_counter, total_items_counter
            if not chunk_orders:
                return
                
            chunk_len = len(chunk_orders)
            Order.objects.bulk_create(chunk_orders, batch_size=500)
            
            inserted_orders = list(Order.objects.order_by('-id')[:chunk_len][::-1])
            
            chunk_order_item_objs = []
            for idx, order in enumerate(inserted_orders):
                if idx < len(chunk_items_data):
                    items_data = chunk_items_data[idx]
                    for data in items_data:
                        chunk_order_item_objs.append(OrderItem(
                            order=order,
                            item=data['item'],
                            quantity=data['qty'],
                            unit_price=data['price'],
                            unit_cost=data['cost'],
                            subtotal=data['subtotal']
                        ))
                        
            OrderItem.objects.bulk_create(chunk_order_item_objs, batch_size=1000)
            
            total_orders_counter += chunk_len
            total_items_counter += len(chunk_order_item_objs)
            
            chunk_orders.clear()
            chunk_items_data.clear()
            gc.collect()

        for u_idx, user in enumerate(users_db):
            orders_to_create = user_order_counts[u_idx]
            if orders_to_create == 0:
                continue

            profile = profile_dict.get(user.id)
            is_intl = profile.is_international() if profile else False
            
            for _ in range(orders_to_create):
                while True:
                    days_ago = random.randint(0, 730)
                    # Randomize hour, minute, and second of purchase
                    test_date = end_date - timedelta(
                        days=days_ago,
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                        seconds=random.randint(0, 59)
                    )
                    month = test_date.month
                    weight = 1.0
                    if month == 11: weight = 1.4
                    elif month == 12: weight = 1.8
                    elif month == 7: weight = 1.15
                    elif month == 1: weight = 0.75
                    
                    if random.random() < weight / 1.8:
                        if test_date >= user.date_joined:
                            order_date = test_date
                            break
                        
                months_ago = days_ago / 30.0
                inflation_factor = (1 + monthly_inflation) ** months_ago
                
                num_items_in_order = random.randint(1, 5)
                selected_items = random.choices(items_db, weights=items_sales_weights, k=num_items_in_order)
                
                subtotal = 0.0
                items_for_this_order = []
                for itm in selected_items:
                    qty = random.randint(1, 3)
                    past_price = max(1.0, round(float(itm.price) / inflation_factor, 2))
                    past_cost = max(0.5, round(float(itm.cost) / inflation_factor, 2))
                    it_subtotal = round(past_price * qty, 2)
                    subtotal += it_subtotal
                    
                    # Track total units sold for inventory decrement
                    units_sold_per_item[itm.id] = units_sold_per_item.get(itm.id, 0) + qty
                    
                    items_for_this_order.append({
                        'item': itm,
                        'qty': qty,
                        'price': past_price,
                        'cost': past_cost,
                        'subtotal': it_subtotal
                    })
                
                discount = 0.0
                discount_code = None
                if random.random() < 0.2:
                    discount_code = random.choice(['DESC10', 'PROMO10', 'OFF500', 'DISCOUNT'])
                    if discount_code in ['DESC10', 'PROMO10']:
                        discount = round(subtotal * 0.10, 2)
                    elif discount_code == 'OFF500':
                        if subtotal >= 1000.0:
                            discount = 500.00
                        else:
                            discount = round(subtotal * 0.20, 2)
                    else: # DISCOUNT
                        discount = round(min(500.0, subtotal * 0.25), 2)
                        
                shipping_cost = 2500.0 if is_intl else 500.0
                total = max(0.0, subtotal + shipping_cost - discount)
                
                chunk_orders.append(Order(
                    user=user,
                    status=random.choices([OrderStatus.DELIVERED, OrderStatus.SHIPPED, OrderStatus.PAID, OrderStatus.CANCELED, OrderStatus.PENDING], weights=[0.6, 0.1, 0.1, 0.1, 0.1])[0],
                    payment_method=random.choice(list(PaymentMethod)).value,
                    discount_code=discount_code,
                    discount=discount,
                    shipping_cost=shipping_cost,
                    total=total,
                    ordered_date=order_date
                ))
                chunk_items_data.append(items_for_this_order)
                
                if len(chunk_orders) >= 500:
                    flush_order_chunk()

        # Flush remaining chunk
        flush_order_chunk()

        # Decrement stock based on simulated sales
        for itm in items_db:
            sold_qty = units_sold_per_item.get(itm.id, 0)
            itm.stock = max(0, itm.stock - sold_qty)
        Item.objects.bulk_update(items_db, ['stock'], batch_size=1000)

        update_progress(92, "Generating Reviews & Comments...", f"Ensuring rating coverage across all categories...")
        log(f"6. Generating Reviews & Comments...")
        comment_objs = []
        used_pairs = set()

        items_by_cat = {}
        for item in items_db:
            cname = item.category.name if item.category else "Unknown"
            items_by_cat.setdefault(cname, []).append(item)

        reviews_by_cat = {}
        for rev in reviews:
            cname = rev.get("category", "Unknown")
            reviews_by_cat.setdefault(cname, []).append(rev)

        sample_bodies = [
            "Excelente producto, cumplió con todas mis expectativas.",
            "Buena relación calidad-precio. Llegó a tiempo y bien empaquetado.",
            "Muy satisfecho con la compra, funciona de maravilla.",
            "Calidad garantizada, lo recomiendo totalmente.",
            "Un producto muy práctico y duradero. Volvería a comprarlo."
        ]

        # Step A: Guarantee at least 2-4 comments/ratings for EVERY category
        for cat_name, cat_obj in cats_db.items():
            cat_items = items_by_cat.get(cat_name, [])
            if not cat_items:
                continue
            
            cat_reviews = reviews_by_cat.get(cat_name, [])
            count_to_create = max(2, min(5, len(cat_reviews) if cat_reviews else 3))
            
            for i in range(count_to_create):
                target_item = random.choice(cat_items)
                usr = random.choice(users_db)
                pair = (usr.id, target_item.id)
                
                if pair not in used_pairs:
                    used_pairs.add(pair)
                    if i < len(cat_reviews) and cat_reviews[i].get("text"):
                        body_text = cat_reviews[i]["text"][:1000]
                        rating_val = int(cat_reviews[i].get("rating", random.randint(4, 5)))
                    else:
                        body_text = random.choice(sample_bodies)
                        rating_val = random.randint(3, 5)
                        
                    comment_objs.append(Comments(
                        user=usr,
                        item=target_item,
                        body=body_text,
                        rating=rating_val,
                        likes=random.randint(0, 100)
                    ))

        # Step B: Process remaining Amazon dataset reviews
        for rev in reviews:
            item = asin_to_item.get(rev["parent_asin"])
            if not item:
                continue
                
            usr = random.choice(users_db)
            pair = (usr.id, item.id)
            if pair not in used_pairs:
                used_pairs.add(pair)
                comment_objs.append(Comments(
                    user=usr,
                    item=item,
                    body=rev["text"][:1000] if rev["text"] else "Excelente producto",
                    rating=int(rev.get("rating", 5)),
                    likes=random.randint(0, 100)
                ))
                
        Comments.objects.bulk_create(comment_objs, batch_size=1000)
        gc.collect()

        summary_msg = f"Dataset generated: {len(items_db)} Items, {len(users_db)} Users, {total_orders_counter} Orders, {total_items_counter} OrderItems."
        update_progress(100, "Dataset generation complete!", summary_msg)
        log(summary_msg)

        with GENERATION_LOCK:
            GENERATION_STATUS["is_running"] = False
            GENERATION_STATUS["completed_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            GENERATION_STATUS["stats"] = {
                "items": len(items_db),
                "users": len(users_db),
                "orders": total_orders_counter,
                "order_items": total_items_counter,
                "seed": seed
            }

    except Exception as e:
        error_msg = f"Generation error: {str(e)}"
        update_progress(0, "Error", error=error_msg)
        log(f"[Error] {error_msg}")
        raise e


def start_async_dataset_generation(config_override: dict = None, seed: int = None) -> bool:
    """
    Launches dataset generation in a background thread for HTTP non-blocking processing.
    """
    with GENERATION_LOCK:
        if GENERATION_STATUS["is_running"]:
            return False

    thread = threading.Thread(
        target=generate_dataset_pipeline,
        kwargs={"config_override": config_override, "seed": seed},
        daemon=True
    )
    thread.start()
    return True


# ==============================================================================
# INTERNAL METRICS SERVICE (AI ORCHESTRATOR CONTRACT)
# ==============================================================================

def _format_top_products(top_products_raw: list) -> list:
    formatted = []
    for p in top_products_raw:
        formatted.append({
            'product_id': p.get('item__id'),
            'title': p.get('item__title'),
            'category': p.get('item__category__name'),
            'price': float(p.get('item__price') or 0.0),
            'total_units_sold': int(p.get('total_units_sold') or 0),
            'total_revenue_generated': float(p.get('total_revenue_generated') or 0.0),
        })
    return formatted


def _format_top_product_star(star_raw: dict) -> dict:
    if not star_raw:
        return None
    return {
        'product_id': star_raw.get('item__id'),
        'title': star_raw.get('item__title'),
        'category': star_raw.get('item__category__name'),
        'price': float(star_raw.get('item__price') or 0.0),
        'total_units_sold': int(star_raw.get('total_units_sold') or 0),
        'total_revenue_generated': float(star_raw.get('total_revenue_generated') or 0.0),
    }


def get_internal_metrics_service(metric_type: str = 'overview') -> tuple:
    """
    Internal business metrics service for AI orchestrator consumption.

    Args:
        metric_type (str): Type of metric to retrieve:
            'overview' | 'kpis' | 'forecast' | 'sales_trend' |
            'category_distribution' | 'top_products' | 'all'

    Returns:
        tuple (dict, int): Payload dictionary and HTTP status code.
    """
    cleaned_type = (metric_type or 'overview').lower().strip()

    valid_types = {
        'overview', 'kpis', 'forecast', 'sales_trend',
        'category_distribution', 'top_products', 'all'
    }

    if cleaned_type not in valid_types:
        return {
            'error': 'Bad Request',
            'detail': 'Invalid metric_type. Supported values: overview, kpis, forecast, sales_trend, category_distribution, top_products, all',
        }, 400

    if cleaned_type in ('overview', 'kpis'):
        kpis = get_dashboard_kpis()
        payload = {
            'metric_type': cleaned_type,
            'current_month': kpis['current_month_name'],
            'monthly_revenue': float(kpis['monthly_revenue']),
            'monthly_orders': int(kpis['monthly_orders_count']),
            'avg_order_value': float(kpis['avg_order_value']),
            'active_customers': int(kpis['active_customers_count']),
            'abandoned_carts': int(kpis['abandoned_carts_count']),
            'top_product_star': _format_top_product_star(kpis['top_product_star']),
        }
        return payload, 200

    elif cleaned_type in ('forecast', 'sales_trend'):
        forecast_data = get_forecast_data()
        payload = {
            'metric_type': cleaned_type,
            'historical_trend': {
                'months': forecast_data['months_labels'],
                'revenue': [float(r) for r in forecast_data['historical_revenue']],
            },
            'forecast_3_months': {
                'months': forecast_data['forecast_months'],
                'projected_revenue': [float(r) for r in forecast_data['forecast_revenue']],
                'upper_bound': [float(r) for r in forecast_data['forecast_upper']],
                'lower_bound': [float(r) for r in forecast_data['forecast_lower']],
            },
            'next_month_projected': float(forecast_data['next_month_projected']),
            'mom_growth_pct': float(forecast_data['mom_growth']),
            'seasonality_index': float(forecast_data['seasonality_index']),
        }
        return payload, 200

    elif cleaned_type == 'category_distribution':
        forecast_data = get_forecast_data()
        categories_data = [
            {'category': label, 'revenue': float(rev)}
            for label, rev in zip(forecast_data['category_labels'], forecast_data['category_revenues'])
        ]
        payload = {
            'metric_type': 'category_distribution',
            'categories': categories_data,
            'total_category_revenue': round(sum(float(r) for r in forecast_data['category_revenues']), 2),
        }
        return payload, 200

    elif cleaned_type == 'top_products':
        kpis = get_dashboard_kpis()
        top_prods = _format_top_products(kpis['top_products'])
        payload = {
            'metric_type': 'top_products',
            'total_returned': len(top_prods),
            'top_products': top_prods,
        }
        return payload, 200

    elif cleaned_type == 'all':
        kpis = get_dashboard_kpis()
        forecast_data = get_forecast_data()
        categories_data = [
            {'category': label, 'revenue': float(rev)}
            for label, rev in zip(forecast_data['category_labels'], forecast_data['category_revenues'])
        ]
        payload = {
            'metric_type': 'all',
            'overview': {
                'current_month': kpis['current_month_name'],
                'monthly_revenue': float(kpis['monthly_revenue']),
                'monthly_orders': int(kpis['monthly_orders_count']),
                'avg_order_value': float(kpis['avg_order_value']),
                'active_customers': int(kpis['active_customers_count']),
                'abandoned_carts': int(kpis['abandoned_carts_count']),
                'top_product_star': _format_top_product_star(kpis['top_product_star']),
            },
            'forecast': {
                'historical_trend': {
                    'months': forecast_data['months_labels'],
                    'revenue': [float(r) for r in forecast_data['historical_revenue']],
                },
                'forecast_3_months': {
                    'months': forecast_data['forecast_months'],
                    'projected_revenue': [float(r) for r in forecast_data['forecast_revenue']],
                    'upper_bound': [float(r) for r in forecast_data['forecast_upper']],
                    'lower_bound': [float(r) for r in forecast_data['forecast_lower']],
                },
                'next_month_projected': float(forecast_data['next_month_projected']),
                'mom_growth_pct': float(forecast_data['mom_growth']),
                'seasonality_index': float(forecast_data['seasonality_index']),
            },
            'category_distribution': {
                'categories': categories_data,
                'total_category_revenue': round(sum(float(r) for r in forecast_data['category_revenues']), 2),
            },
            'top_products': _format_top_products(kpis['top_products']),
        }
        return payload, 200

    return {
        'error': 'Bad Request',
        'detail': 'Invalid metric_type. Supported values: overview, kpis, forecast, sales_trend, category_distribution, top_products, all',
    }, 400