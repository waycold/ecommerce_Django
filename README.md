# 🛒 Enterprise Data-Driven E-Commerce & AI Analytics Platform

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-4.1.2-092E20?style=for-the-badge&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Neon.tech-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://neon.tech/)
[![Render](https://img.shields.io/badge/Render-Hosted-46E3B7?style=for-the-badge&logo=render&logoColor=black)](https://render.com/)
[![Pandas](https://img.shields.io/badge/Pandas-ETL%20Engine-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Pytest](https://img.shields.io/badge/Pytest-143%2B%20Tests%20Passed-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5%20%2F%20Dark%20Console-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white)](https://getbootstrap.com/)

> **Production-grade E-Commerce Web Application, Managerial BI Analytics Console, and AI Copilot Orchestrator** built with **Django**, hosted on **Render**, backed by a Serverless PostgreSQL database on **Neon.tech**, featuring an automated **Pandas ETL pipeline**, statistical **synthetic data generator**, and an **AI Agent Gateway with Server-Sent Events (SSE) token streaming**.

---

## 📌 Architectural Overview & Folder Structure

The project is organized in a clean, scalable, and domain-driven modular architecture:

```text
ecommerce_Django/
├── apps/                               # Modular Domain Applications
│   ├── core/                           # Cross-cutting security, middleware & auth
│   │   ├── authentication/             # JWT token issuance & validation services and views
│   │   ├── middleware.py               # InternalSecretMiddleware (service-to-service header security)
│   │   ├── views.py                    # health_check_view
│   │   └── internal_urls.py            # /api/v1/internal/ API dispatcher
│   │
│   ├── catalog/                        # [Domain 1] Product catalog, categories, brands, inventory
│   │   ├── models.py                   # Category, Brand, Supplier, Item, Comments (db_table preserved)
│   │   ├── services.py                 # Multi-token search & relevance ranking service
│   │   ├── views.py                    # HomeView, ProductDetailView, CRUD & comments
│   │   ├── internal_views.py           # /catalog/search/ internal API for FastAPI microservice
│   │   └── forms.py, admin.py, urls.py
│   │
│   ├── orders/                         # [Domain 2] Orders lifecycle, cart, checkout & customer profiles
│   │   ├── models.py                   # Profile, Order, OrderItem, OrderStatus, PaymentMethod
│   │   ├── services.py                 # Dynamic freight, coupon & checkout calculations
│   │   ├── views.py                    # Cart manipulation, checkout & user authentication controllers
│   │   ├── context_processors.py       # JWT token & user profile image injectors
│   │   └── forms.py, admin.py, urls.py
│   │
│   └── analytics/                      # [Domain 3] Executive BI, forecasting, simulation & AI copilot
│       ├── services/                   # Modularized Business Logic & Analytics Services
│       │   ├── kpi_service.py          # Real-time managerial KPIs & caching
│       │   ├── forecast_service.py     # OLS linear regression demand forecasting
│       │   ├── etl_service.py          # OpenPyXL & Pandas Excel export pipeline
│       │   └── generator_service.py    # Multi-threaded synthetic dataset simulator
│       ├── views.py                    # Dashboard, Forecast, Simulator & AI Copilot views
│       ├── internal_views.py           # /analytics/metrics/ internal API for FastAPI microservice
│       └── management/commands/        # generate_data.py, audit_dataset.py
│
├── config/                             # Enterprise Modular Settings & Orchestration
│   ├── wsgi.py / asgi.py               # Application entrypoints for Gunicorn / Uvicorn
│   ├── urls.py                         # Root URL routing
│   └── settings/
│       ├── base.py                     # Common base settings across all environments
│       ├── local.py                    # Local development configuration (DEBUG=True)
│       ├── production.py               # Production settings (WhiteNoise, SSL, Neon PostgreSQL)
│       └── testing.py                  # High-speed in-memory testing settings
│
├── static/                             # Centralized Static Assets (CSS, JS, Fonts, Images)
│   ├── css/
│   ├── js/ (including chat-widget.js)
│   ├── img/
│   └── font/
│
├── templates/                          # Centralized Templates by Domain
│   ├── base.html
│   ├── catalog/                        # Catalog domain templates
│   ├── orders/                         # Orders & Profile templates
│   └── analytics/                      # Managerial dark console & AI Chat Copilot templates
│
├── tests/                              # Comprehensive QA & Security Pytest Suite
├── .env.example                        # Secure environment variables template (no keys exposed)
├── .gitignore                          # Strict shielding of secrets, caches & databases
├── build.sh                            # Continuous deployment build script for Render
├── manage.py                           # Django CLI manager (defaults to config.settings.local)
├── pytest.ini                          # Pytest discovery and testing settings
└── requirements.txt                    # Clean project dependencies
```

---

## 🔒 Secret Shielding & Environment Configuration

All sensitive credentials, API keys, and internal communication tokens are isolated in environment variables.

### 1. Initializing Environment Variables
Copy the secure template `.env.example` to create your local `.env`:
```bash
cp .env.example .env
```

### 2. Required Environment Variables

| Variable | Description | Example / Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Cryptographic secret for session and CSRF security | `your-secret-key-32-chars` |
| `DJANGO_DEBUG` | Enable debug mode (`True` locally, `False` in prod) | `True` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated list of allowed host domains | `127.0.0.1,localhost,.onrender.com` |
| `DATABASE_URL` | Neon.tech PostgreSQL connection string (defaults to SQLite) | `postgresql://user:pass@ep-neon.tech/db?sslmode=require` |
| `INTERNAL_API_SECRET` | Shared secret header between AI Gateway and Django | `your-shared-internal-secret-token` |
| `GEMINI_API_KEY` | Google Gemini API key for GenAI responses | `AQ.Ab8...` |
| `AI_AGENT_GATEWAY_URL` | Microservice AI Gateway URL | `https://ai-agent-gateway-sued.onrender.com` |
| `CLOUDINARY_*` | Cloudinary asset storage credentials | *(Optional)* |

> [!IMPORTANT]
> The `.env` file is strictly ignored by `.gitignore` along with database files (`*.sqlite3`), coverage reports, and bytecode caches. Never commit `.env` to Git.

---

## ⚙️ Modular Settings Management

The project supports modular Django settings via the `DJANGO_SETTINGS_MODULE` environment variable:

* **Local Development (`config.settings.local`):**
  ```bash
  python manage.py runserver --settings=config.settings.local
  ```
* **Production Deployment (`config.settings.production`):**
  Enforces SSL redirect, HTTPS cookies (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`), and strict security headers.
  ```bash
  gunicorn config.wsgi:application --env DJANGO_SETTINGS_MODULE=config.settings.production
  ```
* **Automated Testing (`config.settings.testing`):**
  Uses fast in-memory SQLite and MD5 password hasher for rapid test execution.
  ```bash
  python -m pytest
  ```

---

## 🧪 Comprehensive Testing Suite (Pytest)

The repository includes a comprehensive test suite guaranteeing 100% reliability across all domain models, internal APIs, and AI integrations:

```bash
# Run full suite with pytest
python -m pytest

# Run specific test modules with verbose output
pytest tests/test_catalog_search_refinements.py -v
pytest tests/test_analytics_chat.py -v
pytest tests/test_auth_contract.py -v
```

---

## 🚀 Installation & Local Setup

### 1. Clone & Virtual Environment Setup
```bash
git clone https://github.com/facur/ecommerce_Django.git
cd ecommerce_Django

# Create and activate virtual environment
python -m venv venv

# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux / macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Edit .env with your specific local configuration
```

### 3. Database Migration & Data Simulation
```bash
# Apply migrations
python manage.py migrate

# Generate statistical synthetic transactions (Pareto & Zipfian modeling)
python manage.py generate_data

# Create superuser for managerial & admin access
python manage.py createsuperuser
```

### 4. Start Development Server
```bash
python manage.py runserver
```
* **Storefront:** [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
* **AI Copilot & BI Portal:** [http://127.0.0.1:8000/analytics/chat/](http://127.0.0.1:8000/analytics/chat/)
* **Executive Dashboard:** [http://127.0.0.1:8000/analytics/dashboard/](http://127.0.0.1:8000/analytics/dashboard/)
* **Django Admin:** [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

---

## ☁️ Cloud Deployment on Render & Neon.tech

### Continuous Deployment via `build.sh`
On every push to `main`, Render triggers `build.sh`:
```bash
#!/usr/bin/env bash
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --no-input --settings=config.settings.production
python manage.py migrate --settings=config.settings.production
```

### Gunicorn Start Command
```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4
```

---

## 👨‍💻 Engineering Team & Quality Assurance

* **Architecture:** Enterprise Domain-Driven Modular Django Architecture (`apps.*` & `config.settings.*`).
* **QA & Security:** Antigravity Agile QA Engineering Suite (`pytest-django`, `X-Internal-Secret` middleware validation, JWT auth contracts).
