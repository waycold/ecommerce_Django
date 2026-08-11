import sys
import math
import random
import json
import os
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
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

class Command(BaseCommand):
    help = 'Generates synthetic dataset for analytics based on Amazon Reviews 2023'

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed',
            type=int,
            help='Specify a seed for reproducible generation'
        )

    def print_progress(self, current, total, bar_length=40, prefix='Progress'):
        progress = float(current) / total if total > 0 else 1
        arrow = '-' * int(round(progress * bar_length) - 1) + '>'
        spaces = ' ' * (bar_length - len(arrow))
        sys.stdout.write(f'\r{prefix}: [{arrow}{spaces}] {int(round(progress * 100))}% ({current}/{total})')
        sys.stdout.flush()
        if current >= total:
            sys.stdout.write('\n')

    def handle(self, *args, **kwargs):
        # Determine seed
        seed = kwargs.get('seed')
        if seed is None:
            seed = random.randint(1, 1000000)
            
        self.stdout.write(self.style.SUCCESS(f"Generating data using seed: {seed}"))
        random.seed(seed)
        Faker.seed(seed)
        fake = Faker(['es_ES', 'es_AR'])

        # Load config weights
        data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        weights_path = os.path.join(data_dir, 'weights_config.json')
        with open(weights_path, 'r', encoding='utf-8') as f:
            weights_config = json.load(f)

        # Ingest Amazon 2023 dataset (uses cache if exists, otherwise streams from Hugging Face)
        self.stdout.write("Ingesting Amazon Reviews 2023 dataset...")
        amazon_data = get_amazon_data(data_dir, limit_meta=65, limit_reviews=100)
        products = amazon_data["products"]
        reviews = amazon_data["reviews"]

        self.stdout.write("1. Deleting existing records...")
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        Comments.objects.all().delete()
        Item.objects.all().delete()
        Category.objects.all().delete()
        Brand.objects.all().delete()
        Supplier.objects.all().delete()
        Profile.objects.all().delete()
        User.objects.exclude(is_superuser=True).delete()

        self.stdout.write("2. Generating Categories...")
        Category.objects.bulk_create([Category(name=name) for name in CATEGORIES_LIST])
        cats_db = {c.name: c for c in Category.objects.all()}
        
        # Build category probability list based on our config weights
        cat_probs = [weights_config["category_weights"].get(cat_name, 1.0) for cat_name in CATEGORIES_LIST]
        
        self.stdout.write("3. Generating Brands and Suppliers (Zipf distribution)...")
        # Extract unique brand names from imported products
        unique_brands = sorted(list(set(p["brand"][:100] for p in products)))
        # Make sure "Generic" is available
        if "Generic" not in unique_brands:
            unique_brands.append("Generic")
            
        Brand.objects.bulk_create([Brand(name=name[:100]) for name in unique_brands])
        brands_db = {b.name: b for b in Brand.objects.all()}
        
        num_suppliers = 50
        countries_pool = ['Argentina'] * 7 + ['Chile', 'Brasil', 'USA', 'China']
        Supplier.objects.bulk_create([Supplier(name=fake.company(), country=random.choice(countries_pool)) for _ in range(num_suppliers)])
        suppliers_db = list(Supplier.objects.all())
        
        def zipf_weights(n, alpha=1.5):
            return [1.0 / (i**alpha) for i in range(1, n+1)]
            
        supplier_weights = zipf_weights(num_suppliers)

        self.stdout.write(f"4. Generating {len(products)} Items from Amazon Metadata...")
        item_objs = []
        for idx, p in enumerate(products):
            if idx % 100 == 0:
                self.print_progress(idx, len(products), prefix='Items')
            
            # Retrieve or generate log-normal price
            price = p["price"]
            if price is None or price <= 0:
                price = round(math.exp(random.gauss(8, 1.5)), 2)
                price = max(100.0, min(price, 50000.0))
                
            cost = round(price * random.uniform(0.45, 0.80), 2)
            
            cat_name = p["category"]
            cat = cats_db.get(cat_name, cats_db["Unknown"])
            
            brand_name = p["brand"][:100]
            brand = brands_db.get(brand_name, brands_db["Generic"])
            
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
            
        self.print_progress(len(products), len(products), prefix='Items')
        Item.objects.bulk_create(item_objs, batch_size=500)
        items_db = list(Item.objects.order_by('id'))
        
        # Build map parent_asin -> Item database object
        asin_to_item = {}
        for idx, item in enumerate(items_db):
            asin = products[idx]["parent_asin"]
            asin_to_item[asin] = item

        # Calculate boundaries and weights for product Tiers based on actual items generated
        num_items = len(items_db)
        tier_configs = weights_config["product_tiers"]
        t1_pct = tier_configs["tier_1_best_sellers"]["percentage_of_catalog"]
        t2_pct = tier_configs["tier_2_steady_sellers"]["percentage_of_catalog"]
        t3_pct = tier_configs["tier_3_slow_sellers"]["percentage_of_catalog"]
        
        t1_count = int(num_items * t1_pct)
        t2_count = int(num_items * t2_pct)
        t3_count = int(num_items * t3_pct)
        t4_count = num_items - t1_count - t2_count - t3_count
        
        t1_w = tier_configs["tier_1_best_sellers"]["sales_weight"] / max(1, t1_count)
        t2_w = tier_configs["tier_2_steady_sellers"]["sales_weight"] / max(1, t2_count)
        t3_w = tier_configs["tier_3_slow_sellers"]["sales_weight"] / max(1, t3_count)
        t4_w = tier_configs["tier_4_long_tail"]["sales_weight"] / max(1, t4_count)
        
        items_sales_weights = []
        for idx in range(num_items):
            if idx < t1_count:
                items_sales_weights.append(t1_w)
            elif idx < t1_count + t2_count:
                items_sales_weights.append(t2_w)
            elif idx < t1_count + t2_count + t3_count:
                items_sales_weights.append(t3_w)
            else:
                items_sales_weights.append(t4_w)

        self.stdout.write("5. Generating 5000 Users and Profiles...")
        user_objs = []
        for i in range(5000):
            if i % 500 == 0:
                self.print_progress(i, 5000, prefix='Users')
            uname = f"user_{i}_{random.randint(10000,99999)}"
            user_objs.append(User(
                username=uname,
                email=fake.email(),
                first_name=fake.first_name()[:30],
                last_name=fake.last_name()[:30]
            ))
        self.print_progress(5000, 5000, prefix='Users')
        User.objects.bulk_create(user_objs, batch_size=1000)
        users_db = list(User.objects.exclude(is_superuser=True).order_by('id'))
        
        self.stdout.write("Generating Profiles...")
        profile_objs = []
        for i, user in enumerate(users_db):
            if i % 500 == 0:
                self.print_progress(i, 5000, prefix='Profiles')
            
            is_foreign = random.random() < 0.20
            if is_foreign:
                country = random.choice(['Chile', 'Brasil', 'Uruguay', 'Peru', 'Mexico', 'USA', 'Spain'])
                province = fake.state()
            else:
                country = 'Argentina'
                province = random.choice(['Buenos Aires', 'CABA', 'Cordoba', 'Santa Fe', 'Mendoza'])
                
            profile_objs.append(Profile(
                user=user,
                phone=fake.phone_number()[:30],
                address_line=fake.street_address()[:255],
                city=fake.city()[:100],
                province=province[:100],
                zip_code=fake.postcode()[:20],
                country=country[:100],
                birth_date=fake.date_of_birth(minimum_age=18, maximum_age=80)
            ))
        self.print_progress(5000, 5000, prefix='Profiles')
        Profile.objects.bulk_create(profile_objs, batch_size=1000)
        profile_dict = {p.user_id: p for p in profile_objs}
        
        self.stdout.write("6. Generating Orders and OrderItems over 24 months...")
        end_date = timezone.now()
        
        user_order_counts = [int(random.paretovariate(2.5)) for _ in range(5000)]
        total_orders_approx = sum(user_order_counts)
        self.stdout.write(f"Will generate roughly {total_orders_approx} orders.")
        
        MONTHLY_INFLATION = 0.04
        order_batch = []
        order_items_data_per_order = []
        
        for u_idx, user in enumerate(users_db):
            if u_idx % 100 == 0:
                self.print_progress(u_idx, 5000, prefix='Order Prep')
                
            orders_to_create = user_order_counts[u_idx]
            profile = profile_dict.get(user.id)
            is_intl = profile.is_international() if profile else False
            
            for _ in range(orders_to_create):
                while True:
                    days_ago = random.randint(0, 730)
                    test_date = end_date - timedelta(days=days_ago)
                    month = test_date.month
                    weight = 1.0
                    if month == 11: weight = 1.4
                    elif month == 12: weight = 1.8
                    elif month == 7: weight = 1.15
                    elif month == 1: weight = 0.75
                    
                    if random.random() < weight / 1.8:
                        order_date = test_date
                        break
                        
                months_ago = days_ago / 30.0
                inflation_factor = (1 + MONTHLY_INFLATION) ** months_ago
                
                num_items = random.randint(1, 5)
                selected_items = random.choices(items_db, weights=items_sales_weights, k=num_items)
                
                subtotal = 0.0
                items_for_this_order = []
                for itm in selected_items:
                    qty = random.randint(1, 3)
                    past_price = max(1.0, round(float(itm.price) / inflation_factor, 2))
                    past_cost = max(0.5, round(float(itm.cost) / inflation_factor, 2))
                    it_subtotal = round(past_price * qty, 2)
                    subtotal += it_subtotal
                    
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
                    else:
                        discount = min(500.00, subtotal)
                        
                shipping_cost = 2500.0 if is_intl else 500.0
                total = max(0.0, subtotal + shipping_cost - discount)
                
                order_batch.append(Order(
                    user=user,
                    status=random.choices([OrderStatus.DELIVERED, OrderStatus.SHIPPED, OrderStatus.PAID, OrderStatus.CANCELED, OrderStatus.PENDING], weights=[0.6, 0.1, 0.1, 0.1, 0.1])[0],
                    payment_method=random.choice(list(PaymentMethod)).value,
                    discount_code=discount_code,
                    discount=discount,
                    shipping_cost=shipping_cost,
                    total=total,
                    ordered_date=order_date
                ))
                order_items_data_per_order.append(items_for_this_order)
                
        self.print_progress(5000, 5000, prefix='Order Prep')
        
        self.stdout.write(f"Bulk inserting {len(order_batch)} orders...")
        Order.objects.bulk_create(order_batch, batch_size=2000)
        
        self.stdout.write("Fetching created orders and building OrderItems...")
        inserted_orders = list(Order.objects.order_by('id'))
        order_item_objs = []
        for idx, order in enumerate(inserted_orders):
            if idx % 1000 == 0:
                self.print_progress(idx, len(inserted_orders), prefix='Order Items')
            
            # Guard against mismatched lists if previous orders existed (idempotency prevents this)
            if idx < len(order_items_data_per_order):
                items_data = order_items_data_per_order[idx]
                for data in items_data:
                    order_item_objs.append(OrderItem(
                        order=order,
                        item=data['item'],
                        quantity=data['qty'],
                        unit_price=data['price'],
                        unit_cost=data['cost'],
                        subtotal=data['subtotal']
                    ))
        self.print_progress(len(inserted_orders), len(inserted_orders), prefix='Order Items')
        
        self.stdout.write(f"Bulk inserting {len(order_item_objs)} OrderItems...")
        OrderItem.objects.bulk_create(order_item_objs, batch_size=5000)
        
        self.stdout.write("7. Generating Comments from Amazon Reviews...")
        comment_objs = []
        used_pairs = set()
        for idx, rev in enumerate(reviews):
            if idx % 500 == 0:
                self.print_progress(idx, len(reviews), prefix='Comments')
            
            asin = rev["parent_asin"]
            item = asin_to_item.get(asin)
            if not item:
                continue
                
            usr = random.choice(users_db)
            pair = (usr.id, item.id)
            if pair not in used_pairs:
                used_pairs.add(pair)
                body = rev["text"][:1000] if rev["text"] else "No review content"
                comment_objs.append(Comments(
                    user=usr,
                    item=item,
                    body=body,
                    rating=int(rev["rating"]),
                    likes=random.randint(0, 100)
                ))
                
        self.print_progress(len(reviews), len(reviews), prefix='Comments')
        Comments.objects.bulk_create(comment_objs, batch_size=1000)

        self.stdout.write(self.style.SUCCESS('Successfully generated the synthetic dataset!'))
