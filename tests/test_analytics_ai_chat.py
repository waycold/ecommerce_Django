"""
tests/test_analytics_ai_chat.py

Comprehensive test suite verifying:
1. Product detail AI consultation prompt cleanliness (no price inside quotes of title).
2. Analytics AI Copilot view authentication & permission gating (staff only).
3. Analytics navbar AI Copilot link & active class state.
4. AI Copilot HTML template components:
   - Markdown table parser with .table-responsive and .table-custom scrolling
   - Conversation controls (Limpiar Conversación & sessionStorage key analytics_chat_session_id)
   - Live performance & telemetry panel (latency_ms, model, agent_id, gateway status)
   - Prompt starters / quick business questions
   - SSE streaming configuration (agent_id='analytics', endpoint, fallback)
"""

from decimal import Decimal
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from product.models import Category, Brand, Supplier, Item


@pytest.fixture
def standard_user(db):
    return User.objects.create_user(
        username="regular_user",
        email="regular@example.com",
        password="Password123!",
        is_staff=False,
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="analytics_manager",
        email="analytics@example.com",
        password="Password123!",
        is_staff=True,
    )


@pytest.fixture
def product_item(db):
    cat = Category.objects.create(name="Electronics")
    brand = Brand.objects.create(name="Sony")
    supplier = Supplier.objects.create(name="Sony Corp", country="Japan")
    return Item.objects.create(
        title="Sony WH-1000XM5 Wireless Headphones",
        description="Premium noise cancelling headphones",
        price=Decimal("399.99"),
        cost=Decimal("250.00"),
        stock=10,
        category=cat,
        brand=brand,
        supplier=supplier,
        is_active=True,
    )


@pytest.mark.django_db
class TestProductDetailAIPromptCleanliness:
    def test_product_detail_passes_clean_prompt_without_price_in_quotes(self, client, product_item):
        """
        Verify that consultarProducto passes:
        'Hola, me interesa el producto "' + nombre + '". ¿Podrías darme más detalles, recomendaciones y disponibilidad?'
        without price injected inside the name quotes.
        """
        url = reverse("product:product", kwargs={"slug": product_item.slug})
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")
        assert "consultarProducto" in html

        # Prompt string check
        expected_prompt_start = "'Hola, me interesa el producto \"' + nombre + '\". ¿Podrías darme más detalles, recomendaciones y disponibilidad?'"
        assert expected_prompt_start in html or "Hola, me interesa el producto" in html
        assert "Precio: $" not in html  # Price removed from inside prompt quotes


@pytest.mark.django_db
class TestAnalyticsAICopilotViewPermissions:
    def test_anonymous_user_redirected_to_login(self, client):
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_non_staff_user_redirected_to_login(self, client, standard_user):
        client.force_login(standard_user)
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_staff_user_can_access_ai_chat(self, client, staff_user):
        client.force_login(staff_user)
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert "Executive AI Copilot & Business Intelligence" in html


@pytest.mark.django_db
class TestAnalyticsNavbarAICopilotIntegration:
    def test_navbar_contains_ai_copilot_link(self, client, staff_user):
        client.force_login(staff_user)
        url = reverse("analytics:dashboard")
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")
        assert reverse("analytics:ai_chat") in html
        assert "AI Copilot" in html
        assert "fa-robot" in html

    def test_navbar_active_state_on_ai_chat_page(self, client, staff_user):
        client.force_login(staff_user)
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")
        # Check active class on AI Copilot link
        assert 'class="nav-link-custom active"' in html or 'nav-link-custom active' in html


@pytest.mark.django_db
class TestAnalyticsAICopilotTemplateComponents:
    def test_required_components_present(self, client, staff_user):
        client.force_login(staff_user)
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 200

        html = response.content.decode("utf-8")

        # a) Markdown table parser & table styling classes
        assert "table-responsive" in html
        assert "table-custom" in html

        # b) Conversation control
        assert "Limpiar Conversación" in html
        assert "clearChatBtn" in html
        assert "analytics_chat_session_id" in html

        # c) Live performance & telemetry
        assert "telemetryLatency" in html
        assert "telemetryModel" in html
        assert "gatewayStatusBadge" in html
        assert "telemetrySessionId" in html

        # d) Prompt Starters / Preguntas Sugeridas
        assert "¿Cuáles son los KPIs del mes actual?" in html
        assert "¿Cuáles son los 5 productos más vendidos?" in html
        assert "Muéstrame la distribución de ventas por categoría en una tabla" in html
        assert "¿Cuál es la proyección de demanda para el próximo trimestre?" in html

        # e) SSE streaming & Microservice configuration
        assert "https://ai-agent-gateway-sued.onrender.com/api/v1/chat/stream" in html
        assert "https://ai-agent-gateway-sued.onrender.com/api/v1/chat" in html
        assert "agent_id" in html
        assert "analytics" in html
        assert "streaming-cursor" in html
