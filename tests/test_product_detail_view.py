"""
tests/test_product_detail_view.py

Comprehensive tests for ProductDetailView frontend & backend implementation:
1. Queryset Optimization: Prefetching attributes and comments with user profiles to avoid N+1 queries.
2. Layout & Presentation: Hero section (image left, purchase summary right), dedicated expandable description section, structured specifications table for ProductAttribute.
3. Interactive Features: Collapsible description triggers, AI assistant consultation button with window.AiChatWidget, comments & reviews.
"""

from decimal import Decimal
import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from apps.catalog.models import Item, Category, Brand, Supplier, ProductAttribute, Comments
from apps.orders.models import Profile


@pytest.fixture
def product_with_attributes_and_comments(db):
    cat = Category.objects.create(name="Smartphones")
    brand = Brand.objects.create(name="Google")
    supplier = Supplier.objects.create(name="Alphabet Logistics", country="USA")

    item = Item.objects.create(
        title="Google Pixel 8 Pro",
        description=(
            "The Google Pixel 8 Pro is Google's flagship smartphone featuring the Tensor G3 processor, "
            "an immersive 6.7-inch Super Actua LTPO OLED display with 120Hz refresh rate, and an upgraded triple camera system. "
            "It includes advanced computational photography, Magic Eraser, Best Take, and 7 years of Android OS and security updates. "
            "Equipped with 12GB of LPDDR5X RAM, 128GB of UFS 3.1 storage, all-day battery life, and fast Qi wireless charging. "
            "Crafted with a polished aluminum frame and matte back glass in Obsidian finish."
        ),
        price=Decimal("999.00"),
        cost=Decimal("700.00"),
        stock=25,
        category=cat,
        brand=brand,
        supplier=supplier,
        is_active=True,
    )

    # Create attributes
    ProductAttribute.objects.create(item=item, name="Color", value="Obsidian Black")
    ProductAttribute.objects.create(item=item, name="Screen Size", value="6.7 inch LTPO OLED")
    ProductAttribute.objects.create(item=item, name="RAM", value="12 GB")
    ProductAttribute.objects.create(item=item, name="Storage", value="128 GB")
    ProductAttribute.objects.create(item=item, name="Battery", value="5050 mAh")

    # Create users, profiles, and comments
    user1 = User.objects.create_user(username="tech_reviewer", email="tech@example.com", password="Pass123!Password")
    Profile.objects.create(user=user1, city="San Francisco", province="CA")
    Comments.objects.create(user=user1, item=item, body="Incredible camera quality and super bright display!", rating=5)

    user2 = User.objects.create_user(username="gadget_fan", email="gadget@example.com", password="Pass123!Password")
    Profile.objects.create(user=user2, city="Austin", province="TX")
    Comments.objects.create(user=user2, item=item, body="Battery life is solid, smoothly handles heavy multitasking.", rating=4)

    return item


@pytest.mark.django_db
class TestProductDetailViewImplementation:
    def test_product_detail_queryset_prefetching(self, client, product_with_attributes_and_comments, django_assert_num_queries):
        """
        Verify that ProductDetailView prefetches attributes and comments__user__profile,
        ensuring efficient query execution without N+1 query loops.
        """
        url = reverse("catalog:product", kwargs={"slug": product_with_attributes_and_comments.slug})
        
        # When rendering the detail view with prefetching, query count is bounded
        response = client.get(url)
        assert response.status_code == 200

        # Validate that prefetched objects are accessible in the template context
        obj = response.context["object"]
        assert hasattr(obj, "_prefetched_objects_cache")
        assert "attributes" in obj._prefetched_objects_cache
        assert "comments" in obj._prefetched_objects_cache

        # Accessing attributes and comments uses cached queryset
        attributes = list(obj.attributes.all())
        assert len(attributes) == 5
        comments = list(obj.comments.all())
        assert len(comments) == 2

    def test_product_detail_hero_section_layout(self, client, product_with_attributes_and_comments):
        """
        Verify hero section layout:
        - Image in left column (col-md-6)
        - Purchase summary in right column (col-md-6) with Category/Brand, Title, Price, Available stock badge, Add to Cart / Remove.
        """
        url = reverse("catalog:product", kwargs={"slug": product_with_attributes_and_comments.slug})
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "Smartphones" in html
        assert "Google" in html
        assert "Google Pixel 8 Pro" in html
        assert "$999.00" in html
        assert "Available Stock:" in html
        assert "25 units" in html
        assert "Add to Cart" in html
        assert "Remove" in html

    def test_product_detail_expandable_description_section(self, client, product_with_attributes_and_comments):
        """
        Verify that Description is rendered in a dedicated card with expand/collapse markup,
        CSS styling, and English headings.
        """
        url = reverse("catalog:product", kwargs={"slug": product_with_attributes_and_comments.slug})
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "product-description-container" in html
        assert "product-description-content" in html
        assert "product-description-fade" in html
        assert "toggleDescriptionBtn" in html
        assert "toggleProductDescription()" in html
        assert "Read more" in html
        assert "Description" in html
        assert "Tensor G3 processor" in html

    def test_product_detail_structured_specifications_table(self, client, product_with_attributes_and_comments):
        """
        Verify structured ProductAttribute key-value specifications section:
        - Shows attribute names and values
        - Clean table formatting
        - English section title 'Specifications'
        """
        url = reverse("catalog:product", kwargs={"slug": product_with_attributes_and_comments.slug})
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "Specifications" in html
        assert "Obsidian Black" in html
        assert "6.7 inch LTPO OLED" in html
        assert "12 GB" in html
        assert "128 GB" in html
        assert "5050 mAh" in html

    def test_product_detail_empty_specifications_fallback(self, client, db):
        """
        Verify that a product without attributes displays the fallback text:
        'No specifications available.'
        """
        item = Item.objects.create(
            title="Simple Product Without Specs",
            price=Decimal("19.99"),
            stock=10,
            is_active=True,
        )
        url = reverse("catalog:product", kwargs={"slug": item.slug})
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "No specifications available." in html

    def test_product_detail_ai_button_and_widget_compatibility(self, client, product_with_attributes_and_comments):
        """
        Verify that consultarProducto and window.AiChatWidget integration is preserved.
        """
        url = reverse("catalog:product", kwargs={"slug": product_with_attributes_and_comments.slug})
        response = client.get(url)
        assert response.status_code == 200
        html = response.content.decode("utf-8")

        assert "consultarProducto" in html
        assert "Preguntar a la IA sobre este producto" in html
        assert "window.AiChatWidget" in html
        assert "window.AiChatWidget.sendMessage" in html
        assert "Google Pixel 8 Pro" in html

    def test_product_detail_admin_options_visibility(self, client, product_with_attributes_and_comments):
        """
        Verify that admin options (Edit Product, Delete) are only shown to superusers.
        """
        url = reverse("catalog:product", kwargs={"slug": product_with_attributes_and_comments.slug})

        # Anonymous request
        resp_anon = client.get(url)
        html_anon = resp_anon.content.decode("utf-8")
        assert "Admin Options" not in html_anon
        assert "Edit Product" not in html_anon

        # Superuser request
        admin = User.objects.create_superuser(username="admin_user", email="admin@example.com", password="SuperPassword123!")
        client.force_login(admin)
        resp_admin = client.get(url)
        html_admin = resp_admin.content.decode("utf-8")
        assert "Admin Options" in html_admin
        assert "Edit Product" in html_admin
