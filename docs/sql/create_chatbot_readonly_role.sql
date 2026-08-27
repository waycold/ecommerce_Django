-- Dedicated, least-privilege Postgres role for the Chatbot-Engine-Gateway's read path.
-- Run this manually against the target database when provisioning the chatbot's DB access —
-- it is NOT applied automatically by Django migrations (role/grant management is
-- instance-level, not schema-level, and the password must never be committed to git).
--
-- Replace the password placeholder with a real, randomly generated secret before running,
-- and store that secret in your deployment platform's environment variables (e.g. Render),
-- never in this file or in git history.
--
-- Already applied to the production Neon project ("Ecommerce database" / dark-tooth-59531599,
-- database `neondb`) on 2026-08-27. This file is kept as the runbook for provisioning the
-- same role again elsewhere (a new environment, a rotated password, a staging database).

CREATE ROLE chatbot_readonly_role LOGIN PASSWORD '<REPLACE_WITH_GENERATED_SECRET>';
GRANT CONNECT ON DATABASE neondb TO chatbot_readonly_role;
GRANT USAGE ON SCHEMA public TO chatbot_readonly_role;
GRANT SELECT (title, price, stock, category_id) ON product_item TO chatbot_readonly_role;
GRANT SELECT ON product_category TO chatbot_readonly_role;
-- Deliberately NEVER granted: auth_user, product_order, product_orderitem, product_item.cost,
-- product_supplier, and any other column of product_item beyond the four above.
ALTER ROLE chatbot_readonly_role SET statement_timeout = '3s';
