import sys
import math
import random
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from faker import Faker
from product.models import (
    OrderItem, Order, Comments, Item, Category, Brand, Supplier, Profile,
    OrderStatus, PaymentMethod
)

class Command(BaseCommand):
    help = 'Generates complex synthetic dataset for analytics'

    def print_progress(self, current, total, bar_length=40, prefix='Progress'):
        progress = float(current) / total if total > 0 else 1
        arrow = '-' * int(round(progress * bar_length) - 1) + '>'
        spaces = ' ' * (bar_length - len(arrow))
        sys.stdout.write(f'\r{prefix}: [{arrow}{spaces}] {int(round(progress * 100))}% ({current}/{total})')
        sys.stdout.flush()
        if current >= total:
            sys.stdout.write('\n')

    def handle(self, *args, **kwargs):
        import json
        import os
        random.seed(42)
        Faker.seed(42)
        fake = Faker(['es_ES', 'es_AR'])

        # Load configs from data folder
        data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
        templates_path = os.path.join(data_dir, 'product_templates.json')
        weights_path = os.path.join(data_dir, 'weights_config.json')

        with open(templates_path, 'r', encoding='utf-8') as f:
            product_templates = json.load(f)
            
        with open(weights_path, 'r', encoding='utf-8') as f:
            weights_config = json.load(f)

        # Calculate boundaries and weights for product tiers based on N=2000 items
        tier_configs = weights_config["product_tiers"]
        t1_pct = tier_configs["tier_1_best_sellers"]["percentage_of_catalog"]
        t2_pct = tier_configs["tier_2_steady_sellers"]["percentage_of_catalog"]
        t3_pct = tier_configs["tier_3_slow_sellers"]["percentage_of_catalog"]
        
        t1_count = int(2000 * t1_pct)
        t2_count = int(2000 * t2_pct)
        t3_count = int(2000 * t3_pct)
        
        t1_w = tier_configs["tier_1_best_sellers"]["sales_weight"] / max(1, t1_count)
        t2_w = tier_configs["tier_2_steady_sellers"]["sales_weight"] / max(1, t2_count)
        t3_w = tier_configs["tier_3_slow_sellers"]["sales_weight"] / max(1, t3_count)
        t4_w = tier_configs["tier_4_long_tail"]["sales_weight"] / max(1, 2000 - t1_count - t2_count - t3_count)

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
        categories = ['Electronics', 'Home & Furniture', 'Clothing & Accessories', 'Sports', 'Toys', 
                      'Health & Beauty', 'Automotive', 'Tools', 'Books', 'Video Games',
                      'Food & Beverage', 'Pets', 'Jewelry', 'Office', 'Baby']
        Category.objects.bulk_create([Category(name=name) for name in categories])
        cats_db = list(Category.objects.all())
        cat_probs = [weights_config["category_weights"].get(cat.name, 1.0) for cat in cats_db]
        
        self.stdout.write("3. Generating Brands and Suppliers (Zipf distribution)...")
        # Extract unique brand names from templates
        unique_brand_names = set()
        for cat_name, data in product_templates.items():
            unique_brand_names.update(data["brands"])
            
        Brand.objects.bulk_create([Brand(name=name) for name in sorted(unique_brand_names)])
        brands_by_name = {b.name: b for b in Brand.objects.all()}
        
        num_suppliers = 50
        countries_pool = ['Argentina'] * 7 + ['Chile', 'Brasil', 'USA', 'China']
        Supplier.objects.bulk_create([Supplier(name=fake.company(), country=random.choice(countries_pool)) for _ in range(num_suppliers)])
        suppliers_db = list(Supplier.objects.all())
        
        def zipf_weights(n, alpha=1.5):
            return [1.0 / (i**alpha) for i in range(1, n+1)]
            
        supplier_weights = zipf_weights(num_suppliers)
        local_brand_weights = zipf_weights(15, alpha=1.2) # Zipf weights for 15 brands in each category

        self.stdout.write("4. Generating 2000 Items...")
        item_objs = []
        for i in range(2000):
            if i % 100 == 0:
                self.print_progress(i, 2000, prefix='Items')
            price = round(math.exp(random.gauss(8, 1.5)), 2)
            price = max(100.0, min(price, 500000.0))
            cost = round(price * random.uniform(0.45, 0.80), 2)
            
            cat = random.choices(cats_db, weights=cat_probs)[0]
            sup = random.choices(suppliers_db, weights=supplier_weights)[0]
            
            # Select semantically matched brand, adjective, and noun from category templates
            cat_templates = product_templates.get(cat.name, {
                "brands": ["Generic"],
                "adjectives": ["Premium"],
                "nouns": ["Product"]
            })
            
            b_list = cat_templates.get("brands", ["Generic"])
            adj_list = cat_templates.get("adjectives", ["Premium"])
            noun_list = cat_templates.get("nouns", ["Product"])
            
            # Use Zipf weights to select the brand (e.g. popular brands are chosen more often)
            brand_weights = local_brand_weights[:len(b_list)]
            sum_w = sum(brand_weights)
            brand_weights = [w / sum_w for w in brand_weights]
            
            brand_name = random.choices(b_list, weights=brand_weights)[0]
            brand = brands_by_name.get(brand_name)
            
            t_adj = random.choice(adj_list)
            t_noun = random.choice(noun_list)
            title = f"{brand_name} {t_adj} {t_noun}"
            
            item_objs.append(Item(
                title=title[:100],
                description=fake.text(max_nb_chars=200),
                price=price,
                cost=cost,
                stock=random.randint(0, 500),
                minimum_stock=random.randint(10, 50),
                category=cat,
                supplier=sup,
                brand=brand,
                slug=f"item-{i}-{random.randint(1000, 9999)}",
                is_active=random.choices([True, False], weights=[0.95, 0.05])[0]
            ))
        self.print_progress(2000, 2000, prefix='Items')
        Item.objects.bulk_create(item_objs, batch_size=500)
        items_db = list(Item.objects.order_by('id'))
        
        # Build weight list corresponding to items_db order
        items_sales_weights = []
        for idx, item in enumerate(items_db):
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
        
        # Build dictionary for quick lookup to avoid DB queries per user
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
        
        self.stdout.write("7. Generating Comments...")
        comment_objs = []
        used_pairs = set()
        for i in range(3000):
            if i % 500 == 0:
                self.print_progress(i, 3000, prefix='Comments')
            attempts = 0
            while attempts < 10:
                usr = random.choice(users_db)
                itm = random.choice(items_db)
                pair = (usr.id, itm.id)
                if pair not in used_pairs:
                    used_pairs.add(pair)
                    comment_objs.append(Comments(
                        user=usr,
                        item=itm,
                        body=fake.paragraph(nb_sentences=3),
                        rating=random.randint(1, 5),
                        likes=random.randint(0, 100)
                    ))
                    break
                attempts += 1
        self.print_progress(3000, 3000, prefix='Comments')
        Comments.objects.bulk_create(comment_objs, batch_size=1000)

        self.stdout.write(self.style.SUCCESS('Successfully generated the complex synthetic dataset!'))
