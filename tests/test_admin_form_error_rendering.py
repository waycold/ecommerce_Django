"""
tests/test_admin_form_error_rendering.py

Fase 4, Tarea 1: a superuser who submits an invalid product (create/edit) or
profile-photo form must see, on the re-rendered page, a message naming the
specific field that failed validation -- not a blank form with no indication
of the cause.

apps/catalog/views.py::create_product and ::edit_product, and
apps/orders/views.py::agregar_imagen already pass the bound form (with its
errors) back to the template on an invalid POST; the only defect is that
templates/create_product.html, templates/edit_product.html and
templates/profile.html never render form.errors / field.errors. These tests
exercise the full request/response cycle (not just form.is_valid() in
isolation) so a regression in either the view's context or the template's
rendering would fail them.

Each invalid input below was confirmed to actually fail validation (and the
exact Django/Pillow error text captured) by running the real forms in a
Django shell before writing the assertions -- see apps/catalog/forms.py's
product_form and apps/orders/forms.py's image_form.
"""
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.catalog.models import Item
from apps.orders.models import Profile


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser(
        username="admin_forms", email="admin_forms@example.com", password="SuperPassword123!"
    )


VALID_PRODUCT_PAYLOAD = {
    "description": "A description",
    "price": "10.00",
    "cost": "5.00",
    "stock": "5",
    "minimum_stock": "1",
}


@pytest.mark.django_db
class TestCreateProductFormErrors:
    def test_empty_title_shows_required_error(self, client, superuser):
        """Item.title is CharField(max_length=300) with no blank=True, so an
        empty title is required and genuinely fails product_form.is_valid()."""
        client.force_login(superuser)

        response = client.post(
            reverse("catalog:create_product"),
            {**VALID_PRODUCT_PAYLOAD, "title": ""},
        )

        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert "This field is required." in html
        assert not Item.objects.filter(description="A description").exists()

    def test_title_over_max_length_shows_specific_error(self, client, superuser):
        """A 301-character title exceeds CharField(max_length=300)."""
        client.force_login(superuser)

        response = client.post(
            reverse("catalog:create_product"),
            {**VALID_PRODUCT_PAYLOAD, "title": "x" * 301},
        )

        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert "Ensure this value has at most 300 characters (it has 301)." in html
        assert not Item.objects.filter(price=Decimal("10.00")).exists()

    def test_invalid_image_file_shows_pillow_error(self, client, superuser):
        """Item.img is an ImageField; a non-image upload trips Pillow's validator."""
        client.force_login(superuser)
        bad_file = SimpleUploadedFile(
            "not_an_image.txt", b"this is definitely not image data", content_type="text/plain"
        )

        response = client.post(
            reverse("catalog:create_product"),
            {**VALID_PRODUCT_PAYLOAD, "title": "A Valid Title", "img": bad_file},
        )

        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert (
            "Upload a valid image. The file you uploaded was either not an image "
            "or a corrupted image." in html
        )
        assert not Item.objects.filter(title="A Valid Title").exists()


@pytest.mark.django_db
class TestEditProductFormErrors:
    @pytest.fixture
    def existing_item(self, db):
        return Item.objects.create(
            title="Original Title",
            price=Decimal("20.00"),
            cost=Decimal("10.00"),
            stock=3,
            minimum_stock=0,
        )

    def test_empty_title_shows_required_error_and_does_not_save(self, client, superuser, existing_item):
        client.force_login(superuser)

        response = client.post(
            reverse("catalog:edit_product", kwargs={"slug": existing_item.slug}),
            {**VALID_PRODUCT_PAYLOAD, "title": "", "price": "20.00", "cost": "10.00", "stock": "3", "minimum_stock": "0"},
        )

        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert "This field is required." in html
        existing_item.refresh_from_db()
        assert existing_item.title == "Original Title"

    def test_invalid_image_file_shows_pillow_error(self, client, superuser, existing_item):
        client.force_login(superuser)
        bad_file = SimpleUploadedFile(
            "not_an_image.txt", b"this is definitely not image data", content_type="text/plain"
        )

        response = client.post(
            reverse("catalog:edit_product", kwargs={"slug": existing_item.slug}),
            {
                "title": "Original Title",
                "description": "",
                "price": "20.00",
                "cost": "10.00",
                "stock": "3",
                "minimum_stock": "0",
                "img": bad_file,
            },
        )

        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert (
            "Upload a valid image. The file you uploaded was either not an image "
            "or a corrupted image." in html
        )


@pytest.mark.django_db
class TestProfileImageFormErrors:
    def test_invalid_image_file_shows_pillow_error(self, client, superuser):
        """Profile.image is an ImageField (same validator as Item.img)."""
        client.force_login(superuser)
        bad_file = SimpleUploadedFile(
            "not_an_image.txt", b"this is definitely not image data", content_type="text/plain"
        )

        response = client.post(reverse("orders:agregar_imagen"), {"image": bad_file})

        assert response.status_code == 200
        html = response.content.decode("utf-8")
        assert (
            "Upload a valid image. The file you uploaded was either not an image "
            "or a corrupted image." in html
        )
        profile = Profile.objects.get(user=superuser)
        assert not profile.image
