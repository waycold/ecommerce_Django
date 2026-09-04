"""
tests/test_internal_csrf_exemption.py

Regression coverage for the CSRF-vs-shared-secret bug that blocked the
Chatbot-Engine-Gateway with 403s on:
    POST /api/v1/internal/auth/validate-token/
    POST /api/v1/internal/catalog/items/verify/

Root cause: apps.core.authentication.views.validate_token_view and
apps.catalog.internal_views.catalog_items_verify_view are plain Django
function views sitting behind django.middleware.csrf.CsrfViewMiddleware
(config/settings/base.py MIDDLEWARE) without @csrf_exempt. CsrfViewMiddleware
enforces its check on every POST/PUT/PATCH/DELETE regardless of the
X-Internal-Secret header used by InternalSecretMiddleware, and the Gateway
is a server-to-server client that never holds a Django session/CSRF cookie
-- so the request never carries a csrftoken cookie and Django rejects it
with 403 "CSRF cookie not set." before the view body ever runs. GET-only
internal endpoints (catalog/search, analytics/query, analytics/metrics)
were unaffected because CsrfViewMiddleware only inspects unsafe HTTP
methods.

Why the existing contract tests (tests/test_auth_contract.py,
tests/test_catalog_contract.py) never caught this: they use pytest-django's
`client` fixture, which builds a plain django.test.Client() with the
default enforce_csrf_checks=False -- the test client silently bypasses the
exact protection that broke real Gateway traffic. This file uses an
explicit enforce_csrf_checks=True client to close that blind spot.
"""
import json

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from apps.core import internal_urls
from apps.core.authentication.services import generate_user_jwt_token
from apps.core.authentication.views import validate_token_view
from apps.catalog.internal_views import catalog_items_verify_view
from apps.catalog.models import EMBEDDING_DIM


# Expected HTTP method per apps.core.internal_urls route `name` -- duplicated
# from tests/test_database_ai_endpoints.py's INTERNAL_ENDPOINT_METHODS on
# purpose so the two regression suites stay independent of each other.
ALL_INTERNAL_ENDPOINT_METHODS = {
    'internal_health': 'GET',
    'internal_auth_validate_token': 'POST',
    'internal_catalog_search': 'GET',
    'internal_catalog_semantic_search': 'POST',
    'internal_catalog_reviews_summary': 'GET',
    'internal_inventory_health': 'GET',
    'internal_analytics_metrics': 'GET',
    'internal_analytics_query': 'GET',
    'internal_analytics_margins': 'GET',
    'internal_analytics_funnel': 'GET',
    'internal_customers_insights': 'GET',
    'internal_raw_sql_sandbox': 'POST',
    'internal_catalog_vector_search': 'POST',
    'internal_catalog_embeddings_similar': 'POST',
    'internal_catalog_embeddings_pending': 'GET',
    'internal_catalog_embeddings_upsert': 'POST',
    'internal_catalog_embeddings_mark_error': 'POST',
    'internal_catalog_items_verify': 'POST',
    'internal_catalog_facets': 'GET',
}


@pytest.fixture
def strict_csrf_client():
    """A test client that enforces CSRF exactly like a real browser/HTTP
    client would -- unlike the default `client` fixture, it will not
    silently swallow a missing @csrf_exempt on a view."""
    return Client(enforce_csrf_checks=True)


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="csrf_staff_member",
        email="csrf_staff@example.com",
        password="securepassword123",
        is_staff=True,
        is_active=True,
    )


class TestInternalViewsAreCsrfExempt:
    """
    Direct assertions that the two previously-broken views carry the
    csrf_exempt marker Django's CsrfViewMiddleware checks for
    (`callback.csrf_exempt is True`, set by the @csrf_exempt decorator).
    These fail immediately -- without needing an HTTP round trip -- if the
    decorator is ever removed by a future refactor.
    """

    def test_validate_token_view_is_csrf_exempt(self):
        assert getattr(validate_token_view, 'csrf_exempt', False) is True

    def test_catalog_items_verify_view_is_csrf_exempt(self):
        assert getattr(catalog_items_verify_view, 'csrf_exempt', False) is True


@pytest.mark.django_db
class TestValidateTokenSurvivesStrictCsrf:
    AUTH_URL = '/api/v1/internal/auth/validate-token/'

    def test_no_csrf_cookie_no_longer_returns_403(self, strict_csrf_client, staff_user):
        """
        Before the fix: a POST with a valid X-Internal-Secret but no CSRF
        cookie/token (exactly how the Gateway calls it) was rejected with
        403 CSRF Failed before validate_token_view ever ran. After the fix
        it must reach business logic and return 200.
        """
        secret = settings.INTERNAL_API_SECRET
        token = generate_user_jwt_token(staff_user)

        response = strict_csrf_client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret,
        )

        assert response.status_code == 200
        data = response.json()
        assert data.get('valid') is True
        assert data.get('user', {}).get('username') == staff_user.username

    def test_strict_csrf_still_respects_secret_and_payload_validation(self, strict_csrf_client):
        """
        The CSRF exemption must not weaken the existing shared-secret gate
        or payload validation: wrong secret still 401s, malformed body
        still 400s, even with strict CSRF enforcement on.
        """
        response_bad_secret = strict_csrf_client.post(
            self.AUTH_URL,
            data=json.dumps({'token': 'irrelevant'}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET='not-the-real-secret',
        )
        assert response_bad_secret.status_code == 401

        response_bad_body = strict_csrf_client.post(
            self.AUTH_URL,
            data="not json",
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=settings.INTERNAL_API_SECRET,
        )
        assert response_bad_body.status_code == 400


@pytest.mark.django_db
class TestCatalogItemsVerifySurvivesStrictCsrf:
    VERIFY_URL = '/api/v1/internal/catalog/items/verify/'

    def test_no_csrf_cookie_no_longer_returns_403(self, strict_csrf_client):
        """
        Same Gateway scenario as validate-token: a POST with a valid
        X-Internal-Secret and no CSRF cookie must reach the view instead of
        being rejected by CsrfViewMiddleware.
        """
        secret = settings.INTERNAL_API_SECRET

        response = strict_csrf_client.post(
            self.VERIFY_URL,
            data=json.dumps({'item_ids': [999999]}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret,
        )

        assert response.status_code == 200
        data = response.json()
        assert 'not_found' in data

    def test_strict_csrf_still_requires_item_ids_or_slugs(self, strict_csrf_client):
        """
        CSRF exemption must not bypass the endpoint's own input validation.
        """
        response = strict_csrf_client.post(
            self.VERIFY_URL,
            data=json.dumps({}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=settings.INTERNAL_API_SECRET,
        )
        assert response.status_code == 400
        assert response.json().get('status') == 'error'

    def test_strict_csrf_still_requires_valid_secret(self, strict_csrf_client):
        response = strict_csrf_client.post(
            self.VERIFY_URL,
            data=json.dumps({'item_ids': [1]}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET='wrong-secret',
        )
        assert response.status_code == 401


@pytest.mark.django_db
class TestAllInternalEndpointsSurviveStrictCsrf:
    """
    Fase 0, Tarea 4 acceptance criterion: walk every one of the 19 routes in
    apps.core.internal_urls.urlpatterns (not a hand-picked subset) with
    Client(enforce_csrf_checks=True) and the correct X-Internal-Secret, and
    confirm none of them ever returns 403. Before the InternalSecretMiddleware
    fix (setting request.csrf_processing_done = True once the secret is
    valid), 6 of the 8 POST routes failed this -- only
    auth/validate-token and catalog/items/verify had a per-view @csrf_exempt.

    A 403 here is the only unacceptable outcome. A GET-only route rejecting
    a payload-less GET with 400, or a POST route responding 404/400 to a
    dummy item_id/task_id that doesn't exist, are legitimate business
    responses proving the request reached the view at all.
    """

    @pytest.fixture(autouse=True)
    def _staff_token(self, db):
        user = User.objects.create_user(
            username='csrf_sweep_staff',
            email='csrf_sweep_staff@example.com',
            password='securepassword123',
            is_staff=True,
            is_active=True,
        )
        self.token = generate_user_jwt_token(user)

    def _payload_for(self, name: str) -> dict:
        """Minimal, shape-valid JSON body per POST route -- just enough to
        clear the view's own input validation so the response reflects real
        business logic (200/400/404) instead of a generic malformed-body 400,
        without needing a fully wired catalog/embedding fixture per route."""
        return {
            'internal_auth_validate_token': {'token': self.token},
            'internal_catalog_semantic_search': {'query_text': 'gaming laptop', 'limit': 5},
            'internal_raw_sql_sandbox': {'query': 'SELECT 1 AS n'},
            'internal_catalog_vector_search': {'query_vector': [0.0] * EMBEDDING_DIM, 'top_k': 3},
            'internal_catalog_embeddings_similar': {'item_id': 999999, 'top_k': 3},
            'internal_catalog_embeddings_upsert': {'item_id': 999999, 'vector': [0.0] * EMBEDDING_DIM},
            'internal_catalog_embeddings_mark_error': {'task_id': 999999, 'error': 'csrf sweep test'},
            'internal_catalog_items_verify': {'item_ids': [999999]},
        }.get(name, {})

    @pytest.mark.parametrize('url_pattern', internal_urls.urlpatterns, ids=lambda p: p.name)
    def test_endpoint_never_returns_403_under_strict_csrf(self, url_pattern):
        name = url_pattern.name
        method = ALL_INTERNAL_ENDPOINT_METHODS[name]
        path = reverse(f'internal:{name}')
        strict_client = Client(enforce_csrf_checks=True)
        auth_header = {'HTTP_X_INTERNAL_SECRET': settings.INTERNAL_API_SECRET}

        if method == 'GET':
            response = strict_client.get(path, **auth_header)
        else:
            response = strict_client.post(
                path,
                data=json.dumps(self._payload_for(name)),
                content_type='application/json',
                **auth_header,
            )

        assert response.status_code != 403, (
            f"{name} ({method} {path}) returned 403 under strict CSRF "
            f"enforcement -- missing InternalSecretMiddleware's "
            f"csrf_processing_done fix (or a per-view @csrf_exempt)."
        )

    def test_endpoints_cover_all_19_internal_routes(self):
        assert len(internal_urls.urlpatterns) == 19
        assert set(p.name for p in internal_urls.urlpatterns) == set(ALL_INTERNAL_ENDPOINT_METHODS)
