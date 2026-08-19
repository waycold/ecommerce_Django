import json
from datetime import datetime, timezone, timedelta
import jwt
import pytest
from django.conf import settings
from django.contrib.auth.models import User
from core.auth_services import generate_user_jwt_token


@pytest.fixture
def staff_user(db):
    """Creates an active staff member."""
    return User.objects.create_user(
        username="staff_member",
        email="staff@example.com",
        password="securepassword123",
        is_staff=True,
        is_active=True,
    )


@pytest.fixture
def superuser(db):
    """Creates an active superuser / administrator."""
    return User.objects.create_superuser(
        username="admin_superuser",
        email="admin@example.com",
        password="supersecretpassword123",
    )


@pytest.fixture
def regular_user(db):
    """Creates a regular non-staff customer."""
    return User.objects.create_user(
        username="regular_customer",
        email="customer@example.com",
        password="customerpassword123",
        is_staff=False,
        is_superuser=False,
        is_active=True,
    )


@pytest.fixture
def inactive_staff_user(db):
    """Creates an inactive staff user."""
    return User.objects.create_user(
        username="inactive_staff",
        email="inactivestaff@example.com",
        password="password123",
        is_staff=True,
        is_active=False,
    )


@pytest.mark.django_db
class TestStaffAuthContract:
    """
    Test suite for Contract 2: Staff Token Validation API (POST /api/v1/internal/auth/validate-token/).
    """

    AUTH_URL = '/api/v1/internal/auth/validate-token/'

    def test_validate_token_unauthorized_missing_internal_secret(self, client, staff_user):
        """
        Requesting validate-token without X-Internal-Secret returns 401 Unauthorized.
        """
        token = generate_user_jwt_token(staff_user)
        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_validate_token_unauthorized_wrong_internal_secret(self, client, staff_user):
        """
        Requesting validate-token with an invalid X-Internal-Secret returns 401 Unauthorized.
        """
        token = generate_user_jwt_token(staff_user)
        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET='wrong-microservice-secret'
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('error') == 'Unauthorized'

    def test_validate_token_disallowed_methods(self, client):
        """
        GET, PUT, DELETE methods on /api/v1/internal/auth/validate-token/ return 405 Method Not Allowed.
        """
        secret = settings.INTERNAL_API_SECRET

        response_get = client.get(self.AUTH_URL, HTTP_X_INTERNAL_SECRET=secret)
        assert response_get.status_code == 405

        response_put = client.put(
            self.AUTH_URL,
            data=json.dumps({'token': 'sample'}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response_put.status_code == 405

        response_delete = client.delete(self.AUTH_URL, HTTP_X_INTERNAL_SECRET=secret)
        assert response_delete.status_code == 405

    def test_validate_token_malformed_json_body(self, client):
        """
        Non-JSON body returns 400 Bad Request.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.post(
            self.AUTH_URL,
            data="not a valid json payload",
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get('error') == 'Bad Request'

    def test_validate_token_missing_token_field(self, client):
        """
        JSON body without 'token' field returns 400 Bad Request.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'unrelated_field': 'value'}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get('error') == 'Bad Request'

    def test_validate_token_empty_token_field(self, client):
        """
        JSON body with empty or whitespace token returns 400 Bad Request.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': '   '}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 400
        data = response.json()
        assert data.get('error') == 'Bad Request'

    def test_validate_token_success_staff_user(self, client, staff_user):
        """
        Valid JWT for an active staff member returns 200 OK and valid: True with user metadata.
        """
        secret = settings.INTERNAL_API_SECRET
        token = generate_user_jwt_token(staff_user)

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('valid') is True
        user_info = data.get('user', {})
        assert user_info.get('id') == staff_user.id
        assert user_info.get('username') == staff_user.username
        assert user_info.get('email') == staff_user.email
        assert user_info.get('is_staff') is True

    def test_validate_token_success_superuser(self, client, superuser):
        """
        Valid JWT for an active superuser returns 200 OK and valid: True with superuser flag.
        """
        secret = settings.INTERNAL_API_SECRET
        token = generate_user_jwt_token(superuser)

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 200
        data = response.json()
        assert data.get('valid') is True
        user_info = data.get('user', {})
        assert user_info.get('id') == superuser.id
        assert user_info.get('is_superuser') is True

    def test_validate_token_forbidden_regular_user(self, client, regular_user):
        """
        Valid JWT for a non-staff user returns 403 Forbidden and valid: False.
        """
        secret = settings.INTERNAL_API_SECRET
        token = generate_user_jwt_token(regular_user)

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 403
        data = response.json()
        assert data.get('valid') is False
        assert 'staff' in data.get('error', '').lower()

    def test_validate_token_expired(self, client, staff_user):
        """
        Expired JWT token returns 401 Unauthorized and valid: False.
        """
        secret = settings.INTERNAL_API_SECRET
        expired_token = generate_user_jwt_token(staff_user, exp_minutes=-60)

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': expired_token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('valid') is False
        assert 'expired' in data.get('error', '').lower()

    def test_validate_token_forged_signature(self, client, staff_user):
        """
        JWT signed with a different secret key returns 401 Unauthorized and valid: False.
        """
        secret = settings.INTERNAL_API_SECRET
        forged_token = generate_user_jwt_token(staff_user, secret='malicious_forged_secret_key')

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': forged_token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('valid') is False
        assert 'invalid' in data.get('error', '').lower()

    def test_validate_token_inactive_user(self, client, inactive_staff_user):
        """
        JWT for an inactive user (is_active=False) returns 401 Unauthorized and valid: False.
        """
        secret = settings.INTERNAL_API_SECRET
        token = generate_user_jwt_token(inactive_staff_user)

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('valid') is False
        assert 'inactive' in data.get('error', '').lower() or 'not found' in data.get('error', '').lower()

    def test_validate_token_nonexistent_user_id(self, client):
        """
        JWT referencing a user ID that does not exist in the database returns 401 Unauthorized.
        """
        secret = settings.INTERNAL_API_SECRET
        now = datetime.now(timezone.utc)
        payload = {
            'user_id': 9999999,
            'username': 'ghost_user',
            'iat': int(now.timestamp()),
            'exp': int((now + timedelta(hours=1)).timestamp()),
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': token}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('valid') is False

    def test_validate_token_corrupted_garbage_string(self, client):
        """
        Completely corrupted / non-JWT string returns 401 Unauthorized and valid: False.
        """
        secret = settings.INTERNAL_API_SECRET
        response = client.post(
            self.AUTH_URL,
            data=json.dumps({'token': 'header.payload.not-a-valid-signature-12345'}),
            content_type='application/json',
            HTTP_X_INTERNAL_SECRET=secret
        )
        assert response.status_code == 401
        data = response.json()
        assert data.get('valid') is False
