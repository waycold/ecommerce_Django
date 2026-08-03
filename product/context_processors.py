from product.utils import get_profile_image_url


def profile_image(request):
    return {'profile_image_url': get_profile_image_url(request.user)}
