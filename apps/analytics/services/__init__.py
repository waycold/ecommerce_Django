"""
apps.analytics.services package initialization.
Exports all domain services across KPIs, Forecasting, ETL, Data Simulation, and AI Internal Contracts.
"""

from .kpi_service import (
    get_dashboard_kpis,
    get_internal_metrics_service,
    _format_top_products,
    _format_top_product_star,
)
from .forecast_service import get_forecast_data
from .etl_service import export_sales_to_excel
from .generator_service import (
    is_production_environment,
    get_config_filepath,
    get_simulator_config,
    save_simulator_config,
    get_generation_progress,
    update_progress,
    generate_dataset_pipeline,
    start_async_dataset_generation,
    GENERATION_LOCK,
    GENERATION_STATUS,
    CATEGORIES_LIST,
)

__all__ = [
    'get_dashboard_kpis',
    'get_internal_metrics_service',
    '_format_top_products',
    '_format_top_product_star',
    'get_forecast_data',
    'export_sales_to_excel',
    'is_production_environment',
    'get_config_filepath',
    'get_simulator_config',
    'save_simulator_config',
    'get_generation_progress',
    'update_progress',
    'generate_dataset_pipeline',
    'start_async_dataset_generation',
    'GENERATION_LOCK',
    'GENERATION_STATUS',
    'CATEGORIES_LIST',
]
