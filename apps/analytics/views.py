"""
apps/analytics/views.py

Web Presentation Layer & API Endpoints for the Analytics module.
Contains distinct views for Dashboard, Forecast & Trends, Data Simulator, and AI Chat Assistant.
"""

import json
from django.views import View
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.utils.decorators import method_decorator
from django.contrib.admin.views.decorators import staff_member_required

from apps.analytics.services import (
    get_dashboard_kpis,
    get_product_performance_series,
    export_sales_to_excel,
    get_forecast_data,
    get_simulator_config,
    save_simulator_config,
    start_async_dataset_generation,
    get_generation_progress,
)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class DashboardView(View):
    """
    Main Managerial Dashboard view.
    Renders real-time KPIs and Top products, including per-product cost/margin data
    computed directly in the same query that produces the Top 8 list (see kpi_service.py).
    """
    template_name = 'analytics/dashboard.html'

    def get(self, request):
        context = get_dashboard_kpis()
        return render(request, self.template_name, context)


AnalyticsDashboardView = DashboardView


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class ProductPerformanceView(View):
    """
    API endpoint powering the Dashboard's Top 8 table row-click detail panel:
    monthly revenue/units time series plus core product data for a single item.
    """
    def get(self, request, item_id):
        data = get_product_performance_series(item_id)
        if data is None:
            return JsonResponse({'status': 'error', 'message': 'Product not found.'}, status=404)
        return JsonResponse(data)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class ForecastView(View):
    """
    Forecast & Trends analytics view.
    Renders time-series sales predictions, seasonality, and category distribution.
    """
    template_name = 'analytics/forecast.html'

    def get(self, request):
        forecast_data = get_forecast_data()
        context = {
            'forecast_data': forecast_data,
            'forecast_data_json': json.dumps(forecast_data),
        }
        return render(request, self.template_name, context)


AnalyticsForecastView = ForecastView


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class SimulatorView(View):
    """
    Synthetic Data Simulator view.
    Renders sliders for JSON configuration attributes and dataset generator control.
    """
    template_name = 'analytics/simulator.html'

    def get(self, request):
        sim_config = get_simulator_config()
        context = {
            'simulator_config': sim_config,
            'simulator_config_json': json.dumps(sim_config),
        }
        return render(request, self.template_name, context)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class AnalyticsChatView(View):
    """
    AI Managerial Chat view.
    Renders conversational assistant interface for real-time analytics insights.
    """
    template_name = 'analytics/ai_chat.html'

    def get(self, request):
        return render(request, self.template_name)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class ExportSalesExcelView(View):
    """
    ETL data export endpoint to Excel format (.xlsx).
    """
    def get(self, request):
        return export_sales_to_excel()


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class SimulatorConfigView(View):
    """
    API endpoint for getting and updating dataset generation configuration weights.
    """
    def get(self, request):
        config = get_simulator_config()
        return JsonResponse(config)

    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8'))
            updated = save_simulator_config(body)
            return JsonResponse({'status': 'success', 'config': updated})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class GenerateDatasetView(View):
    """
    API endpoint for initiating asynchronous dataset generation with slider parameters.
    """
    def post(self, request):
        try:
            body = json.loads(request.body.decode('utf-8')) if request.body else {}
            config = body.get('config')
            seed = body.get('seed')
            if seed is not None:
                try:
                    seed = int(seed)
                except ValueError:
                    seed = None

            started = start_async_dataset_generation(config_override=config, seed=seed)
            if started:
                return JsonResponse({'status': 'started', 'message': 'Dataset generation engine initiated.'})
            else:
                return JsonResponse({'status': 'running', 'message': 'Dataset generation is already in progress.'}, status=409)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)


@method_decorator(staff_member_required(login_url='login'), name='dispatch')
class GenerationProgressView(View):
    """
    API endpoint for polling live dataset generation progress status and step logs.
    """
    def get(self, request):
        progress = get_generation_progress()
        return JsonResponse(progress)
