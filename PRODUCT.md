# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Evaluators & Stakeholders:** Engineering leads, technical recruiters, and business stakeholders evaluating an end-to-end, production-grade Django e-commerce architecture and BI engine.
- **Retail Shoppers (Simulated / Persona):** Consumers exploring a multi-category lifestyle marketplace, browsing catalog items, filtering products, managing shopping carts, completing checkouts with dynamic shipping rates and discount codes, leaving single-submission verified reviews, and consulting the AI shopping assistant.
- **Store Managers & Analysts (Simulated / Persona):** Business operators and data analysts reviewing real-time store KPIs, cart abandonment rates, sales forecasts, running statistical transaction simulations, and downloading automated Pandas ETL Excel/BI workbooks.

## Product Purpose

Provide a fully integrated, cloud-deployed e-commerce platform that connects consumer-facing retail transactions with executive-level data analytics and business intelligence. Success is demonstrated by seamless shopper conversion flows, robust relational database modeling with historical price snapshots, and actionable financial reporting.

## Positioning

A dual-lens e-commerce platform that unites a responsive multi-category retail marketplace with an enterprise-grade analytics engine, automated Pandas ETL pipeline, statistical data simulation (Zipf/Pareto/Log-Normal), and embedded Google Gemini AI assistance.

## Operating Context

- **Environment:** Cloud web application running Django on Render with Gunicorn and WhiteNoise asset compression, backed by Neon Serverless PostgreSQL with connection pooling.
- **Storefront Surface:** Consumer shopping experience covering catalog discovery, product detail views with 5-star ratings, cart summary, and checkout with geo-aware shipping calculation.
- **Analytics Surface:** Dedicated business intelligence suite (`/analytics/`) featuring KPI performance dashboards, time-series forecasting, statistical traffic simulation controls, and conversational AI chat.

## Capabilities and Constraints

- **Catalog & Commerce:** Taxonomy hierarchy (Categories, Brands, Suppliers), stock validation, shopping cart state management, checkout with discount codes (`DESC10`, `OFF500`), domestic vs. international freight calculation, and single-review database constraint (`unique_together = ('user', 'item')`).
- **Data Engineering & BI:** Automated ETL pipeline generating multi-tab formatted Excel (`.xlsx`) workbooks via Pandas and openpyxl; statistical synthetic data generation with Zipf brand distribution, log-normal pricing, and Pareto customer orders.
- **Technical & Infrastructure Constraints:** 512MB RAM cloud memory boundary requiring memory-bounded query chunking and garbage collection; serverless connection limits; WhiteNoise manifest static asset caching.
- **Terminology:** `Item`, `Order`, `OrderItem` (unit price/cost snapshot), `Net Profit`, `Gross Margin %`, `Cart Abandonment Rate`.

## Brand Commitments

- **Tone & Identity:** Modern, data-driven, clean, and credible retail marketplace paired with a professional executive analytics aesthetic.
- **UI Base:** HTML5, CSS3, JavaScript, Bootstrap 5 / Material Design for Bootstrap (MDB) with custom enhancements.

## Evidence on Hand

- Complete 3NF relational data model with historical price preservation in [product/models.py](file:///c:/Users/facur/Documents/ecommerce_Django/product/models.py).
- Automated Pandas ETL service in [analytics/services.py](file:///c:/Users/facur/Documents/ecommerce_Django/analytics/services.py) and data generator in [analytics/management/commands/generate_data.py](file:///c:/Users/facur/Documents/ecommerce_Django/analytics/management/commands/generate_data.py).
- Automated test suite covering auth, financial calculations, reviews, and edge cases in [product/tests.py](file:///c:/Users/facur/Documents/ecommerce_Django/product/tests.py) and [analytics/tests.py](file:///c:/Users/facur/Documents/ecommerce_Django/analytics/tests.py).
- Cloud deployment configuration on Render with Neon PostgreSQL.

## Product Principles

- **Data Integrity First:** Transactional data, historical costs, and business metrics must always remain auditable, mathematically consistent, and resilient to schema changes.
- **Dual-Lens Cohesion:** Storefront interactions must remain frictionless for consumers while executive tools provide dense, scannable intelligence for operators.
- **Production Reality:** Code and workflows respect actual cloud boundaries (memory limits, connection pooling, asset pipelines) rather than local assumptions.
- **Purposeful Intelligence:** AI and statistical simulation serve concrete operational and shopping needs rather than functioning as superficial demo widgets.

## Accessibility & Inclusion

- WCAG 2.1 AA target compliance across all public storefront and internal analytics surfaces.
- Accessible form controls, distinct focus indicators, responsive reflow across device sizes, and semantic HTML markup.
