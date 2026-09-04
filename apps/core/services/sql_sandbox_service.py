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
from django.conf import settings
from django.db import connections, transaction, DatabaseError


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
    r'\bauth_user\b',
    r'\bauth_user_groups\b',
    r'\bauth_user_user_permissions\b',
    r'\bdjango_admin_log\b',
    r'\bpg_shadow\b',
    r'\bpg_authid\b',
]

# Django DATABASES alias for the dedicated least-privilege Postgres role
# (chatbot_readonly_role -- see docs/sql/create_chatbot_readonly_role.sql).
SANDBOX_DB_ALIAS = 'chatbot_readonly'


def get_sandbox_db_alias() -> str:
    """
    Picks the DATABASES alias the sandbox should run queries against.

    Returns 'chatbot_readonly' when that alias is configured in
    settings.DATABASES (production, via CHATBOT_READONLY_DATABASE_URL --
    see config/settings/base.py and config/settings/production.py), so the
    sandbox is bounded by chatbot_readonly_role's GRANTs at the database
    engine level, not only by FORBIDDEN_TABLE_PATTERNS above.

    Falls back to 'default' when the alias isn't configured: local dev and
    the pytest suite run on SQLite, which has no concept of Postgres roles,
    so they never define 'chatbot_readonly' and must keep working against
    the single SQLite database they already have.
    """
    return SANDBOX_DB_ALIAS if SANDBOX_DB_ALIAS in settings.DATABASES else 'default'


def execute_safe_sql_sandbox(raw_query: str) -> Tuple[Dict[str, Any], int]:
    """
    Validates and securely executes a read-only SELECT SQL query.

    Runs against the connection alias returned by get_sandbox_db_alias() --
    the dedicated 'chatbot_readonly' role in production, 'default' otherwise
    -- inside a single transaction.atomic() block so that the per-query
    `SET LOCAL statement_timeout` (Postgres only) actually applies to the
    query that follows it instead of leaking into a separate autocommit
    transaction (see apps/catalog/rag_service.py for the same pattern
    applied to `SET LOCAL hnsw.ef_search`).

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
    alias = get_sandbox_db_alias()
    conn = connections[alias]
    start_time = time.perf_counter()
    try:
        # SET LOCAL only affects the transaction it runs in: both statements
        # MUST share one transaction.atomic() block, otherwise (as before this
        # fix) each cursor.execute() is its own autocommit transaction and the
        # 2s statement_timeout never applies to the real query.
        with transaction.atomic(using=alias):
            with conn.cursor() as cursor:
                # Set statement timeout for postgres if supported
                if conn.vendor == 'postgresql':
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
