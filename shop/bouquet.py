from collections import Counter
from django.templatetags.static import static


FLOWERS = {
    'rose': 'Роза',
    'chrysanthemum': 'Хризантема',
    'hypericum': 'Гиперикум',
    'peony': 'Пион',
    'carnation': 'Гвоздика',
    'tulip': 'Тюльпан',
    'alstroemeria': 'Альстромерия',
    'hydrangea': 'Гортензия',
}
TIERS = {
    'economy': ('Эконом', 3000, 6999),
    'standard': ('Стандарт', 7000, 14999),
    'premium': ('Премиум', 15000, None),
}
VESSELS = {'vase': 'Ваза', 'basket': 'Корзина'}
MAX_STEMS = 25
X_MIN, X_MAX = 38, 602
Y_MIN, Y_MAX = 40, 296


def builder_config():
    return {
        'flowers': {kind: {'name': name, 'url': flower_art_url(kind)} for kind, name in FLOWERS.items()},
        'maxStems': MAX_STEMS,
        'bounds': [X_MIN, X_MAX, Y_MIN, Y_MAX],
    }


def flower_art_url(kind):
    return static(f'shop/img/flowers/{kind}.svg')


def describe(layout):
    counts = Counter(stem['kind'] for stem in layout['stems'])
    return ', '.join(f'{FLOWERS[kind]} × {count}' for kind, count in counts.items())
