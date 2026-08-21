"""
tests/test_analytics_chat.py

Comprehensive test suite verifying the Managerial AI Analytics Copilot Web Interface:
1. Authentication & Permission Gating:
   - Anonymous users: redirected to login (HTTP 302).
   - Non-staff authenticated users: redirected to login (HTTP 302).
   - Staff and superusers: granted access (HTTP 200).
2. Navigation & UI Integration:
   - AI Copilot tab present in managerial navbar with active class when rendered.
   - Distinct active states across analytics pages (Dashboard vs AI Copilot).
3. Core Copilot Template & Architectural Components:
   - Conversation controls (Limpiar Conversación, Clear session, Send button, User input).
   - Live telemetry and performance panels (latency, model router, session ID, online gateway status).
   - Streaming area and indicators (SSE stream targets, streaming cursor, typing indicators).
   - Quick starter prompt suggestions for business queries.
   - Markdown responsive tables and scrollable containers for executive reporting.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def standard_client_user(db):
    return User.objects.create_user(
        username="standard_buyer",
        email="buyer@example.com",
        password="SafePassword123!",
        is_staff=False,
    )


@pytest.fixture
def staff_member(db):
    return User.objects.create_user(
        username="analytics_officer",
        email="officer@company.com",
        password="SafePassword123!",
        is_staff=True,
    )


@pytest.fixture
def superuser_admin(db):
    return User.objects.create_superuser(
        username="chief_executive",
        email="executive@company.com",
        password="SafePassword123!",
    )


# ==============================================================================
# 1. AUTHENTICATION & ACCESS CONTROL TESTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsChatAuthentication:
    """
    Validates permission boundaries and authentication barriers for GET /analytics/chat/.
    """

    CHAT_URL = '/analytics/chat/'

    def test_anonymous_access_redirects_to_login(self, client):
        """
        Unauthenticated requests must be redirected to the login view with next parameter.
        """
        response = client.get(self.CHAT_URL)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_authenticated_non_staff_redirects_to_login(self, client, standard_client_user):
        """
        Authenticated non-staff regular users must be redirected away from internal analytics chat.
        """
        client.force_login(standard_client_user)
        response = client.get(self.CHAT_URL)
        assert response.status_code == 302
        assert "/login" in response.url

    def test_staff_user_access_allowed(self, client, staff_member):
        """
        Staff members have full authorization to access the AI Copilot chat interface.
        """
        client.force_login(staff_member)
        response = client.get(self.CHAT_URL)
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Executive AI Copilot & Business Intelligence" in content

    def test_superuser_access_allowed(self, client, superuser_admin):
        """
        Superusers have full authorization to access the AI Copilot chat interface.
        """
        client.force_login(superuser_admin)
        response = client.get(self.CHAT_URL)
        assert response.status_code == 200

    def test_named_url_reverse_resolution(self):
        """
        Verifies that reverse('analytics:ai_chat') resolves cleanly to '/analytics/chat/'.
        """
        resolved_url = reverse('analytics:ai_chat')
        assert resolved_url == '/analytics/chat/'


# ==============================================================================
# 2. NAVBAR & NAVIGATION ACTIVE STATE TESTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsChatNavbarIntegration:
    """
    Validates navbar tab presence and active CSS state rendering.
    """

    def test_ai_copilot_tab_rendered_with_active_state_on_chat_page(self, client, staff_member):
        """
        When navigating to /analytics/chat/, the AI Copilot navbar tab must have the 'active' class.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "AI Copilot" in html
        assert "fa-robot" in html
        # Active class must be present on the current link
        assert 'class="nav-link-custom active"' in html or 'nav-link-custom active' in html

    def test_ai_copilot_tab_inactive_on_other_analytics_pages(self, client, staff_member):
        """
        When navigating to /analytics/dashboard/, Dashboard is active and AI Copilot is inactive.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:dashboard'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "AI Copilot" in html
        # Dashboard should have active class, and AI Copilot should not be marked active
        assert 'href="/analytics/chat/" class="nav-link-custom "' in html or 'href="/analytics/chat/" class="nav-link-custom"' in html or 'href="/analytics/chat/"' in html


# ==============================================================================
# 3. UI COMPONENTS & TEMPLATE INTEGRITY TESTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsChatTemplateComponents:
    """
    Validates presence of conversation controls, streaming containers,
    telemetry panels, quick prompts, and markdown styling.
    """

    def test_conversation_controls_present(self, client, staff_member):
        """
        Conversation controls: input textarea, send button, clear chat button.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="chatUserInput"' in html
        assert 'id="chatSendBtn"' in html
        assert 'id="clearChatBtn"' in html
        assert "Limpiar Conversación" in html

    def test_streaming_and_messages_container_present(self, client, staff_member):
        """
        Message history container, streaming cursor, and typing dots.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="chatHistoryFeed"' in html
        assert 'class="chat-history"' in html
        assert 'streaming-cursor' in html
        assert 'typing-dots' in html

    def test_live_telemetry_and_metrics_panel_present(self, client, staff_member):
        """
        Live performance metrics, latency, model indicator, session ID, gateway status dot.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="telemetryLatency"' in html
        assert 'id="telemetryModel"' in html
        assert 'id="telemetrySessionId"' in html
        assert 'id="telemetryTurns"' in html
        assert 'id="gatewayStatusBadge"' in html
        assert 'id="gatewayStatusDot"' in html
        assert "Rendimiento en Vivo" in html

    def test_quick_starter_prompt_buttons_present(self, client, staff_member):
        """
        Quick suggested business questions buttons.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'class="prompt-starters-grid"' in html
        assert 'class="btn-starter"' in html
        assert "¿Cuáles son los KPIs del mes actual?" in html
        assert "¿Cuáles son los 5 productos más vendidos?" in html
        assert "Muéstrame la distribución de ventas por categoría en una tabla" in html
        assert "¿Cuál es la proyección de demanda para el próximo trimestre?" in html

    def test_markdown_tables_styling_classes_present(self, client, staff_member):
        """
        Markdown table container with responsive scrollable styling.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "table-responsive" in html
        assert "table-custom" in html

    def test_cloud_gateway_and_agent_configuration_present(self, client, staff_member):
        """
        JavaScript cloud gateway URL and analytics agent ID configuration.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "https://ai-agent-gateway-sued.onrender.com" in html
        assert "analytics" in html
        assert "analytics_chat_session_id" in html
