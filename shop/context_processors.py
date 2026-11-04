from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .cart import Cart
from .models import Addon, Shop, SiteSettings


def site(request):
    """Данные, нужные на каждой странице: настройки магазина, точки, корзина.
    Тяжёлое (точки, корзина) считается лениво — только если шаблон этого действительно касается."""
    cart = Cart(request)
    origin = settings.SITE_URL or request.build_absolute_uri('/').rstrip('/')
    return {
        'site': SiteSettings.load(),
        'shops': SimpleLazyObject(lambda: list(Shop.objects.filter(is_active=True))),
        'music_addon': SimpleLazyObject(lambda: Addon.objects.filter(is_active=True, is_music=True).first()),
        'cart_count': cart.count,
        'cart_promo': cart.promo,
        'cart_quote': SimpleLazyObject(cart.quote) if cart else None,
        'cart_addons': SimpleLazyObject(cart.addon_states),
        'site_origin': origin,
        'canonical_url': origin + request.path,
        'admin_url': '/' + settings.ADMIN_URL,
    }
