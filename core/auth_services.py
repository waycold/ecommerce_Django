"""
core/auth_services.py

Service layer for staff authentication, JWT token validation, and token issuance.
Decoupled from HTTP transport to support internal microservices and testing.
"""

from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any, Optional
import jwt
from django.conf import settings
from django.contrib.auth.models import User


def validate_staff_jwt_token(token: str) -> Tuple[Dict[str, Any], int]:
    """
    Validates a JWT token and verifies that the associated user exists,
    is active, and possesses staff (is_staff or is_superuser) permissions.

    Args:
        token (str): The JWT string to validate.

    Returns:
        tuple (dict, int): Response payload dictionary and HTTP status code.
    """
    if not token or not isinstance(token, str):
        return {'valid': False, 'error': 'Invalid token'}, 401

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256'],
        )
    except jwt.ExpiredSignatureError:
        return {'valid': False, 'error': 'Token has expired'}, 401
    except (jwt.InvalidTokenError, jwt.DecodeError):
        return {'valid': False, 'error': 'Invalid token'}, 401
    except Exception:
        return {'valid': False, 'error': 'Invalid token'}, 401

    # Extract user identity from payload
    user_id = payload.get('user_id') or payload.get('id') or payload.get('sub')
    username = payload.get('username')

    user = None
    if user_id is not None:
        try:
            if str(user_id).isdigit():
                user = User.objects.filter(id=int(user_id), is_active=True).first()
            else:
                user = User.objects.filter(username=str(user_id), is_active=True).first()
        except Exception:
            user = None

    if not user and username:
        user = User.objects.filter(username=str(username), is_active=True).first()

    if not user:
        return {'valid': False, 'error': 'User not found or inactive'}, 401

    # Check staff permissions
    if not (user.is_staff or user.is_superuser):
        return {
            'valid': False,
            'error': 'Forbidden: User does not have staff permissions',
            'is_staff': False,
        }, 403

    return {
        'valid': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser,
        },
    }, 200


def generate_user_jwt_token(
    user: User,
    exp_minutes: int = 60,
    secret: Optional[str] = None,
) -> str:
    """
    Helper to generate an HS256 JWT token for testing and internal service authentication.

    Args:
        user (User): Django User instance.
        exp_minutes (int): Expiration time in minutes from issuance (default 60).
        secret (str, optional): Custom secret key. Defaults to settings.SECRET_KEY.

    Returns:
        str: Encoded JWT string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=exp_minutes)).timestamp()),
    }
    secret_key = secret or settings.SECRET_KEY
    token = jwt.encode(payload, secret_key, algorithm='HS256')
    return token if isinstance(token, str) else token.decode('utf-8')
