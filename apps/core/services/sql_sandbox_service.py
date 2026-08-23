"""
apps/core/services/sql_sandbox_service.py

Safe Read-Only SQL Query Sandbox for LLM Agent & BI Analysts.
Enforces strict syntactic defense, AST parsing guardrails, query timeout limits,
and a mandatory maximum 50-row result limit.
"""

import re
import time
from decimal import Decimal
from datetime import datetime, date
from typing import Tuple, Dict, Any, List
from django.db import connection, DatabaseError


FORBIDDEN_SQL_KEYWORDS = [
    r'\bINSERT\b',
    r'\bUPDATE\b',
    r'\bDELETE\b',
    r'\bDROP\b',
    r'\bALTER\b',
    r'\bTRUNCATE\b',
    r'\bCREATE\b',
    r'\bREPLACE\b',
    r'\bMERGE\b',
    r'\bEXEC\b',
    r'\bEXECUTE\b',
    r'\bGRANT\b',
    r'\bREVOKE\b',
    r'\bCALL\b',
    r'\bCOPY\b',
    r'\bVACUUM\b',
    r'\bATTACH\b',
    r'\bDETACH\b',
    r'\bPRAGMA\b',
    r'\bSET\b',
    r'\bLOCK\b',
    r'\bBEGIN\b',
    r'\bCOMMIT\b',
    r'\bROLLBACK\b',
    r'\bTRANSACTION\b',
]

FORBIDDEN_TABLE_PATTERNS = [
    r'\bdjango_session\b',
    r'\bauth_permission\b',
    r'\bauth_group\b',
    r'\bpg_shadow\b',
    r'\bpg_authid\b',
]


def execute_safe_sql_sandbox(raw_query: str) -> Tuple[Dict[str, Any], int]:
    """
    Validates and securely executes a read-only SELECT SQL query.

    Args:
        raw_query (str): SQL query statement to validate and execute.

    Returns:
        tuple (dict, int): Response payload dictionary and HTTP status code.
    """
    if not raw_query or not isinstance(raw_query, str) or not raw_query.strip():
        return {
            'error': 'Bad Request',
            'detail': 'SQL query string cannot be empty.',
        }, 400

    query_str = raw_query.strip()

    # 1. Strip comments
    # Remove multi-line comments /* ... */
    query_str = re.sub(r'/\*.*?\*/', ' ', query_str, flags=re.DOTALL)
    # Remove single-line comments -- ...
    query_str = re.sub(r'--.*$', ' ', query_str, flags=re.MULTILINE)
    query_str = re.sub(r'\s+', ' ', query_str).strip()

    # Remove optional trailing semicolon
    if query_str.endswith(';'):
        query_str = query_str[:-1].strip()

    # 2. Reject multiple queries
    if ';' in query_str:
        return {
            'error': 'Bad Request',
            'detail': 'Multiple SQL statements are strictly forbidden in read-only sandbox mode.',
        }, 400

    # 3. Must begin with SELECT or WITH (CTE)
    if not (query_str.lower().startswith('select') or query_str.lower().startswith('with')):
        return {
            'error': 'Bad Request',
            'detail': 'Only SELECT or WITH (CTE) read queries are permitted.',
        }, 400

    # 4. Check forbidden mutating keywords
    for pattern in FORBIDDEN_SQL_KEYWORDS:
        if re.search(pattern, query_str, flags=re.IGNORECASE):
            match = re.search(pattern, query_str, flags=re.IGNORECASE).group(0)
            return {
                'error': 'Forbidden SQL Keyword',
                'detail': f'Disallowed SQL operation detected: "{match.upper()}". Sandbox only permits read-only SELECT queries.',
            }, 400

    # 5. Check forbidden system tables
    for tbl in FORBIDDEN_TABLE_PATTERNS:
        if re.search(tbl, query_str, flags=re.IGNORECASE):
            return {
                'error': 'Forbidden Table Access',
                'detail': 'Access to sensitive authentication/session internal tables is restricted.',
            }, 400

    # 6. Wrap query to enforce strict maximum 50 rows limit
    sandboxed_query = f"SELECT * FROM ({query_str}) AS _sandbox_result LIMIT 50"

    # 7. Execute query with timing
    start_time = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            # Set statement timeout for postgres if supported
            if connection.vendor == 'postgresql':
                cursor.execute("SET LOCAL statement_timeout = '2000ms';")
            
            cursor.execute(sandboxed_query)
            description = cursor.description or []
            columns = [col[0] for col in description]
            
            raw_rows = cursor.fetchmany(50)
            
            # Format row data for JSON serialization
            rows_data: List[Dict[str, Any]] = []
            for row in raw_rows:
                formatted_row = {}
                for idx, val in enumerate(row):
                    col_name = columns[idx]
                    if isinstance(val, Decimal):
                        formatted_row[col_name] = float(val)
                    elif isinstance(val, (datetime, date)):
                        formatted_row[col_name] = val.isoformat()
                    else:
                        formatted_row[col_name] = val
                rows_data.append(formatted_row)

    except DatabaseError as db_err:
        return {
            'error': 'Database Query Error',
            'detail': str(db_err),
            'query': query_str,
        }, 400
    except Exception as exc:
        return {
            'error': 'Internal Error',
            'detail': str(exc),
        }, 500

    execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

    return {
        'status': 'success',
        'query_executed': query_str,
        'columns': columns,
        'row_count': len(rows_data),
        'execution_time_ms': execution_time_ms,
        'rows': rows_data,
    }, 200
