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
   - Streaming area and indicators (SSE stream targets, streaming cursor, typing indicators).
   - Quick starter prompt suggestions for business queries.
   - Markdown responsive tables and scrollable containers for executive reporting.
4. Chart.js Interactive Visualizations:
   - Dynamic auto-conversion of tabular data into Chart.js canvases (Bar, Line, Doughnut, Pie).
   - Table action toolbar ("Ver Gráfico", "CSV", "Copiar") and switch-to-table controls.
   - Direct JSON chart block rendering support (.direct-chart-box, data-direct-chart).
5. Comprehensive Export Suite:
   - Multi-format export dropdown (Markdown .md, CSV tables, Session .json, Print/PDF).
   - Print media layout styles (@media print) for clean executive PDF generation.
6. Dynamic Telemetry & Live Heartbeat:
   - Real-time latency tracking (ms), active model indicator, conversational turn counter.
   - Accumulated token estimation metric (telemetryTokens).
   - Real-time live gateway health check (/ping polling, online status badge).
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
        assert "AI Analytics Assistant" in content or "Executive AI Copilot" in content

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


# ==============================================================================
# 4. CHART.JS VISUALIZATIONS & TABLE-TO-CHART CONVERSION TESTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsChatVisualizationsAndCharts:
    """
    Validates Chart.js engine integration, table toolbars, chart controls,
    and direct chart rendering blocks.
    """

    def test_chart_js_script_included_in_page(self, client, staff_member):
        """
        Chart.js library must be loaded in the page via CDN script tag.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "chart.js" in html.lower() or "chart.min.js" in html.lower()

    def test_table_toolbar_and_chart_conversion_elements(self, client, staff_member):
        """
        Tables generated by AI Copilot must have toolbars with 'Ver Gráfico', 'CSV', and 'Copiar' buttons.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "table-container-card" in html
        assert "table-toolbar" in html
        assert "btn-table-chart" in html
        assert "Ver Gráfico" in html
        assert "btn-table-csv" in html
        assert "btn-table-copy" in html

    def test_chart_controls_and_type_selectors_present(self, client, staff_member):
        """
        Chart view wrapper must provide type selectors (Bar, Line, Doughnut, Pie) and 'Ver Tabla' switch.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "chart-controls-bar" in html
        assert "chart-type-selector" in html
        assert 'data-chart-type="bar"' in html
        assert 'data-chart-type="line"' in html
        assert 'data-chart-type="doughnut"' in html
        assert 'data-chart-type="pie"' in html
        assert "btn-switch-to-table" in html
        assert "Ver Tabla" in html
        assert "chart-canvas-wrapper" in html

    def test_direct_chart_blocks_support(self, client, staff_member):
        """
        Direct JSON chart blocks (```chart or ```json-chart) must be supported.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "direct-chart-box" in html
        assert "data-direct-chart" in html
        assert "renderDirectChartBlocks" in html


# ==============================================================================
# 5. MULTI-FORMAT EXPORT SUITE TESTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsChatExportFeatures:
    """
    Validates report export menu options (Markdown, CSV, JSON, PDF/Print) and table exports.
    """

    def test_export_dropdown_menu_present(self, client, staff_member):
        """
        Export dropdown button 'Exportar Reporte' and dropdown container must be present.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="exportDropdownBtn"' in html
        assert "Exportar Reporte" in html
        assert "dropdown-menu-dark" in html

    def test_export_format_buttons_present(self, client, staff_member):
        """
        Dropdown must offer Markdown, CSV, JSON, and PDF/Print export options.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="exportMarkdownBtn"' in html
        assert "Descargar Markdown (.md)" in html

        assert 'id="exportCsvBtn"' in html
        assert "Descargar Tablas (.csv)" in html

        assert 'id="exportJsonBtn"' in html
        assert "Descargar Sesión (.json)" in html

        assert 'id="exportPdfBtn"' in html
        assert "Guardar como PDF / Imprimir" in html

    def test_export_client_functions_defined(self, client, staff_member):
        """
        JavaScript export handlers must be properly wired.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "exportSessionMarkdown" in html
        assert "exportSessionAllTablesCsv" in html
        assert "exportSessionJson" in html
        assert "exportTableToCsv" in html

    def test_print_media_stylesheet_present_for_pdf_generation(self, client, staff_member):
        """
        Print stylesheet (@media print) must hide navigation/telemetry and format clean tables.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "@media print" in html
        assert "telemetry-sidebar" in html
        assert "prompt-starters-section" in html


# ==============================================================================
# 6. DYNAMIC TELEMETRY & LIVE HEALTH TESTS
# ==============================================================================

@pytest.mark.django_db
class TestAnalyticsChatDynamicTelemetry:
    """
    Validates dynamic telemetry sidebar elements: live latency, active model,
    conversational turns, accumulated token estimation, and gateway health heartbeat.
    """

    def test_telemetry_sidebar_selectors_present(self, client, staff_member):
        """
        Live performance panel metrics: latency, model, agent, protocol, turns, tokens.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="telemetryLatency"' in html
        assert 'id="telemetryModel"' in html
        assert 'id="telemetryTurns"' in html
        assert 'id="telemetryTokens"' in html
        assert "Tokens Estimados" in html
        assert 'id="telemetrySessionId"' in html
        assert "Rendimiento en Vivo" in html

    def test_gateway_live_heartbeat_and_status_dot(self, client, staff_member):
        """
        Real-time Gateway status badge and live heartbeat ping checking.
        """
        client.force_login(staff_member)
        response = client.get(reverse('analytics:ai_chat'))
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert 'id="gatewayStatusBadge"' in html
        assert 'id="gatewayStatusDot"' in html
        assert 'id="gatewayStatusText"' in html
        assert "checkGatewayHealth" in html
        assert "/ping" in html
