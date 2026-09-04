-- Dedicated, least-privilege Postgres role for the Chatbot-Engine-Gateway's read path.
-- Run this manually against the target database when provisioning the chatbot's DB access —
-- it is NOT applied automatically by Django migrations (role/grant management is
-- instance-level, not schema-level, and the password must never be committed to git).
--
-- Replace the password placeholder with a real, randomly generated secret before running,
-- and store that secret in your deployment platform's environment variables (e.g. Render),
-- never in this file or in git history.
--
-- Originally applied to the production Neon project ("Ecommerce database" / dark-tooth-59531599,
-- database `neondb`) on 2026-08-27 with a narrower GRANT set. This file is kept as the runbook
-- for (re-)provisioning the role anywhere (a new environment, a rotated password, a staging
-- database).
--
-- Applying this to the EXISTING production role (to pick up the widened GRANTs from the audit
-- below): skip the CREATE ROLE line -- the role already exists -- and run everything from the
-- first GRANT CONNECT onward. GRANT is additive and safe to re-run against an existing role;
-- only CREATE ROLE would fail with "role already exists".
--
-- Audit (Fase 0, Tarea 2a): the GRANTs below are the *minimum* verified against every raw-SQL
-- query the sandbox (apps/core/services/sql_sandbox_service.py::execute_safe_sql_sandbox, exposed
-- via POST /api/v1/internal/query/raw-read/) is actually asked to run today, across its entire
-- test coverage:
--   - tests/test_database_ai_endpoints.py::TestModule7SQLSandbox::test_valid_select_query_executes_successfully
--       SELECT id, title, price, stock FROM product_item WHERE is_active = 1 ...
--   - tests/test_database_ai_endpoints.py::TestModule7SQLSandbox::test_cte_with_query_allowed
--       WITH items_cte AS (SELECT id, title, price FROM product_item) SELECT * FROM items_cte ...
--   - tests/test_ai_engine_internal_contracts.py::...::test_sql_sandbox_safe_select
--       SELECT title, price, stock FROM product_item ORDER BY price DESC;
--   - tests/test_chatbot_emulation_postman.py::...::test_query_9_safe_sql_sandbox (+ the
--     sequential-pipeline test right after it)
--       SELECT status, count(*) as count FROM product_order GROUP BY status
--   - apps/core/internal_views.py::raw_sql_sandbox_view's own docstring example
--       SELECT category_id, COUNT(*) FROM product_item GROUP BY category_id;
-- No exercised query touches product_comments or product_supplier, so this GRANT set does not
-- add them -- widen it (and this comment) again if/when a real query needs them, following the
-- same "verify against a real test first" discipline instead of granting speculatively.

CREATE ROLE chatbot_readonly_role LOGIN PASSWORD '<REPLACE_WITH_GENERATED_SECRET>';
GRANT CONNECT ON DATABASE neondb TO chatbot_readonly_role;
GRANT USAGE ON SCHEMA public TO chatbot_readonly_role;

-- product_item: id/is_active back the WHERE/ORDER BY + result columns of the two tests above;
-- title/price/stock/category_id were already granted and are used by every listed query.
-- product_item.cost (margin data) is deliberately still never granted.
GRANT SELECT (id, title, price, stock, category_id, is_active) ON product_item TO chatbot_readonly_role;

-- product_category: unchanged from the original grant. No listed test queries it directly via
-- raw SQL, but it's a non-sensitive lookup table (category names only) already relied upon for
-- joins/lookups against product_item.category_id, so it's kept rather than narrowed.
GRANT SELECT ON product_category TO chatbot_readonly_role;

-- product_order: added by this audit. `status` is the only column any exercised query reads
-- (test_query_9_safe_sql_sandbox above); nothing else on this table is granted.
GRANT SELECT (status) ON product_order TO chatbot_readonly_role;

-- Deliberately NEVER granted: auth_user (and the other tables FORBIDDEN_TABLE_PATTERNS blocks at
-- the application layer -- this role makes that a physical impossibility too), product_orderitem,
-- product_item.cost, product_supplier, product_comments, and any product_item/product_order
-- column not listed above.
ALTER ROLE chatbot_readonly_role SET statement_timeout = '3s';
