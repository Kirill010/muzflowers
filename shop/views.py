from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.core.cache import cache
from .models import Category, Product, Order, OrderItem
from .cart import Cart
from .forms import OrderCreateForm
from .tasks import send_order_email_safe


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

    return render(request, 'shop/index.html', {
        'category': category,
        'categories': categories,
        'products': products,
    })


def product_detail(request, id, slug):
    product = get_object_or_404(Product, id=id, slug=slug, available=True)
    return render(request, 'shop/product_detail.html', {'product': product})


@require_POST
def cart_add(request, product_id):
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    quantity = int(request.POST.get('quantity', 1))
    cart.add(product=product, quantity=quantity)
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