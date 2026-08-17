from django.conf import settings
from django.templatetags.static import static


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

