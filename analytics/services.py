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
import pandas as pd

from django.db.models import Sum, Count, F, Q
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
    Pipeline de Extracción, Transformación y Carga (ETL) utilizando Pandas.
    1. Extracción: Consulta la base de datos uniendo Órdenes y Detalles de Órdenes.
    2. Transformación: Limpia tipos de datos, calcula métricas de margen en Pandas y formatea columnas.
    3. Carga: Genera un archivo binario `.xlsx` optimizado para Business Intelligence (PowerBI / Tableau).

    Returns:
        HttpResponse: Respuesta HTTP estructurada para descarga automática de Excel.
    """
    # 1. EXTRACCIÓN (Extraction): Consulta optimizada mediante select_related / values
    sales_queryset = OrderItem.objects.all().values(
        'id',
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
        'subtotal'
    )

    # 2. TRANSFORMACIÓN (Transformation): Carga en DataFrame de Pandas
    df = pd.DataFrame(list(sales_queryset))

    if not df.empty:
        # Renombrar columnas para formato estándar de Business Intelligence
        column_mapping = {
            'id': 'ID Detalle',
            'order__id': 'ID Orden',
            'order__ordered_date': 'Fecha Orden',
            'order__status': 'Estado Orden',
            'order__payment_method': 'Método Pago',
            'order__user__username': 'Cliente',
            'item__title': 'Producto',
            'item__category__name': 'Categoría',
            'quantity': 'Cantidad',
            'unit_price': 'Precio Unitario Histórico',
            'unit_cost': 'Costo Unitario Histórico',
            'subtotal': 'Subtotal ($)'
        }
        df.rename(columns=column_mapping, inplace=True)

        # Formatear la fecha (eliminar zona horaria para compatibilidad con Excel)
        if 'Fecha Orden' in df.columns and pd.notnull(df['Fecha Orden']).any():
            df['Fecha Orden'] = pd.to_datetime(df['Fecha Orden']).dt.tz_localize(None)
            df['Fecha Orden'] = df['Fecha Orden'].dt.strftime('%Y-%m-%d %H:%M:%S')

        # Manejo de valores nulos o categóricos vacíos
        df['Categoría'] = df['Categoría'].fillna('Sin Categoría')
        df['Cliente'] = df['Cliente'].fillna('Invitado/Anónimo')

        # Cálculo de métricas avanzadas en Pandas (Margen de Ganancia)
        df['Costo Total'] = df['Costo Unitario Histórico'] * df['Cantidad']
        df['Ganancia Neta ($)'] = df['Subtotal ($)'] - df['Costo Total']
        df['Margen (%)'] = ((df['Ganancia Neta ($)'] / df['Subtotal ($)']) * 100).round(2).fillna(0.0)

        # Reordenar columnas lógicamente
        ordered_cols = [
            'ID Orden', 'Fecha Orden', 'Estado Orden', 'Método Pago', 'Cliente',
            'Producto', 'Categoría', 'Cantidad', 'Precio Unitario Histórico',
            'Costo Unitario Histórico', 'Subtotal ($)', 'Ganancia Neta ($)', 'Margen (%)'
        ]
        df = df[[col for col in ordered_cols if col in df.columns]]
    else:
        # DataFrame vacío estructurado si no hay datos
        df = pd.DataFrame(columns=[
            'ID Orden', 'Fecha Orden', 'Estado Orden', 'Método Pago', 'Cliente',
            'Producto', 'Categoría', 'Cantidad', 'Precio Unitario Histórico',
            'Costo Unitario Histórico', 'Subtotal ($)', 'Ganancia Neta ($)', 'Margen (%)'
        ])

    # 3. CARGA (Load): Exportación a flujo binario en memoria usando openpyxl
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Reporte_Ventas_ETL', index=False)

    excel_buffer.seek(0)

    # Generación de la respuesta HTTP para descarga de archivo
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
