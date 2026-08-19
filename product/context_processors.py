from product.utils import get_profile_image_url
from core.auth_services import generate_user_jwt_token


def profile_image(request):
    return {'profile_image_url': get_profile_image_url(request.user)}


def user_jwt_token(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        return {'user_jwt_token': generate_user_jwt_token(request.user)}
    return {'user_jwt_token': None}

