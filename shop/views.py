from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.core.cache import cache
from django.contrib import messages
from django.db.models import Avg
from django.core.paginator import Paginator
from .models import Category, Product, Order, OrderItem, ConsultationRequest
from .cart import Cart
from .forms import OrderCreateForm, ConsultationForm
from .tasks import send_order_email_safe
from promotions.models import PromoCode


def product_list(request, category_slug=None):
    category = None
    categories = cache.get('all_categories')
    if categories is None:
        categories = list(Category.objects.all())
        cache.set('all_categories', categories, 3600)

    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        cache_key = f'products_category_{category.id}'
    else:
        cache_key = 'products_all'

    products = cache.get(cache_key)
    if products is None:
        products = Product.objects.filter(available=True)
        if category:
            products = products.filter(category=category)
        products = list(products)
        cache.set(cache_key, products, 900)

    occasion = request.GET.get('occasion')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    sort = request.GET.get('sort', 'name')

    if occasion:
        products = [p for p in products if p.occasion == occasion]
    try:
        if min_price:
            products = [p for p in products if float(p.price) >= float(min_price)]
        if max_price:
            products = [p for p in products if float(p.price) <= float(max_price)]
    except (ValueError, TypeError):
        pass

    if sort == 'price_asc':
        products = sorted(products, key=lambda p: float(p.price))
    elif sort == 'price_desc':
        products = sorted(products, key=lambda p: float(p.price), reverse=True)
    elif sort == 'rating':
        products = sorted(products, key=lambda p: float(p.rating), reverse=True)

    paginator = Paginator(products, 9)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'shop/index.html', {
        'category': category,
        'categories': categories,
        'products': page_obj,
        'occasion_choices': Product.OCCASION_CHOICES,
        'current_filters': {
            'occasion': occasion or '',
            'min_price': min_price or '',
            'max_price': max_price or '',
            'sort': sort,
        },
    })


def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    reviews = product.reviews.filter(is_approved=True).order_by('-created_at')[:5]
    avg = reviews.aggregate(r=Avg('rating'))['r'] or 0

    from reviews.forms import ReviewForm
    return render(request, 'shop/product_detail.html', {
        'product': product,
        'reviews': reviews,
        'avg_rating': round(avg, 1),
        'review_form': ReviewForm(),
    })


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    cart.add(product=product, quantity=quantity)
    messages.success(request, f'«{product.name}» добавлен в корзину')
    return redirect('shop:cart_detail')


def cart_remove(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.remove(product)
    return redirect('shop:cart_detail')


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'shop/cart_detail.html', {'cart': cart})


def checkout(request):
    cart = Cart(request)
    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user

            promo_code = form.cleaned_data.get('promo_code')
            if promo_code:
                try:
                    promo = PromoCode.objects.get(code=promo_code, is_active=True)
                    if promo.is_valid():
                        order.promo_code = promo_code
                        total = sum(item['total_price'] for item in cart)
                        order.discount_amount = promo.calculate_discount(total)
                        promo.used_count += 1
                        promo.save()
                except PromoCode.DoesNotExist:
                    pass

            order.save()
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    price=item['price'],
                    quantity=item['quantity'],
                )
            cart.clear()
            send_order_email_safe(order.id)
            return render(request, 'shop/order_created.html', {'order': order})
    else:
        form = OrderCreateForm()
    return render(request, 'shop/checkout.html', {'cart': cart, 'form': form})


def consultation_view(request):
    if request.method == 'POST':
        form = ConsultationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Спасибо! Флорист свяжется с вами в ближайшее время.')
            return redirect('shop:product_list')
    else:
        form = ConsultationForm()
    return render(request, 'shop/consultation.html', {'form': form})


def quick_pick_view(request):
    occasion = request.GET.get('occasion')
    budget = request.GET.get('budget')

    products = Product.objects.filter(available=True)
    if occasion:
        products = products.filter(occasion=occasion)
    if budget:
        try:
            products = products.filter(price__lte=float(budget))
        except ValueError:
            pass
    products = products.order_by('-rating')[:6]

    return render(request, 'shop/quick_pick.html', {
        'products': products,
        'occasion_choices': Product.OCCASION_CHOICES,
    })


@require_POST
def wishlist_toggle(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    wl = request.session.get('wishlist', [])
    if product_id in wl:
        wl.remove(product_id)
        messages.info(request, f'«{product.name}» удалён из избранного')
    else:
        wl.append(product_id)
        messages.success(request, f'«{product.name}» добавлен в избранное')
    request.session['wishlist'] = wl
    request.session.modified = True
    return redirect('shop:product_detail', id=product.id, slug=product.slug)


def wishlist_view(request):
    wl_ids = request.session.get('wishlist', [])
    products = Product.objects.filter(id__in=wl_ids, available=True)
    return render(request, 'shop/wishlist.html', {'products': products})