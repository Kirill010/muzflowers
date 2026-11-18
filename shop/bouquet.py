from collections import Counter

from django.urls import reverse

from . import art


FLOWERS = {
    'rose': ('Роза', '#f5a9b6', '#b84967'),
    'chrysanthemum': ('Хризантема', '#fff5d7', '#dbac4a'),
    'hypericum': ('Гиперикум', '#f19281', '#9b363e'),
    'peony': ('Пион', '#f4afc8', '#ae4269'),
    'carnation': ('Гвоздика', '#f0a89a', '#b65246'),
    'tulip': ('Тюльпан', '#e7a7b1', '#ab4669'),
    'alstroemeria': ('Альстромерия', '#e0bedf', '#9c5d98'),
    'hydrangea': ('Гортензия', '#c8cced', '#8387ba'),
}
VESSELS = {'vase': 'Ваза', 'basket': 'Корзина'}
MAX_STEMS = 25
X_MIN, X_MAX = 38, 602
Y_MIN, Y_MAX = 40, 296


def builder_config():
    return {
        'flowers': {kind: {'name': data[0], 'url': reverse('shop:stem_art', args=[kind])}
                    for kind, data in FLOWERS.items()},
        'maxStems': MAX_STEMS,
        'bounds': [X_MIN, X_MAX, Y_MIN, Y_MAX],
    }


def describe(layout):
    counts = Counter(stem['kind'] for stem in layout['stems'])
    return ', '.join(f'{FLOWERS[kind][0]} × {count}' for kind, count in counts.items())


def flower_svg(kind):
    _, light, dark = FLOWERS[kind]
    head = art.HEADS.get(kind)
    if head:
        petals = head(light, dark)
    elif kind == 'hypericum':
        petals = ''.join(
            f'<path d="M0 80L{x} {y}" stroke="#58734d" stroke-width="7"/>'
            f'<circle cx="{x}" cy="{y}" r="24" fill="{dark}"/>'
            f'<circle cx="{x - 7}" cy="{y - 8}" r="10" fill="{light}"/>'
            for x, y in [(-55, -14), (-28, -63), (29, -60), (57, -15), (0, -15), (-31, 35), (31, 36)]
        )
    else:
        edge = art.dark(dark, .2)
        if kind == 'peony':
            petals = (
                art._ring(8, 51, 41, 10, light, edge)
                + art._ring(9, 32, 31, 23, art.mix(light, dark, .25), edge)
                + art._ring(8, 18, 22, 12, art.mix(light, dark, .55), edge)
                + art._ring(5, 7, 12, 0, dark, edge)
            )
        else:
            petals = (
                art._ring(15, 57, 24, 1, light, edge, ry=40)
                + art._ring(12, 35, 21, 18, art.mix(light, dark, .25), edge, ry=29)
                + art._ring(9, 17, 16, 8, art.mix(light, dark, .48), edge, ry=25)
                + art._ring(5, 7, 11, 0, dark, edge)
            )
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-115 -115 230 230">{petals}</svg>'
