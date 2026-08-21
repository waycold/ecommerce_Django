"""
analytics/urls.py

Exclusive URL routes for the managerial data analytics module.
"""

from django.urls import path
from analytics.views import (
    DashboardView,
    ForecastView,
    SimulatorView,
    AnalyticsChatView,
    ExportSalesExcelView,
    SimulatorConfigView,
    GenerateDatasetView,
    GenerationProgressView
)

app_name = 'analytics'

urlpatterns = [
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('forecast/', ForecastView.as_view(), name='forecast'),
    path('simulator/', SimulatorView.as_view(), name='simulator'),
    path('chat/', AnalyticsChatView.as_view(), name='ai_chat'),
    path('export/excel/', ExportSalesExcelView.as_view(), name='export_excel'),
    path('api/simulator-config/', SimulatorConfigView.as_view(), name='simulator_config'),
    path('api/generate-dataset/', GenerateDatasetView.as_view(), name='generate_dataset'),
    path('api/generation-progress/', GenerationProgressView.as_view(), name='generation_progress'),
]
