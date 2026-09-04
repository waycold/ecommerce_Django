"""
tests/test_frontend_integration.py

Comprehensive test suite verifying the Frontend Universal AI Chat Widget integration:
1. Static Asset Availability: `product/static/js/chat-widget.js` exists, non-empty, defines Shadow DOM, exposes `window.AiChatWidget`.
2. Base & Home Template Rendering: `GET /` returns 200, contains `<script>` with `chat-widget.js`, `data-api-url="https://ai-agent-gateway-sued.onrender.com"`, `data-agent="ecommerce"`, `data-title="Asistente de Compras"`.
3. JWT Context Processor Injection:
   - Anonymous user -> `data-user-token` not present or empty.
   - Authenticated user -> `data-user-token` contains a valid JWT token decodable & verifiable by `validate_staff_jwt_token` / `jwt.decode`.
4. Product Detail Programmatic Button: `GET /product/<slug>/` contains `consultarProducto` button and script with `window.AiChatWidget`.
5. Legacy Widget Purge: No broken references to `/api/chat/` across all templates.
"""

import os
import re
from pathlib import Path
from decimal import Decimal
import jwt
import pytest
from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.test import RequestFactory
from django.urls import reverse

from apps.core.authentication.services import validate_staff_jwt_token
from apps.orders.context_processors import user_jwt_token
from apps.catalog.models import Category, Brand, Supplier, Item


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def regular_customer(db):
    """Creates an active standard customer."""
    return User.objects.create_user(
        username="qa_customer",
        email="customer@example.com",
        password="CustomerPass123!",
        is_staff=False,
        is_superuser=False,
        is_active=True,
    )


@pytest.fixture
def staff_customer(db):
    """Creates an active staff member."""
    return User.objects.create_user(
        username="qa_staff",
        email="staff@example.com",
        password="StaffPass123!",
        is_staff=True,
        is_superuser=False,
        is_active=True,
    )


@pytest.fixture
def admin_superuser(db):
    """Creates an active superuser administrator."""
    return User.objects.create_superuser(
        username="qa_admin",
        email="admin@example.com",
        password="AdminPass123!",
    )


@pytest.fixture
def sample_product(db):
    """Creates a sample product catalog hierarchy for testing product detail view."""
    cat = Category.objects.create(name="Monitors")
    brand = Brand.objects.create(name="Samsung")
    supplier = Supplier.objects.create(name="Samsung Electronics", country="South Korea")
    item = Item.objects.create(
        title="Samsung Odyssey G9 Gaming Monitor",
        description="49 inch Curved Dual QHD Gaming Monitor",
        price=Decimal("1299.99"),
        cost=Decimal("950.00"),
        stock=15,
        category=cat,
        brand=brand,
        supplier=supplier,
        is_active=True,
    )
    return item


# ---------------------------------------------------------------------------
# 1. Static Asset Availability & Shadow DOM
# ---------------------------------------------------------------------------

class TestStaticWidgetAsset:
    """
    Validates static file availability, Shadow DOM encapsulation, and global API exposure.
    """

    @property
    def widget_js_path(self):
        return os.path.join(settings.BASE_DIR, "static", "js", "chat-widget.js")

    def test_chat_widget_js_file_exists_and_not_empty(self):
        """
        Verify that `product/static/js/chat-widget.js` exists on disk and is not empty.
        """
        assert os.path.exists(self.widget_js_path), f"File not found at: {self.widget_js_path}"
        file_size = os.path.getsize(self.widget_js_path)
        assert file_size > 0, "chat-widget.js must not be empty"

    def test_chat_widget_defines_shadow_dom(self):
        """
        Verify that `chat-widget.js` implements Shadow DOM isolation via `attachShadow`.
        """
        with open(self.widget_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "attachShadow" in content, "chat-widget.js must define Shadow DOM using attachShadow"
        assert "mode:" in content or "'open'" in content or '"open"' in content

    def test_chat_widget_exposes_window_aichatwidget(self):
        """
        Verify that `chat-widget.js` exposes `window.AiChatWidget` and essential programmatic APIs.
        """
        with open(self.widget_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "window.AiChatWidget" in content, "chat-widget.js must expose window.AiChatWidget"
        assert "open" in content, "window.AiChatWidget must provide an open method"
        assert "close" in content, "window.AiChatWidget must provide a close method"
        assert "sendMessage" in content, "window.AiChatWidget must provide a sendMessage method"

    def test_chat_widget_handles_gateway_dataset_config(self):
        """
        Verify that `chat-widget.js` reads dataset attributes (apiUrl, agent, title, userToken).
        """
        with open(self.widget_js_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "apiUrl" in content or "data-api-url" in content or "dataset.apiUrl" in content
        assert "agent" in content or "data-agent" in content or "dataset.agent" in content
        assert "title" in content or "data-title" in content or "dataset.title" in content


# ---------------------------------------------------------------------------
# 2. Template Rendering in Base & Home
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestBaseAndHomeTemplateRendering:
    """
    Validates rendering of the Chat Widget script tag across base templates and home view.
    """

    def test_home_page_returns_200_and_renders_widget_script(self, client):
        """
        Petición GET / retorna 200 y el HTML contiene <script con chat-widget.js,
        data-api-url, data-agent="ecommerce", data-title="Asistente de Compras".
        """
        response = client.get("/")
        assert response.status_code == 200

        html = response.content.decode("utf-8")

        # Script source check
        assert "chat-widget.js" in html, "Home page must include chat-widget.js in a <script> tag"

        # Gateway parameters check
        assert 'data-api-url="https://ai-agent-gateway-sued.onrender.com"' in html
        assert 'data-agent="ecommerce"' in html
        assert 'data-title="Asistente de Compras"' in html

    def test_about_page_renders_widget_script(self, client):
        """
        GET /about/ renders the universal widget script tag inherited from base.html.
        """
        response = client.get("/about/")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "chat-widget.js" in html
        assert 'data-api-url="https://ai-agent-gateway-sued.onrender.com"' in html
        assert 'data-agent="ecommerce"' in html

    def test_search_page_renders_widget_script(self, client):
        """
        GET / (with search filter) renders the universal widget script tag.
        """
        response = client.get("/?search=monitor")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "chat-widget.js" in html
        assert 'data-agent="ecommerce"' in html


# ---------------------------------------------------------------------------
# 3. JWT Context Processor Injection
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestJWTContextProcessorInjection:
    """
    Validates injection and decoding of JWT tokens for anonymous and authenticated users.
    """

    def test_anonymous_user_no_token_in_widget(self, client):
        """
        Petición como usuario anónimo -> data-user-token no está presente o está vacío en el script tag.
        """
        response = client.get("/")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        # data-user-token must NOT be populated with a token
        token_match = re.search(r'data-user-token="([^"]+)"', html)
        assert token_match is None, "Anonymous user must not have a populated data-user-token attribute"

    def test_authenticated_regular_user_jwt_token_injection(self, client, regular_customer):
        """
        Petición como usuario autenticado -> data-user-token contiene un token JWT válido
        que puede ser decodificado y verificado con jwt.decode.
        """
        client.force_login(regular_customer)
        response = client.get("/")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        # Extract token from data-user-token attribute
        token_match = re.search(r'data-user-token="([^"]+)"', html)
        assert token_match is not None, "Authenticated user must have data-user-token attribute injected"

        token = token_match.group(1)
        assert len(token) > 20, "Injected JWT token must be a non-trivial string"

        # Decode using settings.JWT_SECRET_KEY -- generate_user_jwt_token signs
        # with it, not SECRET_KEY (they only coincided by default pre-Fase 0).
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])
        assert payload.get("user_id") == regular_customer.id
        assert payload.get("username") == regular_customer.username
        assert payload.get("email") == regular_customer.email
        assert payload.get("is_staff") is False
        assert payload.get("is_superuser") is False

    def test_authenticated_staff_user_jwt_token_validation(self, client, staff_customer):
        """
        Petición como staff -> data-user-token contiene un token JWT verificable
        mediante core.auth_services.validate_staff_jwt_token.
        """
        client.force_login(staff_customer)
        response = client.get("/")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        token_match = re.search(r'data-user-token="([^"]+)"', html)
        assert token_match is not None, "Staff user must have data-user-token injected"

        token = token_match.group(1)

        # Validate with auth_services
        data, status_code = validate_staff_jwt_token(token)
        assert status_code == 200
        assert data.get("valid") is True
        assert data.get("user", {}).get("id") == staff_customer.id
        assert data.get("user", {}).get("is_staff") is True

    def test_authenticated_superuser_jwt_token_validation(self, client, admin_superuser):
        """
        Petición como superuser -> data-user-token contiene un token JWT verificable con is_superuser=True.
        """
        client.force_login(admin_superuser)
        response = client.get("/")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        token_match = re.search(r'data-user-token="([^"]+)"', html)
        assert token_match is not None

        token = token_match.group(1)
        data, status_code = validate_staff_jwt_token(token)
        assert status_code == 200
        assert data.get("valid") is True
        assert data.get("user", {}).get("is_superuser") is True

    def test_context_processor_direct_invocation(self, regular_customer):
        """
        Direct unit test for the `user_jwt_token` context processor function.
        """
        factory = RequestFactory()

        # Anonymous request
        anon_request = factory.get("/")
        anon_request.user = AnonymousUser()
        anon_result = user_jwt_token(anon_request)
        assert "user_jwt_token" in anon_result
        assert anon_result["user_jwt_token"] is None

        # Authenticated request
        auth_request = factory.get("/")
        auth_request.user = regular_customer
        auth_result = user_jwt_token(auth_request)
        assert "user_jwt_token" in auth_result
        assert auth_result["user_jwt_token"] is not None
        assert isinstance(auth_result["user_jwt_token"], str)


# ---------------------------------------------------------------------------
# 4. Programmatic Button in Product Detail Page
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestProductDetailChatIntegration:
    """
    Validates programmatic button and integration script on the product detail page (/product/<slug>/).
    """

    def test_product_detail_contains_consultar_producto_button(self, client, sample_product):
        """
        Petición GET /product/<slug>/ contiene el botón con `consultarProducto`.
        """
        url = reverse("product:product", kwargs={"slug": sample_product.slug})
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")
        assert "consultarProducto" in html, "Product detail page must contain `consultarProducto` handler"
        assert sample_product.title in html

    def test_product_detail_contains_window_aichatwidget_script(self, client, sample_product):
        """
        Petición GET /product/<slug>/ contiene el script de integración `window.AiChatWidget`.
        """
        url = reverse("product:product", kwargs={"slug": sample_product.slug})
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")
        assert "window.AiChatWidget" in html, "Product detail page must invoke `window.AiChatWidget`"
        assert "window.AiChatWidget.open" in html or "AiChatWidget.open" in html
        assert "window.AiChatWidget.sendMessage" in html or "AiChatWidget.sendMessage" in html

    def test_product_detail_renders_chat_widget_script_tag(self, client, sample_product):
        """
        Product detail page inherits base.html and renders the universal chat widget script tag.
        """
        url = reverse("product:product", kwargs={"slug": sample_product.slug})
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")
        assert "chat-widget.js" in html
        assert 'data-agent="ecommerce"' in html


# ---------------------------------------------------------------------------
# 5. Legacy Widget Purge
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestLegacyWidgetPurged:
    """
    Validates that the legacy widget and broken `/api/chat/` references have been purged from templates.
    """

    def test_no_legacy_chat_route_in_any_template(self):
        """
        Confirm that no template in `templates/` references the deprecated `/api/chat/` endpoint.
        """
        templates_dir = Path(settings.BASE_DIR) / "templates"
        assert templates_dir.exists()

        violating_templates = []
        for html_file in templates_dir.rglob("*.html"):
            content = html_file.read_text(encoding="utf-8")
            if "/api/chat/" in content:
                violating_templates.append(html_file.name)

        assert not violating_templates, f"Deprecated route '/api/chat/' found in templates: {violating_templates}"

    def test_home_page_does_not_render_legacy_widget_elements(self, client):
        """
        Home page HTML does not render legacy elements like `#aiChatWindow` or `#aiChatBody`.
        """
        response = client.get("/")
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="aiChatWindow"' not in html
        assert 'id="aiChatBody"' not in html
        assert 'id="aiChatInput"' not in html

    def test_legacy_api_chat_route_returns_404(self, client):
        """
        Requesting the legacy /api/chat/ endpoint returns HTTP 404 Not Found.
        """
        response_get = client.get("/api/chat/")
        assert response_get.status_code == 404

        response_post = client.post("/api/chat/", data={"message": "hello"}, content_type="application/json")
        assert response_post.status_code == 404
