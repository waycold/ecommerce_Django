"""
analytics/urls.py

Exclusive URL routes for the managerial data analytics module.
"""

from django.urls import path
from analytics.views import DashboardView, ExportSalesExcelView

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('export/excel/', ExportSalesExcelView.as_view(), name='export_excel'),
]
