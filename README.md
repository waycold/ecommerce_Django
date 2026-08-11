# Data-Driven E-Commerce & Analytics Platform

[![Python Version](https://img.shields.io/badge/python-3.8%20%7C%203.9%20%7C%203.10-blue.svg)](https://www.python.org/)
[![Django Version](https://img.shields.io/badge/django-4.1.2-green.svg)](https://www.djangoproject.com/)
[![Pandas](https://img.shields.io/badge/pandas-2.2.0-orange.svg)](https://pandas.pydata.org/)
[![Status](https://img.shields.io/badge/status-in--development-yellow.svg)](#)

A production-ready Django E-commerce platform integrated with a custom **Pandas-powered ETL pipeline** and an **automated synthetic data generator**. This project is designed to highlight advanced software engineering, data engineering, and automation concepts for a professional portfolio.

---

## 🚀 Key Portfolio Highlights (Data & Automation)

Unlike standard online stores, this project focuses heavily on **realistic database simulation**, **data transformation**, and **analytics aggregation**. 

### 1. Statistical Synthetic Data Simulation Engine
To demonstrate data engineering and analytics capabilities under realistic conditions, the project includes a custom Django command (`generate_data`) that generates large, coherent synthetic datasets from scratch using advanced statistical modeling:
*   **Zipf's Law Distribution:** Brands and suppliers are distributed using Zipfian weights, mimicking real-world markets where a small group of companies dominates search and order volume.
*   **Log-Normal Price Modeling:** Item prices are modeled using a log-normal distribution:
    $$\text{Price} \sim e^{\mathcal{N}(\mu=8,\, \sigma^2=1.5^2)}$$
    This creates a few high-ticket items and many low-cost everyday commodities. Unit cost is calculated dynamically as a percentage (45%–80%) of the price to simulate variable margins.
*   **Pareto Purchasing Behavior:** Orders per user are modeled using a Pareto distribution ($x_{min}=1$, $\alpha=2.5$), simulating real buyer behavior where a small percentage of power users account for the majority of sales.
*   **Seasonality Adjustments:** Sales quantities are weighted based on the calendar month, creating volume spikes in November (1.4x) and December (1.8x), and drops in January (0.75x).
*   **Temporal Inflation Modeling:** Simulates prices and costs going back 24 months, deflating them at a compound monthly inflation rate of 4% to create historical price trends.

### 2. Pandas-Driven ETL Pipeline
A decoupled service module (`analytics/services.py`) houses a robust Extraction, Transformation, and Load pipeline:
*   **Extract:** Pulls transactional orders and details from the database using Django ORM annotations.
*   **Transform:** Operates on the dataset using **Pandas**:
    *   Renames fields for Business Intelligence standard layouts.
    *   Formats timestamps to timezone-naive datetimes for Excel compatibility.
    *   Fills empty categories/profiles with descriptive placeholders (e.g., "Guest/Anonymous", "Uncategorized").
    *   Calculates new financial metrics: Total Cost, Net Profit, and Profit Margin % per order.
*   **Load:** Exports the formatted DataFrame into a multi-sheet, openpyxl-styled `.xlsx` spreadsheet, prepared for ingestion by reporting systems like **PowerBI** or **Tableau**.

### 3. Managerial KPI Dashboard
A staff-only dashboard (`analytics/views.py`) displays real-time key performance indicators (KPIs) built on optimized Django aggregates (`Sum`, `Count`, `F`, `Q`), minimizing database query loads:
*   Current month total revenue.
*   Abandoned cart statistics (orders stuck in `PENDING` state).
*   Top 3 best-selling products by quantity and revenue.

---

## 🛍️ Core E-Commerce Features
*   **Catalog & Navigation:** Pagination (16 items/page), categorical filtering, and active item indexing.
*   **User Management:** Customizable user profiles with geo-location handling (Argentina vs. International).
*   **Dynamic Cart & Checkout:** Conditional shipping rates ($500 local vs. $2500 international) and promotional discount code evaluations (e.g., `DESC10` for 10% off, `OFF500` for flat deductions).
*   **Feedback Loops:** Comment and rating section with database-level uniqueness constraints ensuring one review per user per product.

---

## 🛠️ Technology Stack
*   **Backend:** Python, Django 4.1.2
*   **Data Processing:** Pandas, openpyxl
*   **Mocking & Simulation:** Faker, Random, Math
*   **Database:** SQLite (Development) / PostgreSQL-ready (with `psycopg2-binary`, `dj-database-url`)
*   **Deployment:** Gunicorn, WhiteNoise (production-grade static asset handling)

---

## 🗂️ Project Structure
```text
├── core/                   # Main Django configuration (settings, core routing)
├── product/                # Catalog, cart, checkouts, and reviews
│   ├── models.py           # Database schemas (Item, Order, Profile, Comments)
│   ├── views.py            # Business logic, cart handlers, and forms
│   └── tests.py            # Isolated TestCase suite
├── analytics/              # Data analysis and ETL module
│   ├── services.py         # Business intelligence ETL logic and KPI aggregates
│   ├── views.py            # Staff-only dashboards and Excel exports
│   └── management/
│       └── commands/
│           └── generate_data.py   # Complex synthetic data generator script
├── requirements.txt        # PIP dependencies
└── build.sh                # Deployment execution script
```

---

## ⚙️ Installation & Setup

Follow these steps to run the application and generate the analytics dataset locally:

### 1. Prerequisites
Ensure you have Python 3.8+ installed on your system.

### 2. Set Up Virtual Environment & Dependencies
Clone the repository, initialize a virtual environment, and install the required libraries:
```bash
# Create and activate virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Setup Configuration
Create a `.env` file in the root directory (based on `.env.example` if available) or set your environment variables:
```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
```

### 4. Database Migrations
Run the standard Django database migration sequence:
```bash
python manage.py migrate
```

### 5. Generate Synthetic Data
Execute the simulation command to wipe the database and generate 5,000 users, 2,000 products, 3,000 comments, and thousands of monthly orders:
```bash
python manage.py generate_data
```

### 6. Create Superuser (Admin Access)
Create an administrative staff member to access the dashboard and admin panel:
```bash
python manage.py createsuperuser
```

### 7. Run the Development Server
```bash
python manage.py runserver
```
Visit the shop at `http://127.0.0.1:8000/`. To access the Dashboard and download the Excel ETL export, log in with your admin account and navigate to `http://127.0.0.1:8000/analytics/`.

---

## 🧪 Testing
The project includes a robust test suite covering model validation, cart calculations, out-of-stock logic, conditional shipping, and user permissions. Run tests with:
```bash
python manage.py test
```

---

## 🎯 Portfolio Roadmap & Next Steps
As this project is in active development, the next milestones are focused on expanding its data engineering complexity:
*   [ ] **Association Rule Mining:** Implement a Scikit-Learn script to perform *Market Basket Analysis* (Apriori or FP-Growth algorithms) on generated order data.
*   [ ] **Demand Forecasting:** Integrate *Prophet* or *ARIMA* time-series forecasting models to predict product inventory restock dates.
*   [ ] **Asynchronous Pipelines:** Offload ETL generation and complex reports to background tasks using **Celery** and **Redis**.
*   [ ] **API Endpoints:** Configure **Django REST Framework** serialization endpoints for continuous BI dashboard data ingestion.
