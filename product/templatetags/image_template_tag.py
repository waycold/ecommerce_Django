from django import template
from product.utils import get_profile_image_url

register = template.Library()


@register.simple_tag()
def image_user_tag(user):
    return get_profile_image_url(user)
