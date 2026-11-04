import re
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from . import art as artlib
from . import notifications, seo
from .forms import LeadForm
from .models import FAQ, Addon, Category, Lead, Product, Review, Shop, SiteSettings
from .thumbs import thumb_url
from .throttle import throttled
from .utils import plural_ru

PAGE_SIZE = 24
SORTS = {'pop': 'Сначала популярные', 'price_asc': 'Сначала дешевле', 'price_desc': 'Сначала дороже', 'new': 'Сначала новые'}


def catalog_qs():
    return Product.objects.filter(is_active=True, category__is_active=True).select_related('category').prefetch_related('variants', 'photos')


def origin_of(request):
    from django.conf import settings
    return settings.SITE_URL or request.build_absolute_uri('/').rstrip('/')


def og_image(request, product=None):
    """Картинка для ссылки в Telegram/ВК: фото букета или общая открытка магазина."""
    origin = origin_of(request)
    if product is not None and product.cover:
        url = thumb_url(product.cover, 1200)
        return url if url.startswith('http') else origin + url
    return origin + static('shop/img/og.jpg')


# ───────────── главная и каталог ─────────────

def home(request):
    products = list(catalog_qs())
    ready = sorted((p for p in products if p.is_ready), key=lambda p: p.price_from)[:4]
    context = {
        'ready': ready,
        'featured': products[:8],
        'categories': Category.objects.filter(is_active=True),
        'reviews': Review.objects.filter(is_published=True)[:6],
        'faq': FAQ.objects.filter(is_active=True)[:6],
        'og_image': og_image(request),
        'jsonld': seo.dump(seo.florist(origin_of(request))),
    }
    return render(request, 'shop/home.html', context)


def _apply_filters(request, items):
    """Фильтры и сортировка в Python: каталог небольшой, а так одинаково работает на SQLite и PostgreSQL (в SQLite поиск не различает регистр кириллицы)."""
    params = request.GET
    q = params.get('q', '').strip()
    sort = params.get('sort') if params.get('sort') in SORTS else 'pop'
    if q:
        needle = q.casefold()
        items = [p for p in items if needle in f'{p.name} {p.tagline} {p.description} {p.category.name}'.casefold()]
    if params.get('ready') == '1':
        items = [p for p in items if p.is_ready]
    for key, op in (('min', lambda p, v: p.price_from >= v), ('max', lambda p, v: p.price_from <= v)):
        if params.get(key, '').isdigit():
            value = int(params[key])
            items = [p for p in items if op(p, value)]
    if sort == 'price_asc':
        items = sorted(items, key=lambda p: p.price_from)
    elif sort == 'price_desc':
        items = sorted(items, key=lambda p: -p.price_from)
    elif sort == 'new':
        items = sorted(items, key=lambda p: p.created, reverse=True)
    return items, q, sort


def catalog(request, slug=None):
    category = get_object_or_404(Category, slug=slug, is_active=True) if slug else None
    everything = list(catalog_qs())
    scope = [p for p in everything if category is None or p.category_id == category.id]
    items, q, sort = _apply_filters(request, scope)

    page = Paginator(items, PAGE_SIZE).get_page(request.GET.get('page'))
    keep = {k: v for k, v in request.GET.items() if k != 'page' and v}
    prices = [p.price_from for p in scope] or [0]
    context = {
        'category': category, 'page': page, 'products': page.object_list, 'total': len(items),
        'categories': Category.objects.filter(is_active=True), 'q': q, 'sort': sort, 'sorts': SORTS.items(),
        'ready_only': request.GET.get('ready') == '1', 'price_min': request.GET.get('min', ''), 'price_max': request.GET.get('max', ''),
        'price_floor': min(prices), 'price_ceil': max(prices),
        'qs': urlencode(keep), 'filtered': bool(q or request.GET.get('ready') or request.GET.get('min') or request.GET.get('max')),
        'og_image': og_image(request),
    }
    origin = origin_of(request)
    crumbs = [('Главная', '/'), ('Каталог', reverse('shop:catalog'))] + ([(category.name, category.get_absolute_url())] if category else [])
    context['jsonld'] = seo.dump(seo.breadcrumbs_ld(origin, crumbs))
    if request.headers.get('X-Requested-With') == 'fetch':
        return HttpResponse(render_to_string('shop/_catalog_results.html', context, request=request))
    return render(request, 'shop/catalog.html', context)


def product(request, slug):
    item = get_object_or_404(catalog_qs(), slug=slug)
    related = [p for p in catalog_qs().filter(category=item.category).exclude(pk=item.pk)][:4]
    if len(related) < 4:
        related += [p for p in catalog_qs().exclude(pk=item.pk).exclude(pk__in=[r.pk for r in related])][:4 - len(related)]
    origin = origin_of(request)
    crumbs = [('Главная', '/'), ('Каталог', reverse('shop:catalog')), (item.category.name, item.category.get_absolute_url()), (item.name, item.get_absolute_url())]
    context = {
        'p': item, 'related': related, 'variants': item.active_variants, 'addons': Addon.objects.filter(is_active=True),
        'og_image': og_image(request, item),
        'jsonld': seo.dump(seo.product_ld(item, origin), seo.breadcrumbs_ld(origin, crumbs)),
    }
    return render(request, 'shop/product.html', context)


@require_GET
def suggest(request):
    """Быстрый поиск: до 6 букетов по первым буквам."""
    q = request.GET.get('q', '').strip().casefold()
    if len(q) < 2:
        return JsonResponse({'items': []})
    found = [p for p in catalog_qs() if q in f'{p.name} {p.tagline} {p.category.name}'.casefold()][:6]
    return JsonResponse({'items': [{
        'name': p.name, 'url': p.get_absolute_url(), 'price': p.price_from, 'tagline': p.tagline,
        'image': thumb_url(p.cover, 160) if p.cover else p.art_url,
    } for p in found]})


# ───────────── рисованный букет ─────────────

HEX6 = re.compile(r'^[0-9a-fA-F]{6}$')
ART_KINDS = {k for k, _ in Product.ART_KINDS}


@cache_control(public=True, max_age=31536000, immutable=True)
def art(request, kind, count, a, b):
    if kind not in ART_KINDS or not 1 <= count <= 25 or not (HEX6.match(a) and HEX6.match(b)):
        raise Http404
    return HttpResponse(artlib.bouquet_svg(kind, count, '#' + a, '#' + b), content_type='image/svg+xml')


# ───────────── страницы ─────────────

def _page(request, template, **extra):
    return render(request, template, {'og_image': og_image(request), **extra})


def music(request):
    return _page(request, 'shop/music.html', addon=Addon.objects.filter(is_active=True, is_music=True).first(),
                 products=list(catalog_qs().filter(is_ready=True))[:4])


def delivery(request):
    return _page(request, 'shop/delivery.html', shops=Shop.objects.filter(is_active=True))


def care(request):
    return _page(request, 'shop/care.html')


def about(request):
    return _page(request, 'shop/about.html', jsonld=seo.dump(seo.florist(origin_of(request))))


def contacts(request):
    return _page(request, 'shop/contacts.html', shops=Shop.objects.filter(is_active=True), jsonld=seo.dump(seo.florist(origin_of(request))))


def faq(request):
    items = list(FAQ.objects.filter(is_active=True))
    return _page(request, 'shop/faq.html', items=items, jsonld=seo.dump(seo.faq_ld(items)))


def privacy(request):
    return _page(request, 'shop/privacy.html')


def offer(request):
    return _page(request, 'shop/offer.html')


def _lead_page(request, kind, template):
    form = LeadForm(request.POST or None, kind=kind)
    if request.method == 'POST':
        if throttled(request, 'lead', 5, 3600):
            messages.error(request, 'Слишком много заявок с одного адреса. Позвоните нам — мы на связи.')
        elif form.is_valid():
            d = form.cleaned_data
            with transaction.atomic():
                lead = Lead.objects.create(kind=kind, name=d['name'], company=d.get('company', ''), phone=d['phone'], email=d.get('email', ''),
                                           message=d.get('message', ''), source=request.session.get('mz_src', '')[:40])
                transaction.on_commit(lambda: notifications.dispatch_lead(lead.pk))
            messages.success(request, 'Спасибо! Мы получили заявку и позвоним вам в ближайшее время.')
            return redirect(request.path)
    return _page(request, template, form=form)


def offices(request):
    return _lead_page(request, Lead.Kind.OFFICE, 'shop/offices.html')


def subscription(request):
    return _lead_page(request, Lead.Kind.SUBSCRIPTION, 'shop/subscription.html')


def favicon(request):
    """Браузеры сами просят /favicon.ico — отдаём значок из статики."""
    return redirect(static('shop/img/favicon-32.png'))


@require_GET
def health(request):
    SiteSettings.load()  # заодно проверяем, что база отвечает
    return JsonResponse({'ok': True})


def page_not_found(request, exception=None):
    return render(request, '404.html', status=404)


def server_error(request):
    return HttpResponse(render_to_string('500.html'), status=500)
