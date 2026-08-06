from django.conf import settings
from product.models import Profile

DEFAULT_PROFILE_IMAGE = f'{settings.MEDIA_URL}profile_image/default.jpg'


def get_profile_image_url(user):
    if not user.is_authenticated:
        return DEFAULT_PROFILE_IMAGE

    profile = getattr(user, 'profile', None)
    if profile and profile.image and profile.image.name:
        return profile.image.url

    return DEFAULT_PROFILE_IMAGE
