"""
analytics/views.py

Capa de Presentación Web para el módulo de Analytics.
Contiene exclusivamente la lógica de recepción de solicitudes HTTP,
control de permisos y renderizado de respuestas. La lógica de negocio y ETL
está delegada a analytics.services.
"""

from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required

# Importación de servicios desacoplados
from analytics.services import get_dashboard_kpis, export_sales_to_excel


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class DashboardView(View):
    """
    Vista principal del Dashboard Gerencial.
    Restringida de forma estricta a usuarios administradores (staff / superusers).
    Muestra KPIs en tiempo real y el Top 3 de productos más vendidos.
    """
    template_name = 'analytics/dashboard.html'

    def get(self, request):
        # Invocación del servicio desacoplado de procesamiento de datos
        context = get_dashboard_kpis()
        return render(request, self.template_name, context)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class ExportSalesExcelView(View):
    """
    Endpoint de exportación de datos ETL a formato Excel (.xlsx).
    Restringido a administradores. Invoca la canalización Pandas en services.py.
    """

    def get(self, request):
        # Invocación del pipeline ETL en Pandas para descarga automática de Excel
        return export_sales_to_excel()
