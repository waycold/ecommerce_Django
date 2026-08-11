"""
analytics/views.py

Web Presentation Layer for the Analytics module.
Contains exclusively the logic for receiving HTTP requests,
permission control, and response rendering. Business logic and ETL
are delegated to analytics.services.
"""

from django.views import View
from django.shortcuts import render
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required

# Decoupled services imports
from analytics.services import get_dashboard_kpis, export_sales_to_excel


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class DashboardView(View):
    """
    Main Managerial Dashboard view.
    Strictly restricted to admin users (staff / superusers).
    Displays real-time KPIs and the Top 3 best-selling products.
    """
    template_name = 'analytics/dashboard.html'

    def get(self, request):
        # Invoke decoupled data processing service
        context = get_dashboard_kpis()
        return render(request, self.template_name, context)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class ExportSalesExcelView(View):
    """
    ETL data export endpoint to Excel format (.xlsx).
    Restricted to admins. Invokes the Pandas pipeline in services.py.
    """

    def get(self, request):
        # Invoke the ETL pipeline in Pandas for automatic Excel download
        return export_sales_to_excel()

