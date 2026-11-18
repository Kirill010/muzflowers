from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .cart import Cart
from .legal import DOCUMENT_DATE, DOCUMENT_VERSION
from .models import Addon, Shop, SiteSettings


def site(request):
    """Данные, нужные на каждой странице: настройки магазина, точки, корзина.
    Тяжёлое (точки, корзина) считается лениво — только если шаблон этого действительно касается."""
    cart = Cart(request)
    origin = settings.SITE_URL or request.build_absolute_uri('/').rstrip('/')
    shops = SimpleLazyObject(lambda: list(Shop.objects.filter(is_active=True)))
    return {
        'site': SiteSettings.load(),
        'shops': shops,
        'primary_pickup': SimpleLazyObject(lambda: next((shop for shop in shops if shop.is_pickup), None)),
        'music_addon': SimpleLazyObject(lambda: Addon.objects.filter(is_active=True, is_music=True).first()),
        'cart_count': cart.count,
        'cart_promo': cart.promo,
        'cart_quote': SimpleLazyObject(cart.quote) if cart else None,
        'cart_addons': SimpleLazyObject(cart.addon_states),
        'site_origin': origin,
        'canonical_url': origin + request.path,
        'admin_url': '/' + settings.ADMIN_URL,
        'legal_version': DOCUMENT_VERSION,
        'legal_date': DOCUMENT_DATE,
        'sites_storefront': getattr(settings, 'SITES_STOREFRONT', False),
    }
