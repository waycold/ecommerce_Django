"""
apps.core.services package initialization.
"""

from .sql_sandbox_service import execute_safe_sql_sandbox

__all__ = [
    'execute_safe_sql_sandbox',
]
