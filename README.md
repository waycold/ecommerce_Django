# 🛒 Data-Driven E-Commerce Platform & Business Intelligence Engine

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.1.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon.tech-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Render](https://img.shields.io/badge/Render-Hosted-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com/)
[![Pandas](https://img.shields.io/badge/Pandas-ETL%20Engine-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5%20%2F%20MDB-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

> **Production-grade E-Commerce Web Application and Data Analytics Platform** built with **Django**, hosted on **Render**, backed by a Serverless PostgreSQL database on **Neon.tech**, featuring an automated **Pandas ETL pipeline**, statistical **synthetic data simulation**, and an **AI-powered assistant**.

---

## 📌 Executive Summary & Architecture Overview

This project is architected to demonstrate end-to-end backend engineering, scalable database modeling, data analytics, and cloud deployment. Beyond standard CRUD capabilities, the platform integrates realistic retail transaction simulation, automated financial metric extraction, and production cloud infrastructure.

```
                  ┌──────────────────────────────────────────────┐
                  │                 CLIENT BROWSER               │
                  └───────────────────────┬──────────────────────┘
                                          │ HTTPS (SSL/TLS)
                                          ▼
                  ┌──────────────────────────────────────────────┐
                  │              RENDER WEB SERVICE              │
                  │  ┌────────────────────────────────────────┐  │
                  │  │     Gunicorn WSGI Application Server   │  │
                  │  ├────────────────────────────────────────┤  │
                  │  │     WhiteNoise (Static Asset Engine)   │  │
                  │  ├────────────────────────────────────────┤  │
                  │  │     Django 4.1.2 Backend Architecture  │  │
                  │  │     • Product Catalog & Cart Engine    │  │
                  │  │     • Analytics & Pandas ETL Pipeline  │  │
                  │  │     • Statistical Data Generator       │  │
                  │  │     • Gemini AI Chatbot Service        │  │
                  │  └───────────────────┬────────────────────┘  │
                  └──────────────────────┼───────────────────────┘
                                         │ TCP / SSL Connection Pooling
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │           NEON.TECH POSTGRESQL CLOUD         │
                  │  ┌────────────────────────────────────────┐  │
                  │  │      Serverless PostgreSQL Instance     │  │
                  │  │      • High Availability & Auto-scaling│  │
                  │  │      • 3NF Relational Data Model       │  │
                  │  │      • ACID Transactional Guarantees   │  │
                  │  └────────────────────────────────────────┘  │
                  └──────────────────────────────────────────────┘
```

---

## ☁️ Cloud Infrastructure & Deployment

### 1. Web Hosting on [Render](https://render.com)
* **Application Server:** Powered by **Gunicorn** for resilient multi-worker concurrency.
* **Static Asset Management:** Utilizes **WhiteNoise** with `CustomCompressedManifestStaticFilesStorage` for Gzip/Brotli compression, permanent browser caching, and instant static file delivery without external S3 overhead.
* **CI/CD Build Pipeline:** Automated build execution via `build.sh` running dependency installation, migration execution, and static collection on every GitHub push:
  ```bash
  pip install -r requirements.txt
  python manage.py collectstatic --no-input
  python manage.py migrate
  ```
* **Memory-Optimized Execution:** Optimized memory footprint ensuring seamless operation within 512MB RAM constraints through chunked queries and garbage-collected batch insertions.

### 2. Database on [Neon.tech](https://neon.tech) (Serverless PostgreSQL)
* **Cloud Database:** Hosted on **Neon.tech Serverless PostgreSQL** with compute-storage separation, instantaneous branching, and SSL encryption (`sslmode=require`).
* **Connection Pooling:** Integrated via `dj-database-url` with persistent connections (`conn_max_age=600`) to minimize connection overhead under burst traffic.
* **Environment Isolation:** Zero-drift dual environment architecture:
  * **Production / Staging:** PostgreSQL on Neon.tech.
  * **Test Suite (CI/CD):** Fast in-memory/isolated SQLite triggered automatically during `python manage.py test`.

---

## 🗄️ Database Architecture & Entity-Relationship Model (ERD)

The database follows strict relational normalization (3NF) designed for high integrity, historical auditability, and analytical performance.

### 📊 Visual Entity-Relationship Diagram

```mermaid
erDiagram
    User ||--o| Profile : "1:1 has profile"
    User ||--o{ Order : "1:N places"
    User ||--o{ Comments : "1:N writes"

    Brand ||--o{ Item : "1:N manufactures"
    Category ||--o{ Item : "1:N categorizes"
    Supplier ||--o{ Item : "1:N supplies"

    Item ||--o{ OrderItem : "1:N included in"
    Item ||--o{ Comments : "1:N receives"

    Order ||--|{ OrderItem : "1:N contains"

    User {
        int id PK
        varchar username "unique"
        varchar email
        varchar password
    }

    Profile {
        int id PK
        int user_id FK "1:1 Unique"
        varchar phone
        varchar description
        varchar image
        varchar address_line
        varchar city
        varchar province
        varchar zip_code
        varchar country "Default: United States"
        date birth_date
        varchar gender "M / F / O"
    }

    Brand {
        int id PK
        varchar name "unique"
        datetime created_at
        datetime updated_at
    }

    Category {
        int id PK
        varchar name "unique"
        datetime created_at
        datetime updated_at
    }

    Supplier {
        int id PK
        varchar name
        varchar country
        datetime created_at
        datetime updated_at
    }

    Item {
        int id PK
        varchar title
        varchar description
        decimal price "10,2"
        decimal cost "10,2"
        int stock
        int minimum_stock
        int category_id FK
        int supplier_id FK
        int brand_id FK
        varchar label
        varchar slug "unique"
        varchar img
        datetime created_at
        datetime updated_at
        boolean is_active
    }

    Order {
        int id PK
        int user_id FK
        varchar status "PENDING, PAID, SHIPPED, etc."
        varchar payment_method
        varchar discount_code
        decimal discount "10,2"
        decimal shipping_cost "10,2"
        decimal total "10,2"
        datetime start_date
        datetime ordered_date
        datetime updated_at
    }

    OrderItem {
        int id PK
        int order_id FK
        int item_id FK
        int quantity
        decimal unit_price "10,2 (Snapshot)"
        decimal unit_cost "10,2 (Snapshot)"
        decimal subtotal "10,2"
    }

    Comments {
        int id PK
        int user_id FK
        int item_id FK
        text body
        int rating "1 to 5"
        datetime date_added
        int likes
    }
```

### 📋 Data Dictionary & Relational Schema

| Model | Primary Key | Foreign Keys | Key Fields & Description | Constraints & Business Logic |
| :--- | :--- | :--- | :--- | :--- |
| **`User`** | `id` (int) | — | `username`, `email`, `password` | Django Auth core model; unique usernames. |
| **`Profile`** | `id` (int) | `user_id` (User) | `phone`, `city`, `province`, `country`, `birth_date`, `gender`, `image` | One-to-One with User. Determines domestic vs. international shipping rates. |
| **`Brand`** | `id` (int) | — | `name`, `created_at`, `updated_at` | Categorical brand entity with unique naming index. |
| **`Category`** | `id` (int) | — | `name`, `created_at`, `updated_at` | Taxonomy entity for item segmentation and catalog navigation. |
| **`Supplier`** | `id` (int) | — | `name`, `country`, `created_at`, `updated_at` | Vendor entity tracking origin country for supply chain analytics. |
| **`Item`** | `id` (int) | `category_id`, `supplier_id`, `brand_id` | `title`, `price`, `cost`, `stock`, `minimum_stock`, `slug`, `is_active` | Unique auto-slugified URLs; stock validation rules before cart insertion. |
| **`Order`** | `id` (int) | `user_id` (User) | `status`, `payment_method`, `discount_code`, `discount`, `shipping_cost`, `total`, `ordered_date` | Lifecycle state machine (`PENDING` -> `PAID` -> `SHIPPED` -> `DELIVERED`). |
| **`OrderItem`** | `id` (int) | `order_id` (Order), `item_id` (Item) | `quantity`, `unit_price`, `unit_cost`, `subtotal` | **Historical Price Snapshots:** Preserves historical pricing at time of purchase. |
| **`Comments`** | `id` (int) | `user_id` (User), `item_id` (Item) | `body`, `rating` (1–5), `date_added`, `likes` | **Database Uniqueness Constraint:** `unique_together = ('user', 'item')` (1 review/user). |

---

## 📈 Data Engineering & Simulation Engine

### 1. Statistical Synthetic Data Generation (`generate_data`)
To simulate high-volume enterprise traffic without compromising realism, a custom Django management command generates thousands of mathematically coherent records:
* **Zipf's Law Distribution:** Brands and suppliers are distributed with Zipfian weights, mimicking real-world market concentration where a dominant minority captures the majority of transactions.
* **Log-Normal Price & Cost Modeling:**
  $$\text{Price} \sim e^{\mathcal{N}(\mu=8,\, \sigma^2=1.5^2)}$$
  Unit costs are dynamically calibrated as a percentage (45%–80%) of price to create variable gross margins.
* **Pareto Purchasing Behavior:** Order distributions follow a Pareto distribution ($x_{min}=1, \alpha=2.5$), reproducing authentic 80/20 customer concentration.
* **Seasonality & Inflation:** Simulates 24-month historical depth with calendar-based seasonality (November 1.4x, December 1.8x, January 0.75x) and a 4% compound monthly deflator.
* **Chunked Batch Ingestion:** Uses memory-bounded chunking (`batch_size=1000`) and explicit garbage collection (`gc.collect()`), allowing ingestion of 10,000+ rows within 512MB RAM environments.

### 2. Automated Pandas ETL Pipeline
Located in `analytics/services.py`, this service extracts relational data, applies transformations, and delivers formatted business outputs:
* **Extract:** Queries orders and line items using optimized Django ORM prefetching (`select_related`, `prefetch_related`).
* **Transform with Pandas:**
  * Flattens multi-table joins into denormalized transactional tables.
  * Formats UTC timestamps to timezone-naive datetimes for Excel/BI ingestion.
  * Computes financial metrics: `Total Cost`, `Net Profit`, and `Profit Margin %` per transaction.
* **Load:** Generates styled multi-tab `.xlsx` workbooks via **openpyxl** formatted specifically for **Power BI**, **Tableau**, or Excel stakeholders.

### 3. Managerial KPI Dashboard
A secured dashboard (`/analytics/`) displaying real-time metrics computed via database-level aggregates (`Sum`, `Count`, `F()`, `Q()` expressions):
* Real-time Monthly Revenue & Historical Trajectory.
* Cart Abandonment Rate (orders in `PENDING` vs. completed transactions).
* Top Best-Selling Products by Volume and Gross Revenue.

---

## 🛍️ Key Functional Features

* **E-Commerce Flow:** Full shopping cycle (Catalog, Filtering, Cart Summary, Checkout, Dynamic Shipping Calculation, Discount Codes like `DESC10` or `OFF500`).
* **Resilient User Profiles:** Avatar system with automatic SVG vector fallback, geo-location handling (Domestic vs. International shipping rates).
* **Audited Reviews:** 5-star rating system with database-level integrity constraints preventing duplicate submissions.
* **AI Virtual Assistant:** Integrated **Gemini AI** chatbot assisting users with queries about the product line, tech stack, and data architecture.

---

## 🛠️ Technology Stack Summary

| Layer | Technology | Details |
| :--- | :--- | :--- |
| **Backend Framework** | **Python 3.10+ / Django 4.1.2** | MTV Architecture, ORM, Forms, Class-Based & Function-Based Views |
| **Database (Cloud)** | **PostgreSQL (Neon.tech)** | Serverless, Connection Pooling, SSL Encryption, ACID Compliance |
| **Data & Analytics** | **Pandas 2.2+, openpyxl, NumPy** | ETL processing, financial aggregation, Excel multi-sheet reports |
| **AI Integration** | **Google Gemini AI SDK** | Contextual chatbot microservice endpoint (`/api/chat/`) |
| **Frontend & UI** | **HTML5, CSS3, JavaScript, Bootstrap, MDB** | Responsive modern design, interactive star ratings, SVG fallbacks |
| **Production Server** | **Gunicorn + WhiteNoise** | Multi-worker WSGI, manifest static storage, gzip caching |
| **Cloud Platform** | **Render** | Web Service continuous deployment linked to GitHub repository |
| **Quality Assurance** | **Django TestCase Suite** | 21 automated unit tests covering business logic and edge cases |

---

## 🧪 Testing Suite & Validation

The codebase includes an isolated test suite validating core business logic, permissions, financial calculations, and edge cases:
* **User & Auth Lifecycle:** Login verification and profile creation.
* **Order & Calculation Logic:** Subtotal aggregation, discount code evaluation, dynamic international freight recalculation.
* **Inventory Control:** Out-of-stock validation and catalog filtering.
* **Review Integrity:** Uniqueness constraint enforcement via `IntegrityError` testing.
* **AI Chatbot Safety:** Error handling for invalid requests and configuration states.

Execute the test suite with:
```bash
python manage.py test
```

---

## ⚙️ Local Development Setup

### 1. Clone & Initialize Environment
```bash
git clone https://github.com/facur/ecommerce_Django.git
cd ecommerce_Django

# Create and activate virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Create a `.env` file in the root directory:
```env
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
# Optional: Neon.tech PostgreSQL connection string (defaults to SQLite if omitted)
# DATABASE_URL=postgresql://user:password@ep-sample.neon.tech/ecommerce_db?sslmode=require
# GEMINI_API_KEY=your-gemini-api-key
```

### 3. Run Migrations & Generate Data
```bash
# Run database migrations
python manage.py migrate

# Generate statistical synthetic data (optional)
python manage.py generate_data

# Create superuser for administrative access
python manage.py createsuperuser
```

### 4. Run Development Server
```bash
python manage.py runserver
```
* **Storefront:** `http://127.0.0.1:8000/`
* **Analytics & KPI Dashboard:** `http://127.0.0.1:8000/analytics/`
* **Django Admin:** `http://127.0.0.1:8000/admin/`

---

## 👨‍💻 Author & Contact

* **Developer:** Facundo
* **Focus:** Python / Django Backend Development, Database Architecture & Data Engineering
