"""
apps/analytics/services/etl_service.py

ETL pipeline using openpyxl for memory-efficient streaming exports of sales and orders to Excel (.xlsx).
"""

import io
from datetime import datetime
from openpyxl import Workbook
from django.http import HttpResponse
from django.db.models import F, Case, When, Value, DecimalField, ExpressionWrapper
from django.db.models.functions import Round
from apps.orders.models import OrderItem


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
