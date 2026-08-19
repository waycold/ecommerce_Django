"""
tests/test_chat_widget_integration.py

Comprehensive test suite verifying the AI Chat Widget integration:
- Context processor: user_jwt_token (authenticated vs anonymous)
- Settings registration
- Template rendering in base.html, home.html, and product.html
- Static JavaScript file integrity and API contracts
"""

import os
import jwt
from django.conf import settings
from django.contrib.auth.models import User, AnonymousUser
from django.test import TestCase, RequestFactory
from django.urls import reverse
from product.context_processors import user_jwt_token
from product.models import Item, Category, Brand, Supplier


class TestChatWidgetContextProcessor(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="buyer_test",
            email="buyer@test.com",
            password="securepassword123",
        )

    def test_anonymous_user_token_is_none(self):
        request = self.factory.get("/")
        request.user = AnonymousUser()
        context = user_jwt_token(request)
        self.assertIn("user_jwt_token", context)
        self.assertIsNone(context["user_jwt_token"])

    def test_authenticated_user_token_is_valid_jwt(self):
        request = self.factory.get("/")
        request.user = self.user
        context = user_jwt_token(request)
        self.assertIn("user_jwt_token", context)
        token = context["user_jwt_token"]
        self.assertIsNotNone(token)
        self.assertIsInstance(token, str)

        # Decode token and verify payload
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        self.assertEqual(payload["user_id"], self.user.id)
        self.assertEqual(payload["username"], self.user.username)
        self.assertEqual(payload["email"], self.user.email)
        self.assertEqual(payload["is_staff"], False)
        self.assertEqual(payload["is_superuser"], False)


class TestChatWidgetSettingsAndTemplates(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Laptops")
        self.brand = Brand.objects.create(name="Dell")
        self.supplier = Supplier.objects.create(name="Dell Inc", country="USA")
        self.item = Item.objects.create(
            title="Dell XPS 15",
            price=1500.00,
            cost=1200.00,
            stock=5,
            category=self.category,
            brand=self.brand,
            supplier=self.supplier,
        )
        self.user = User.objects.create_user(
            username="testuser_widget",
            email="widget@test.com",
            password="password123",
        )

    def test_context_processor_registered_in_settings(self):
        context_processors = settings.TEMPLATES[0]["OPTIONS"]["context_processors"]
        self.assertIn("product.context_processors.user_jwt_token", context_processors)

    def test_base_template_anonymous_renders_widget_without_token(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("js/chat-widget.js", content)
        self.assertIn('data-api-url="https://ai-agent-gateway-sued.onrender.com"', content)
        self.assertIn('data-agent="ecommerce"', content)
        self.assertIn('data-title="Asistente de Compras"', content)
        self.assertIn('data-primary-color="#2563eb"', content)
        self.assertNotIn("data-user-token=", content)

    def test_base_template_authenticated_renders_widget_with_token(self):
        self.client.login(username="testuser_widget", password="password123")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("js/chat-widget.js", content)
        self.assertIn("data-user-token=", content)

    def test_home_template_does_not_contain_old_widget_include(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        # Ensure old ai_chat_widget elements or specific old titles aren't directly embedded twice
        self.assertNotIn("Project AI Assistant", content)

    def test_product_detail_contains_ai_consultation_button(self):
        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        self.assertIn("consultarProducto", content)
        self.assertIn("Preguntar a la IA sobre este producto", content)
        self.assertIn("window.AiChatWidget.sendMessage", content)
        self.assertIn("window.AiChatWidget.setAgent", content)
        self.assertIn("Dell XPS 15", content)


class TestChatWidgetStaticFileIntegrity(TestCase):
    def test_chat_widget_js_file_exists_and_implements_spec(self):
        js_path = os.path.join(settings.BASE_DIR, "product", "static", "js", "chat-widget.js")
        self.assertTrue(os.path.exists(js_path), "chat-widget.js static file must exist")

        with open(js_path, "r", encoding="utf-8") as f:
            js_content = f.read()

        # Shadow DOM encapsulation
        self.assertIn("attachShadow", js_content)
        self.assertIn("ai-chat-widget-root", js_content)

        # Global API exposure
        self.assertIn("window.AiChatWidget", js_content)
        self.assertIn("open:", js_content)
        self.assertIn("close:", js_content)
        self.assertIn("toggle:", js_content)
        self.assertIn("setAgent:", js_content)
        self.assertIn("sendMessage:", js_content)
        self.assertIn("setUserToken:", js_content)
        self.assertIn("clearSession:", js_content)

        # Microservice communication endpoints
        self.assertIn("/api/v1/chat/stream", js_content)
        self.assertIn("/api/v1/chat", js_content)

        # Session & Storage
        self.assertIn("sessionStorage", js_content)
        self.assertIn("ai_chat_session_id", js_content)

        # Markdown & Formatting
        self.assertIn("renderMarkdown", js_content)
        self.assertIn("code-container", js_content)
        self.assertIn("chat-link", js_content)
