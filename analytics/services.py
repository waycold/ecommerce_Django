"""
analytics/services.py

Services and Data Processing Layer (Data Engineering & Business Logic).
Strict separation of concerns: this module abstracts all complex ORM queries,
statistical aggregations, and the ETL pipeline powered by openpyxl for BI exports.

Designed with a modular architecture to support future asynchronous executions
(Celery/Redis) and Machine Learning models (Market Basket Analysis, Demand Forecasting).
"""

import io
from datetime import datetime
from openpyxl import Workbook

from django.db.models import Sum, Count, F, Q, DecimalField, Case, When, Value, ExpressionWrapper
from django.db.models.functions import Round
from django.utils import timezone
from django.http import HttpResponse

# Importación de modelos desde la aplicación del e-commerce
from product.models import Order, OrderItem, Item, OrderStatus


def get_dashboard_kpis() -> dict:
    """
    Calculates key performance indicators (KPIs) in real-time for the Managerial Dashboard.
    Uses optimized Django ORM queries (aggregate/annotate) to minimize
    database load.

    Returns:
        dict: Structured dictionary with sales metrics, abandoned carts, and top products.
    """
    now = timezone.now()
    current_year = now.year
    current_month = now.month

    # 1. Total Revenue of the current month (Paid/Shipped/Delivered orders)
    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    
    monthly_revenue_agg = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).aggregate(
        total_revenue=Sum('total')
    )
    monthly_revenue = monthly_revenue_agg['total_revenue'] or 0.0

    # 2. Abandoned Carts count (Orders in PENDING status)
    abandoned_carts_count = Order.objects.filter(
        status=OrderStatus.PENDING
    ).count()

    # 3. Top 3 Best-Selling Products (by quantity in completed orders)
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
    ).order_by('-total_units_sold')[:3]

    top_products = list(top_products_qs)

    # Structured return for the presentation layer (views.py)
    return {
        'current_month_name': now.strftime('%B %Y'),
        'monthly_revenue': float(monthly_revenue),
        'abandoned_carts_count': abandoned_carts_count,
        'top_products': top_products,
        'top_product_star': top_products[0] if top_products else None,
    }


def export_sales_to_excel() -> HttpResponse:
    """
    Extraction, Transformation, and Loading (ETL) pipeline using a SQL-First approach.
    1. Extract & Transform: Performs mathematical calculations directly in the database engine
       (PostgreSQL/SQLite) using Django annotations.
    2. Load: Generates the Excel file (.xlsx) efficiently in memory using openpyxl in
       write-only mode to prevent worker timeouts and OOM errors on Render.

    Returns:
        HttpResponse: Structured HTTP response for automatic Excel download.
    """
    # 1. EXTRACTION AND TRANSFORMATION (SQL-First)
    # Calculate Total Cost, Net Profit, and Margin directly in the database engine
    cost_total_expr = ExpressionWrapper(
        F('unit_cost') * F('quantity'),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    
    net_profit_expr = ExpressionWrapper(
        F('subtotal') - (F('unit_cost') * F('quantity')),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    
    # Safe handling of division by zero for the margin
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

    # 2. LOAD
    # openpyxl with write_only=True writes directly to the in-memory ZIP file,
    # without building the entire document structure in Python memory.
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title='Sales_Report_ETL')
    
    # Headers
    headers = [
        'Order ID', 'Order Date', 'Order Status', 'Payment Method', 'Customer',
        'Product', 'Category', 'Quantity', 'Historical Unit Price',
        'Historical Unit Cost', 'Subtotal ($)', 'Net Profit ($)', 'Margin (%)'
    ]
    ws.append(headers)

    # We use iterator to process in chunks of 2000 records,
    # freeing up memory between each processed block.
    for row in sales_queryset.iterator(chunk_size=2000):
        # Convert row tuple to list to modify null values / dates
        row_list = list(row)
        
        # Order Date: Remove timezone for Excel compatibility
        if row_list[1]:
            row_list[1] = row_list[1].replace(tzinfo=None)
            
        # Null values in categorical fields
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
# FUTURE EXTENSIONS & STUBS SECTION (Machine Learning & Asynchronous Tasks)
# ==============================================================================

class AdvancedAnalyticsService:
    """
    Reserved class for future integration of Data Science algorithms,
    Machine Learning, and background tasks (Celery / Redis / Scikit-learn).
    """

    @staticmethod
    def run_market_basket_analysis():
        """
        [FUTURE] Apriori / FP-Growth algorithm to detect frequent itemsets/purchasing patterns
        (Product association in shopping carts).
        """
        pass

    @staticmethod
    def predict_sales_demand(periods_days: int = 30):
        """
        [FUTURE] Time-series forecasting algorithm (Prophet / ARIMA)
        for inventory demand estimation.
        """
        pass