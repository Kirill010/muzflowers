from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from shop.thumbs import thumb_url
from shop.utils import format_phone, plural_ru
from shop.utils import rub as _rub

register = template.Library()

# (ширины копий фото, подсказка браузеру, какой размер выбрать)
SIZES = {
    'card': ([320, 480, 720], '(min-width: 1100px) 280px, (min-width: 700px) 33vw, 50vw'),
    'main': ([640, 960, 1280], '(min-width: 1000px) 560px, 100vw'),
    'thumb': ([120, 240], '84px'),
    'cart': ([96, 192], '76px'),
    'wide': ([720, 1080, 1600], '100vw'),
}
LAZY, EAGER = mark_safe('loading="lazy"'), mark_safe('fetchpriority="high"')


@register.filter
def rub(value):
    return _rub(value or 0)


@register.filter
def phone(value):
    return format_phone(value)


@register.filter
def plural(number, forms):
    """{{ n|plural:"букет,букета,букетов" }}"""
    one, few, many = forms.split(',')
    return plural_ru(number, one, few, many)


@register.simple_tag
def icon(name, css=''):
    return format_html('<svg class="i {}" aria-hidden="true" focusable="false"><use href="#i-{}"></use></svg>', css, name)


@register.simple_tag
def photo(file, alt='', kind='card', eager=False):
    """Фото с набором копий разного размера: телефону — маленькая, большому экрану — крупная."""
    widths, sizes = SIZES[kind]
    urls = [(thumb_url(file, w), w) for w in widths]
    return format_html('<img class="pimg" src="{}" srcset="{}" sizes="{}" alt="{}" {} decoding="async">',
                       urls[-1][0], ', '.join(f'{u} {w}w' for u, w in urls), sizes, alt, EAGER if eager else LAZY)


@register.simple_tag
def product_image(product, kind='card', eager=False):
    """Фото букета, а если его нет — нарисованный букет."""
    file = product.cover
    if file:
        return photo(file, product.name, kind, eager)
    return format_html('<img class="pimg pimg--art" src="{}" alt="{}" width="400" height="500" {} decoding="async">',
                       product.art_url, product.name, EAGER if eager else LAZY)


@register.filter
def inp(field):
    """Поле формы с подсказками для экранных дикторов: если есть ошибка — aria-invalid и ссылка на её текст."""
    attrs = {'aria-invalid': 'true', 'aria-describedby': f'{field.id_for_label}-err'} if field.errors else {}
    return field.as_widget(attrs=attrs)


@register.simple_tag(takes_context=True)
def current(context, *names):
    """aria-current для пункта меню: {% current 'shop:catalog' 'shop:category' %}"""
    match = getattr(context.get('request'), 'resolver_match', None)
    return mark_safe(' aria-current="page"') if match and match.view_name in names else ''


@register.simple_tag
def stars(rating):
    try:
        value = round(float(rating) * 2) / 2
    except (TypeError, ValueError):
        return ''
    icons = ''.join(icon('star' if value >= i else 'star-half' if value >= i - .5 else 'star-o') for i in range(1, 6))
    return format_html('<span class="stars" role="img" aria-label="Рейтинг {} из 5">{}</span>', rating, mark_safe(icons))
