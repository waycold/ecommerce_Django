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
from django.urls import reverse
from django.contrib.auth.models import User
from apps.catalog.models import Category, Brand, Supplier, Item



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

        # f) Dynamic Chart.js Integration
        assert "btn-table-chart" in html
        assert "Ver Gráfico" in html
        assert "chart-type-selector" in html
        assert "chart-canvas-wrapper" in html
        assert "renderChartForTable" in html

        # g) Export Module (Markdown, CSV, JSON, PDF)
        assert "exportDropdownBtn" in html
        assert "exportMarkdownBtn" in html
        assert "exportCsvBtn" in html
        assert "exportJsonBtn" in html
        assert "exportPdfBtn" in html
        assert "@media print" in html

        # h) Dynamic Telemetry & Gateway Heartbeat
        assert "telemetryTokens" in html
        assert "checkGatewayHealth" in html

    def test_markdown_parser_safe_delimiters_and_no_italic_corruption(self, client, staff_user):
        """
        Verify that parseMarkdown uses safe delimiters without underscores (%%%HTMLPART, %%%DIRECTCHARTPART, etc.)
        and that it renders tables with toolbar actions without leaving broken placeholders.
        """
        import json
        import subprocess

        client.force_login(staff_user)
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        # Verify safe delimiters present in JS code
        assert "%%%HTMLPART" in html
        assert "%%%DIRECTCHARTPART" in html
        assert "%%%CODEBLOCKPART" in html
        assert "%%%INLINECODEPART" in html

        # Extract parseMarkdown and escapeHtml from the template
        fn_start = html.find("function escapeHtml")
        fn_end = html.find("// 5. Chart.js Dynamic Rendering Engine")
        extracted_js = html[fn_start:fn_end]

        js_test = f"""
        let tableCounter = 0;
        {extracted_js}

        const sampleMarkdown = `
Aquí está el análisis para _ventas del mes_:

| Categoría | Ventas ($) | Cantidad |
| :--- | :---: | ---: |
| Electrónica | 120,000 | 450 |
| Calzado | 85,000 | 920 |

Puntos clave:
- Mayor volumen en *calzado*.
- Mayor margen en **electrónica**.

Segundo reporte de _inventario_:

| Item | Stock |
| --- | --- |
| Laptop | 15 |
| Mouse | 150 |
        `;

        const result = parseMarkdown(sampleMarkdown);
        const hasBrokenTokens = /HTMLPART/i.test(result);
        const tableCardCount = (result.match(/table-container-card/g) || []).length;
        const hasVerGrafico = result.includes('Ver Gráfico');
        const hasCsv = result.includes('CSV');
        const hasCopiar = result.includes('Copiar');

        console.log(JSON.stringify({{
            hasBrokenTokens,
            tableCardCount,
            hasVerGrafico,
            hasCsv,
            hasCopiar
        }}));
        """
        res = subprocess.run(["node", "-e", js_test], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())
        assert not data["hasBrokenTokens"], "parseMarkdown left broken HTMLPART placeholders"
        assert data["tableCardCount"] == 2, f"Expected 2 table cards, got {data['tableCardCount']}"
        assert data["hasVerGrafico"], "Expected 'Ver Gráfico' button in table toolbar"
        assert data["hasCsv"], "Expected 'CSV' button in table toolbar"
        assert data["hasCopiar"], "Expected 'Copiar' button in table toolbar"

    def test_complex_markdown_multi_table_mixed_formatting_parser_resilience(self, client, staff_user):
        """
        Validates that a complex multi-table response containing mixed formatting:
        - Multiple tables (3 distinct tables)
        - Italic with single underscore `_text_` and asterisk `*text*`
        - Bold with double underscore `__text__` and double asterisk `**text**`
        - Snake_case variable names (`Industrial_and_Scientific`, `calculate_margins_service`)
        - Bulleted lists (- and *) and numbered lists (1., 2.)
        - Inline code with underscores
        - Fenced code blocks
        - Direct JSON chart blocks
        - Markdown links [text](url)
        - Multi-line paragraphs and single line breaks
        parses 100% cleanly without leaving broken placeholder tokens (HTMLPART, CODEBLOCKPART, etc.).
        """
        import json
        import subprocess

        client.force_login(staff_user)
        url = reverse("analytics:ai_chat")
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        fn_start = html.find("function escapeHtml")
        fn_end = html.find("// 5. Chart.js Dynamic Rendering Engine")
        extracted_js = html[fn_start:fn_end]

        complex_markdown = r"""
# Reporte Ejecutivo de Ventas y Márgenes - Diciembre 2025

A continuación se detalla el desglose por categorías líderes para el período _2025-12-01_ a _2025-12-31_:

| Ranking | Categoría | Ingresos ($) | Margen Bruto (%) | Unidades |
| :---: | :--- | ---: | :---: | ---: |
| 1 | Industrial_and_Scientific | $95,000.00 | 48.5% | 1,250 |
| 2 | Cell_Phones_and_Accessories | $78,500.00 | 42.0% | 3,100 |
| 3 | Electronics | $54,200.00 | 38.0% | 890 |
| 4 | Home_and_Kitchen | $36,800.00 | 35.2% | 1,420 |
| 5 | Automotive | $22,100.00 | 31.8% | 610 |

### Observaciones y Conclusiones:
* La categoría **Industrial_and_Scientific** lidera con un margen del __48.5%__.
* El producto destacado es `industrial_sensor_pro_v2` con _alto rendimiento_ y campo `gross_margin_pct`.
- Crecimiento sostenido en **Cell_Phones_and_Accessories**.
- Enlaces de referencia: [Ver Portal Analytics](https://analytics.example.com/portal_2025).

1. Primer paso: reabastecer inventario de *sensores industriales*.
2. Segundo paso: optimizar logística en **Home_and_Kitchen**.

```json-chart
{"type": "bar", "labels": ["Industrial_and_Scientific", "Cell_Phones_and_Accessories", "Electronics"], "datasets": [{"data": [95000, 78500, 54200]}]}
```

```python
def verify_margin_aggregation(category_name, revenue, cost):
    margin = (revenue - cost) / revenue * 100.0
    return {"category": category_name, "margin_pct": round(margin, 2)}
```

### Tabla Secundaria: Rendimiento por Canal de Pago

| Canal de Pago | Transacciones | Total Facturado | Tasa Aprobación |
| :--- | :---: | ---: | ---: |
| CREDIT_CARD | 4,200 | $185,000.00 | 98.2% |
| TRANSFER | 1,150 | $68,500.00 | 99.5% |
| DEBIT_CARD | 820 | $33,100.00 | 97.8% |

### Tabla Terciaria: Resumen de Stock Crítico

| SKU | Descripción | Stock Actual | Punto Reorden | Estado |
| :--- | :--- | :---: | :---: | :---: |
| IND-9901 | Sensor Láser Industrial Pro | 4 | 15 | CRÍTICO |
| CEL-4421 | Funda Ultra Resistente Armor | 8 | 20 | BAJO |
| AUT-1029 | Filtro de Aceite Sintético | 0 | 10 | AGOTADO |

Fin del reporte consolidado.
"""

        js_test = f"""
        let tableCounter = 0;
        {extracted_js}

        const inputMarkdown = {json.dumps(complex_markdown)};
        const outputHtml = parseMarkdown(inputMarkdown);

        // Verification checks
        const hasBrokenHtmlPart = /(?:HTMLPART|%%%HTMLPART|@@@HTMLPART)/i.test(outputHtml);
        const hasBrokenCodeBlock = /(?:CODEBLOCKPART|%%%CODEBLOCK|@@@CODEBLOCK)/i.test(outputHtml);
        const hasBrokenInlineCode = /(?:INLINECODEPART|%%%INLINECODE|@@@INLINECODE)/i.test(outputHtml);
        const hasBrokenDirectChart = /(?:DIRECTCHARTPART|%%%DIRECTCHART|@@@DIRECTCHART)/i.test(outputHtml);

        const tableContainerCards = (outputHtml.match(/class="table-container-card"/g) || []).length;
        const directChartBoxes = (outputHtml.match(/class="direct-chart-box"/g) || []).length;
        const codeBlockWrappers = (outputHtml.match(/class="code-block-wrapper"/g) || []).length;
        const inlineCodeCount = (outputHtml.match(/class="inline-code"/g) || []).length;
        const boldTagsCount = (outputHtml.match(/<strong>/g) || []).length;
        const italicTagsCount = (outputHtml.match(/<em>/g) || []).length;
        const ulCount = (outputHtml.match(/<ul/g) || []).length;
        const olCount = (outputHtml.match(/<ol/g) || []).length;

        console.log(JSON.stringify({{
            hasBrokenHtmlPart,
            hasBrokenCodeBlock,
            hasBrokenInlineCode,
            hasBrokenDirectChart,
            tableContainerCards,
            directChartBoxes,
            codeBlockWrappers,
            inlineCodeCount,
            boldTagsCount,
            italicTagsCount,
            ulCount,
            olCount,
            outputHtmlLength: outputHtml.length
        }}));
        """
        res = subprocess.run(["node", "-e", js_test], capture_output=True, text=True, check=True)
        data = json.loads(res.stdout.strip())

        assert not data["hasBrokenHtmlPart"], f"parseMarkdown produced broken HTMLPART tokens: {data}"
        assert not data["hasBrokenCodeBlock"], f"parseMarkdown produced broken CODEBLOCK tokens: {data}"
        assert not data["hasBrokenInlineCode"], f"parseMarkdown produced broken INLINECODE tokens: {data}"
        assert not data["hasBrokenDirectChart"], f"parseMarkdown produced broken DIRECTCHART tokens: {data}"
        assert data["tableContainerCards"] == 3, f"Expected 3 table containers, got {data['tableContainerCards']}"
        assert data["directChartBoxes"] == 1, f"Expected 1 direct chart box, got {data['directChartBoxes']}"
        assert data["codeBlockWrappers"] == 1, f"Expected 1 code block wrapper, got {data['codeBlockWrappers']}"
        assert data["inlineCodeCount"] >= 2, f"Expected inline code tags, got {data['inlineCodeCount']}"
        assert data["boldTagsCount"] >= 4, f"Expected bold tags, got {data['boldTagsCount']}"
        assert data["italicTagsCount"] >= 3, f"Expected italic tags, got {data['italicTagsCount']}"
        assert data["ulCount"] >= 1, f"Expected unordered list, got {data['ulCount']}"
        assert data["olCount"] >= 1, f"Expected ordered list, got {data['olCount']}"


