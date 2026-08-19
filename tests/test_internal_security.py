import pytest
from django.conf import settings
from django.urls import reverse


@pytest.mark.django_db
class TestInternalSecurityMiddleware:
    """
    Comprehensive test suite for Internal Microservice Security Middleware and protected routes.
    Validates X-Internal-Secret authentication, edge cases, public route access, and legacy route removal.
    """

    def test_internal_health_missing_secret_header(self, client):
        """
        Attempting to access /api/v1/internal/health/ without the X-Internal-Secret header
        must return HTTP 401 Unauthorized with proper JSON error payload.
        """
        response = client.get('/api/v1/internal/health/')
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'
        assert 'Invalid or missing' in data.get('detail', '')

    def test_internal_health_invalid_secret_header(self, client):
        """
        Attempting to access /api/v1/internal/health/ with an incorrect X-Internal-Secret
        must return HTTP 401 Unauthorized.
        """
        response = client.get(
            '/api/v1/internal/health/',
            HTTP_X_INTERNAL_SECRET='wrong-invalid-secret-key-12345'
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_internal_health_empty_secret_header(self, client):
        """
        Attempting to access /api/v1/internal/health/ with an empty X-Internal-Secret
        must return HTTP 401 Unauthorized.
        """
        response = client.get(
            '/api/v1/internal/health/',
            HTTP_X_INTERNAL_SECRET=''
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_internal_health_tampered_secret_header(self, client):
        """
        Attempting to access /api/v1/internal/health/ with a secret that is close but altered
        must return HTTP 401 Unauthorized.
        """
        valid_secret = settings.INTERNAL_API_SECRET
        tampered_secret = valid_secret + "_extra_characters"
        response = client.get(
            '/api/v1/internal/health/',
            HTTP_X_INTERNAL_SECRET=tampered_secret
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_internal_health_valid_secret_header(self, client):
        """
        Accessing /api/v1/internal/health/ with the correct X-Internal-Secret header
        must return HTTP 200 OK and status 'healthy'.
        """
        valid_secret = settings.INTERNAL_API_SECRET
        response = client.get(
            '/api/v1/internal/health/',
            HTTP_X_INTERNAL_SECRET=valid_secret
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('status') == 'healthy'
        assert data.get('service') == 'django-internal-api'

    def test_internal_health_disallowed_methods(self, client):
        """
        HTTP methods other than GET on /api/v1/internal/health/ should be rejected with 405 Method Not Allowed
        when valid secret is provided.
        """
        valid_secret = settings.INTERNAL_API_SECRET
        response = client.post(
            '/api/v1/internal/health/',
            data={'ping': 'pong'},
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=valid_secret
        )
        assert response.status_code == 405

        response_put = client.put(
            '/api/v1/internal/health/',
            data={'ping': 'pong'},
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=valid_secret
        )
        assert response_put.status_code == 405

        response_delete = client.delete(
            '/api/v1/internal/health/',
            HTTP_X_INTERNAL_SECRET=valid_secret
        )
        assert response_delete.status_code == 405

    def test_internal_wildcard_route_blocked_without_secret(self, client):
        """
        Any arbitrary endpoint under /api/v1/internal/* without secret must be blocked by the middleware
        with HTTP 401 before reaching route resolution.
        """
        response = client.get('/api/v1/internal/nonexistent-endpoint/')
        assert response.status_code == 401

    def test_internal_wildcard_route_404_with_valid_secret(self, client):
        """
        A non-existent endpoint under /api/v1/internal/* with valid secret passes the middleware
        and receives HTTP 404 from Django router.
        """
        valid_secret = settings.INTERNAL_API_SECRET
        response = client.get(
            '/api/v1/internal/nonexistent-endpoint/',
            HTTP_X_INTERNAL_SECRET=valid_secret
        )
        assert response.status_code == 404

    def test_public_routes_unblocked(self, client):
        """
        Public routes such as / and /about/ should remain accessible without X-Internal-Secret header (HTTP 200).
        """
        response_home = client.get('/')
        assert response_home.status_code == 200

        response_about = client.get('/about/')
        assert response_about.status_code == 200

    def test_legacy_chat_route_removed(self, client):
        """
        The deprecated legacy AI chat route (/api/chat/) must no longer exist and return HTTP 404 Not Found.
        """
        response_get = client.get('/api/chat/')
        assert response_get.status_code == 404

        response_post = client.post('/api/chat/', data={'message': 'hello'}, content_type='application/json')
        assert response_post.status_code == 404
