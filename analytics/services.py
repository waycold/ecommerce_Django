"""
analytics/services.py

Capa de Servicios y Procesamiento de Datos (Data Engineering & Business Logic).
Separación estricta de responsabilidades: este módulo abstrae todas las consultas ORM complejas,
agregaciones estadísticas y el pipeline de ETL impulsado por Pandas para exportación a BI.

Diseñado con arquitectura modular para soportar futuras ejecuciones asíncronas
(Celery/Redis) y modelos de Machine Learning (Market Basket Analysis, Predicción de Demanda).
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
    Calcula en tiempo real las métricas clave de rendimiento (KPIs) para el Dashboard Gerencial.
    Utiliza consultas optimizadas del ORM de Django (aggregate/annotate) para minimizar
    la carga en la base de datos.

    Returns:
        dict: Diccionario estructurado con métricas de ventas, carritos abandonados y top productos.
    """
    now = timezone.now()
    current_year = now.year
    current_month = now.month

    # 1. Ingresos Totales (Revenue) del mes en curso (Órdenes pagadas/enviadas/entregadas)
    paid_statuses = [OrderStatus.PAID, OrderStatus.SHIPPED, OrderStatus.DELIVERED]
    
    monthly_revenue_agg = Order.objects.filter(
        status__in=paid_statuses,
        ordered_date__year=current_year,
        ordered_date__month=current_month
    ).aggregate(
        total_revenue=Sum('total')
    )
    monthly_revenue = monthly_revenue_agg['total_revenue'] or 0.0

    # 2. Cantidad de Carritos Abandonados (Órdenes en estado PENDING)
    abandoned_carts_count = Order.objects.filter(
        status=OrderStatus.PENDING
    ).count()

    # 3. Top 3 de Productos Más Vendidos (por cantidad en órdenes completadas)
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

    # Retorno estructurado para la capa de presentación (views.py)
    return {
        'current_month_name': now.strftime('%B %Y'),
        'monthly_revenue': float(monthly_revenue),
        'abandoned_carts_count': abandoned_carts_count,
        'top_products': top_products,
        'top_product_star': top_products[0] if top_products else None,
    }


def export_sales_to_excel() -> HttpResponse:
    """
    Pipeline de Extracción, Transformación y Carga (ETL) utilizando un enfoque SQL-First.
    1. Extracción y Transformación: Realiza los cálculos matemáticos directamente en el motor 
       de base de datos (PostgreSQL/SQLite) mediante annotations de Django.
    2. Carga: Genera el archivo Excel (.xlsx) de manera optimizada y eficiente en memoria 
       usando openpyxl en modo write-only para evitar WORKER TIMEOUT y OOM en Render.

    Returns:
        HttpResponse: Respuesta HTTP estructurada para descarga automática de Excel.
    """
    # 1. EXTRACCIÓN Y TRANSFORMACIÓN (SQL-First)
    # Calculamos Costo Total, Ganancia Neta y Margen directamente en el motor de base de datos
    cost_total_expr = ExpressionWrapper(
        F('unit_cost') * F('quantity'),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    
    net_profit_expr = ExpressionWrapper(
        F('subtotal') - (F('unit_cost') * F('quantity')),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )
    
    # Manejo seguro de división por cero para el margen
    margin_expr = Case(
        When(subtotal__gt=0, then=Round((net_profit_expr / F('subtotal')) * 100, 2)),
        default=Value(0.0),
        output_field=DecimalField(max_digits=5, decimal_places=2)
    )

    sales_queryset = OrderItem.objects.annotate(
        costo_total=cost_total_expr,
        ganancia_neta=net_profit_expr,
        margen=margin_expr
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
        'ganancia_neta',
        'margen'
    )

    # 2. CARGA (Load)
    # openpyxl en modo write_only=True escribe directamente en el archivo ZIP en memoria,
    # sin construir la estructura del documento en memoria de Python.
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(title='Reporte_Ventas_ETL')
    
    # Headers
    headers = [
        'ID Orden', 'Fecha Orden', 'Estado Orden', 'Método Pago', 'Cliente',
        'Producto', 'Categoría', 'Cantidad', 'Precio Unitario Histórico',
        'Costo Unitario Histórico', 'Subtotal ($)', 'Ganancia Neta ($)', 'Margen (%)'
    ]
    ws.append(headers)

    # Usamos iterator para procesar en bloques (chunks) de 2000 registros,
    # liberando memoria entre cada bloque procesado.
    for row in sales_queryset.iterator(chunk_size=2000):
        # Convertimos la tupla de row a lista para poder modificar los valores nulos/fechas
        row_list = list(row)
        
        # Fecha Orden: Remover zona horaria para compatibilidad con Excel
        if row_list[1]:
            row_list[1] = row_list[1].replace(tzinfo=None)
            
        # Valores nulos en campos categóricos
        if row_list[4] is None:
            row_list[4] = 'Invitado/Anónimo'
        if row_list[6] is None:
            row_list[6] = 'Sin Categoría'
            
        ws.append(row_list)
        
    excel_buffer = io.BytesIO()
    wb.save(excel_buffer)
    excel_buffer.seek(0)
    
    file_name = f"reporte_ventas_analytics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response = HttpResponse(
        excel_buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{file_name}"'
    return response


# ==============================================================================
# SECCIÓN STUBS Y EXTENSIONES FUTURAS (Machine Learning & Asynchronous Tasks)
# ==============================================================================

class AdvancedAnalyticsService:
    """
    Clase reservada para la integración futura de algoritmos de Data Science,
    Machine Learning y tareas en segundo plano (Celery / Redis / Scikit-learn).
    """

    @staticmethod
    def run_market_basket_analysis():
        """
        [FUTURO] Algoritmo Apriori / FP-Growth para detectar patrones de compra conjunta
        (Asociación de productos frecuentes en carrito).
        """
        pass

    @staticmethod
    def predict_sales_demand(periods_days: int = 30):
        """
        [FUTURO] Algoritmo de predicción de series temporales (Prophet / ARIMA)
        para estimación de demanda de inventario.
        """
        pass
