import os
import sys
import django
from django.db.models import Count, Sum, Max, Min, F, Q

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from product.models import Order, OrderItem, Item, Category, Brand, Supplier, Profile, Comments
from django.contrib.auth.models import User

def run_exhaustive_audit():
    print("--- EXHAUSTIVE DATASET AUDIT REPORT ---")
    
    # 1. Row Counts
    num_items = Item.objects.count()
    num_users = User.objects.exclude(is_superuser=True).count()
    num_orders = Order.objects.count()
    num_order_items = OrderItem.objects.count()
    num_comments = Comments.objects.count()
    num_categories = Category.objects.count()
    
    print(f"\n1. TABLE ROW COUNTS:")
    print(f"Items: {num_items} (Expected ~2100-2200) -> {'PASS' if 2000 <= num_items <= 2500 else 'FAIL'}")
    print(f"Users: {num_users} (Expected 5000) -> {'PASS' if num_users == 5000 else 'FAIL'}")
    print(f"Orders: {num_orders} (Expected ~4000-6500) -> {'PASS' if 4000 <= num_orders <= 6500 else 'FAIL'}")
    print(f"Order Items: {num_order_items} (Expected ~12000-20000) -> {'PASS' if 10000 <= num_order_items <= 25000 else 'FAIL'}")
    print(f"Comments/Reviews: {num_comments} (Expected > 0) -> {'PASS' if num_comments > 0 else 'FAIL'}")
    
    # 2. User Activity (Conversion Funnel)
    users_with_orders = Order.objects.values('user').distinct().count()
    inactive_users = num_users - users_with_orders
    inactive_pct = (inactive_users / num_users) * 100 if num_users else 0
    print(f"\n2. USER ACTIVITY (CONVERSION FUNNEL):")
    print(f"Inactive Users (0 orders): {inactive_users} ({inactive_pct:.1f}%)")
    print(f"Expected Inactive: ~25% -> {'PASS' if 20 <= inactive_pct <= 30 else 'FAIL'}")
    
    # 3. Registration vs Order Dates
    print(f"\n3. REGISTRATION VS ORDER DATES:")
    invalid_dates = Order.objects.filter(ordered_date__lt=F('user__date_joined')).count()
    print(f"Orders placed before user registered: {invalid_dates}")
    print(f"Expected: 0 -> {'PASS' if invalid_dates == 0 else 'FAIL'}")
    
    # 4. Order Timeline (Should span max 730 days / 2 years)
    print(f"\n4. ORDER TIMELINE:")
    first_order = Order.objects.aggregate(Min('ordered_date'))['ordered_date__min']
    last_order = Order.objects.aggregate(Max('ordered_date'))['ordered_date__max']
    from django.utils import timezone
    now = timezone.now()
    if first_order and last_order:
        days_span = (last_order - first_order).days
        days_since_first = (now - first_order).days
        print(f"First order: {first_order.strftime('%Y-%m-%d')} ({days_since_first} days ago)")
        print(f"Last order: {last_order.strftime('%Y-%m-%d')}")
        print(f"Total span: {days_span} days")
        print(f"Expected span <= 730 days: {'PASS' if days_since_first <= 735 else 'FAIL'}")
    else:
        print("No orders found!")
        
    # 5. Pricing and Discounts
    print(f"\n5. PRICING & DISCOUNTS LOGIC:")
    invalid_totals = 0
    invalid_discounts = 0
    sample_orders = Order.objects.all()[:1000]
    for o in sample_orders:
        subtotal_sum = sum(oi.subtotal for oi in o.items.all())
        expected_total = max(0.0, float(subtotal_sum) + float(o.shipping_cost) - float(o.discount))
        if abs(float(o.total) - expected_total) > 0.05:
            invalid_totals += 1
            
        if o.discount_code in ['DESC10', 'PROMO10']:
            expected_discount = round(float(subtotal_sum) * 0.10, 2)
            if abs(float(o.discount) - expected_discount) > 0.05:
                invalid_discounts += 1
                
    print(f"Sampled 1000 orders for total/subtotal verification.")
    print(f"Orders with invalid Total formula: {invalid_totals} -> {'PASS' if invalid_totals == 0 else 'FAIL'}")
    print(f"Orders with invalid Discount formula: {invalid_discounts} -> {'PASS' if invalid_discounts == 0 else 'FAIL'}")
    
    # 6. Inventory Constraints
    print(f"\n6. INVENTORY CONSTRAINTS:")
    negative_stock = Item.objects.filter(stock__lt=0).count()
    print(f"Items with negative stock: {negative_stock}")
    print(f"Expected: 0 -> {'PASS' if negative_stock == 0 else 'FAIL'}")
    
    # 7. Reviews Coverage
    print(f"\n7. REVIEWS & COMMENTS COVERAGE:")
    categories = Category.objects.all()
    categories_without_reviews = 0
    for cat in categories:
        has_reviews = Comments.objects.filter(item__category=cat).exists()
        if not has_reviews:
            # Check if category even has items
            if Item.objects.filter(category=cat).exists():
                categories_without_reviews += 1
                
    print(f"Categories with items but 0 reviews: {categories_without_reviews}")
    print(f"Expected: 0 -> {'PASS' if categories_without_reviews == 0 else 'FAIL'}")
    
    print("\n--- AUDIT COMPLETE ---")

if __name__ == '__main__':
    run_exhaustive_audit()
