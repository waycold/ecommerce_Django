from django.templatetags.static import static
from apps.core.authentication.services import generate_user_jwt_token


def get_profile_image_url(user):
    default_avatar = static('img/default-avatar.svg')
    if not user or not user.is_authenticated:
        return default_avatar

    profile = getattr(user, 'profile', None)
    if profile and profile.image and profile.image.name:
        try:
            return profile.image.url
        except Exception:
            return default_avatar

    return default_avatar


def profile_image(request):
    return {'profile_image_url': get_profile_image_url(request.user if hasattr(request, 'user') else None)}


def user_jwt_token(request):
    if hasattr(request, 'user') and request.user.is_authenticated:
        return {'user_jwt_token': generate_user_jwt_token(request.user)}
    return {'user_jwt_token': None}
