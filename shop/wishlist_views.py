from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Product
from .wishlist import Wishlist


def wishlist_page(request):
    wishlist = Wishlist(request)
    return render(request, 'shop/wishlist.html', {'products': wishlist.products()})


@require_POST
def wishlist_toggle(request):
    try:
        product_id = int(request.POST.get('product', ''))
    except (TypeError, ValueError):
        product_id = 0
    product = get_object_or_404(Product, pk=product_id, is_active=True, category__is_active=True)
    wishlist = Wishlist(request)
    active, changed = wishlist.toggle(product.pk)
    if changed:
        message = f'«{product.name}» — в избранном' if active else f'«{product.name}» убран из избранного'
    else:
        message = f'В избранном можно сохранить до {wishlist.MAX_ITEMS} букетов'
    if request.headers.get('X-Requested-With') == 'fetch':
        return JsonResponse({'ok': changed, 'active': active, 'count': wishlist.count,
                             'product': product.pk, 'message': message}, status=200 if changed else 409)
    (messages.success if changed else messages.error)(request, message)
    target = request.POST.get('next', '')
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        target = reverse('shop:wishlist')
    return redirect(target)
