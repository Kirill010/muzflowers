import re
from urllib.parse import urlencode

from django.conf import settings
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
from . import bouquet, notifications, seo
from .faq import presentation_questions
from .legal import record_acceptance
from .forms import BouquetForm, LeadForm
from .models import FAQ, Addon, Category, Lead, Product, Review, Shop, SiteSettings
from .thumbs import thumb_url
from .throttle import throttled
from .utils import plural_ru, rub

PAGE_SIZE = 24
SORTS = {'pop': 'Сначала популярные', 'price_asc': 'Сначала дешевле', 'price_desc': 'Сначала дороже', 'new': 'Сначала новые'}
OCCASION_FILTERS = dict(Product.OCCASIONS)
BUDGETS = {
    'small': ('До 2 500 ₽', '', '2500'),
    'medium': ('2 500–5 000 ₽', '2500', '5000'),
    'large': ('Более 5 000 ₽', '5001', ''),
}
PRICE_TIERS = [(key, title, minimum) for key, (title, minimum, _) in bouquet.TIERS.items()]
BUDGETS.update({
    key: (f'{title} — от {rub(minimum)}', str(minimum), str(maximum) if maximum else '')
    for key, (title, minimum, maximum) in bouquet.TIERS.items()
})


def catalog_qs():
    return Product.objects.filter(is_active=True, category__is_active=True).select_related('category').prefetch_related('variants', 'photos')


def origin_of(request):
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
        'featured': [p for p in products if p not in ready][:8],
        'reviews': Review.objects.filter(is_published=True, permission_given=True).exclude(source=Review.Source.YANDEX, source_url='')[:6],
        'occasions': OCCASION_FILTERS.items(),
        'price_tiers': PRICE_TIERS,
        'categories': Category.objects.filter(is_active=True),
        'faq': presentation_questions(SiteSettings.load(), storefront=getattr(settings, 'SITES_STOREFRONT', False)),
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
    if params.get('occasion') in OCCASION_FILTERS:
        items = [p for p in items if p.occasion == params['occasion']]
    if params.get('ready') == '1':
        items = [p for p in items if p.is_ready]
    if params.get('sale') == '1':
        items = [p for p in items if p.old_price and p.old_price > p.price]
    budget = BUDGETS.get(params.get('budget'))
    min_price, max_price = budget[1:] if budget else (params.get('min', ''), params.get('max', ''))
    if min_price.isdigit():
        items = [p for p in items if p.price_from >= int(min_price)]
    if max_price.isdigit():
        items = [p for p in items if p.price_from <= int(max_price)]
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
    budget = BUDGETS.get(request.GET.get('budget'))
    price_min, price_max = budget[1:] if budget else (request.GET.get('min', ''), request.GET.get('max', ''))
    occasion = request.GET.get('occasion') if request.GET.get('occasion') in OCCASION_FILTERS else ''

    page_size = max(len(items), 1) if getattr(settings, 'SITES_STOREFRONT', False) else PAGE_SIZE
    page = Paginator(items, page_size).get_page(request.GET.get('page'))
    keep = {k: v for k, v in request.GET.items() if k != 'page' and not (budget and k in ('budget', 'min', 'max')) and v}
    if budget:
        keep.update({key: value for key, value in (('min', price_min), ('max', price_max)) if value})
    prices = [p.price_from for p in scope] or [0]
    context = {
        'category': category, 'page': page, 'products': page.object_list, 'total': len(items),
        'categories': Category.objects.filter(is_active=True), 'q': q, 'sort': sort, 'sorts': SORTS.items(),
        'occasion': occasion, 'occasions': OCCASION_FILTERS.items(),
        'budget_ranges': {key: values[1:] for key, values in BUDGETS.items()},
        'price_tiers': PRICE_TIERS, 'selected_budget': request.GET.get('budget'),
        'ready_only': request.GET.get('ready') == '1', 'sale_only': request.GET.get('sale') == '1',
        'price_min': price_min, 'price_max': price_max,
        'price_floor': min(prices), 'price_ceil': max(prices),
        'qs': urlencode(keep), 'filtered': bool(q or occasion or budget or request.GET.get('ready') or request.GET.get('sale') or price_min or price_max),
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


@require_GET
@cache_control(public=True, max_age=86400)
def stem_art(request, kind):
    if kind not in bouquet.FLOWERS:
        raise Http404
    return redirect(bouquet.flower_art_url(kind))


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
    items = presentation_questions(SiteSettings.load(), storefront=getattr(settings, 'SITES_STOREFRONT', False))
    covered = [item.question for item in items] + ['Как оплатить заказ?', 'Сколько стоит доставка?']
    extra = [] if getattr(settings, 'SITES_STOREFRONT', False) else list(FAQ.objects.filter(is_active=True).exclude(question__in=covered))
    return _page(request, 'shop/faq.html', items=items, extra=extra, jsonld=seo.dump(seo.faq_ld(items + extra)))


def privacy(request):
    return _page(request, 'shop/privacy.html')


def offer(request):
    return _page(request, 'shop/offer.html')


def legal(request):
    return _page(request, 'shop/legal.html')


def consent(request):
    return _page(request, 'shop/consent.html')


def marketing_consent(request):
    return _page(request, 'shop/marketing_consent.html')


def cookies(request):
    return _page(request, 'shop/cookies.html')


def _lead_page(request, kind, template, *, form_class=LeadForm, **context):
    form = form_class(request.POST if request.method == 'POST' else None, kind=kind)
    if request.method == 'POST':
        if throttled(request, 'lead', 5, 3600):
            messages.error(request, 'Слишком много заявок с одного адреса. Позвоните нам — мы на связи.')
        elif form.is_valid():
            d = form.cleaned_data
            custom = kind == Lead.Kind.BOUQUET
            with transaction.atomic():
                lead = Lead.objects.create(kind=kind, name=d['name'], company=d.get('company', ''), phone=d['phone'], email=d.get('email', ''),
                                           message=form.lead_message() if custom else d['message'],
                                           layout=d['layout'] if custom else {},
                                           source=request.session.get('mz_src', '')[:40])
                record_acceptance(request, 'personal', reference=f'lead:{lead.pk}', contact=lead.email or lead.phone)
                transaction.on_commit(lambda: notifications.dispatch_lead(lead.pk))
            messages.success(request, 'Спасибо! Мы получили заявку и позвоним вам в ближайшее время.')
            return redirect(request.path)
    return _page(request, template, form=form, **context)


def bouquet_builder(request):
    config = bouquet.builder_config()
    flowers = list(config['flowers'].items())
    middle = (len(flowers) + 1) // 2
    palettes = [('left', flowers[:middle]), ('right', flowers[middle:])]
    return _lead_page(request, Lead.Kind.BOUQUET, 'shop/builder.html', form_class=BouquetForm,
                      builder_config=config, palettes=palettes, vessels=bouquet.VESSELS, price_tiers=PRICE_TIERS)


def offices(request):
    return _lead_page(request, Lead.Kind.OFFICE, 'shop/offices.html')


def subscription(request):
    return _lead_page(request, Lead.Kind.SUBSCRIPTION, 'shop/subscription.html')


def balloons(request):
    return _lead_page(request, Lead.Kind.BALLOONS, 'shop/gifts.html',
                      title='Шары к букету и празднику', heading='Шары к особенному дню',
                      intro='Добавьте воздушные шары к букету или выберите отдельное украшение к празднику.',
                      description='Шары к букету, дню рождения и празднику в Выхино. Подбор цветов, количества и стоимости с флористом MuzFlowers.',
                      benefits=['Цвета и настроение подберём под ваш букет', 'Подойдут для дня рождения, открытия или сюрприза', 'Количество, наличие и стоимость согласуем до заказа'],
                      submit_label='Узнать варианты шаров')


def souvenirs(request):
    return _lead_page(request, Lead.Kind.SOUVENIRS, 'shop/gifts.html',
                      title='Сувениры и маленькие подарки к цветам', heading='Маленький подарок. Больше внимания.',
                      intro='Добавьте к букету сувенир, который подчеркнёт повод и будет напоминать о вашем жесте.',
                      description='Сувениры и небольшие подарки к букету в Выхино. Флорист MuzFlowers предложит доступные варианты под повод и бюджет.',
                      benefits=['Предложим варианты под повод и получателя', 'Можно обсудить подарок вместе с букетом', 'Наличие, состав и цену подтвердим до оплаты'],
                      submit_label='Узнать варианты сувениров')


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
