from .cart import Cart
from .models import Category


def cart(request):
    return {'cart': Cart(request)}


def categories(request):
    return {'global_categories': Category.objects.all()}


def wishlist(request):
    wl = request.session.get('wishlist', [])
    return {'wishlist_ids': wl, 'wishlist_count': len(wl)}