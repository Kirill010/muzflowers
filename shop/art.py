"""Рисованные букеты. Пока у букета нет фото, сайт показывает аккуратную иллюстрацию в цветах бренда.
Рисунок собирается из нескольких «головок» цветка, которые повторяются через <use>, поэтому файл лёгкий (3–8 КБ).
Модуль не зависит от Django — его можно запускать отдельно и смотреть результат."""
import math
import random
from hashlib import md5

W, H = 400, 500
NECK = (200, 326)           # здесь сходятся стебли и начинается обёртка
GREENS = ['#7da06b', '#5f8a56', '#93b27c', '#4d7447']
WRAPS = {                    # (светлая, средняя, тёмная) обёртка
    'sage': ('#dfe8d3', '#c4d4b3', '#a6bb92'),
    'cream': ('#f8efe0', '#ecdcc2', '#d6c19f'),
    'blush': ('#fde9ef', '#f8cddb', '#eba9bf'),
}
RIBBONS = {'sage': ('#fca8c0', '#e9809f'), 'cream': ('#6b8a5a', '#4a6340'), 'blush': ('#7da06b', '#4a6340')}


def _rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _hex(rgb):
    return '#%02x%02x%02x' % tuple(max(0, min(255, round(v))) for v in rgb)


def mix(a, b, t):
    return _hex(tuple(x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))))


def light(c, t):
    return mix(c, '#ffffff', t)


def dark(c, t):
    return mix(c, '#3a1f2c', t)  # тень с тёплым оттенком, а не серая


def _f(v):
    return f'{v:.1f}'.rstrip('0').rstrip('.')


# ───────────── головки цветов: рисуются в круге радиусом 100 вокруг (0, 0) ─────────────

def _ring(n, dist, rad, rot, fill, stroke, ry=None, sw=1.6, op=.45):
    out = []
    for k in range(n):
        a = math.radians(rot + k * 360 / n)
        x, y = dist * math.cos(a), dist * math.sin(a)
        out.append(f'<ellipse cx="{_f(x)}" cy="{_f(y)}" rx="{_f(rad)}" ry="{_f(ry or rad)}" '
                   f'transform="rotate({_f(math.degrees(a) - 90)} {_f(x)} {_f(y)})" fill="{fill}" '
                   f'stroke="{stroke}" stroke-opacity="{op}" stroke-width="{sw}"/>')
    return ''.join(out)


def head_rose(c1, c2):
    edge = dark(c2, .25)
    return (
        _ring(5, 56, 46, 10, c1, edge) +
        _ring(5, 40, 38, 46, mix(c1, c2, .22), edge) +
        _ring(5, 26, 28, 10, mix(c1, c2, .45), edge) +
        _ring(4, 13, 20, 40, mix(c1, c2, .68), edge) +
        f'<circle r="14" fill="{c2}" stroke="{edge}" stroke-opacity=".5" stroke-width="1.6"/>'
        f'<path d="M-9 4C-9-9 9-10 10 1c1 11-12 15-17 6" fill="none" stroke="{edge}" stroke-opacity=".7" stroke-width="2.2" stroke-linecap="round"/>'
        f'<ellipse cx="-30" cy="-34" rx="16" ry="8" transform="rotate(-38 -30 -34)" fill="#fff" opacity=".28"/>')


def head_chrysanthemum(c1, c2):
    edge = dark(c2, .2)
    return (
        _ring(18, 66, 11, 0, c1, edge, ry=36, sw=1.2, op=.35) +
        _ring(14, 48, 11, 12, mix(c1, c2, .25), edge, ry=32, sw=1.2, op=.35) +
        _ring(10, 30, 11, 5, mix(c1, c2, .55), edge, ry=26, sw=1.2, op=.35) +
        _ring(7, 14, 9, 20, mix(c1, c2, .8), edge, ry=18, sw=1.1, op=.35) +
        f'<circle r="9" fill="#f2c94c" stroke="{edge}" stroke-opacity=".4" stroke-width="1.2"/>')


def head_alstroemeria(c1, c2):
    edge = dark(c2, .25)
    dots = ''.join(
        f'<circle cx="{_f(d * math.cos(math.radians(a)))}" cy="{_f(d * math.sin(math.radians(a)))}" r="2.3" fill="{dark(c2, .35)}"/>'
        for a, d in [(-100, 22), (-80, 34), (-120, 36), (30, 24), (50, 36), (10, 38), (150, 26), (170, 38), (130, 40)])
    return (
        _ring(3, 48, 30, -90, c1, edge, ry=54, op=.4) +
        _ring(3, 32, 22, -30, mix(c1, c2, .35), edge, ry=44, op=.4) + dots +
        '<circle r="7" fill="#f2c94c"/>' +
        ''.join(f'<path d="M0 0L{_f(30 * math.cos(math.radians(a)))} {_f(30 * math.sin(math.radians(a)))}" stroke="{dark(c2, .4)}" stroke-width="1.6" stroke-linecap="round"/>'
                for a in (-80, 20, 140)))


def head_hydrangea(c1, c2):
    rng = random.Random(7)
    pts = [(0, 0)]
    for ring, (n, d) in enumerate([(7, 36), (13, 70)]):
        pts += [(d * math.cos(2 * math.pi * k / n + ring), d * math.sin(2 * math.pi * k / n + ring)) for k in range(n)]
    out = []
    for x, y in sorted(pts, key=lambda p: p[1]):
        col = rng.choice([c1, c1, mix(c1, c2, .4), mix(c1, '#ffffff', .35), mix(c1, c2, .7)])
        edge = dark(c2, .3)
        out.append(f'<g transform="translate({_f(x)} {_f(y)}) rotate({rng.randint(0, 80)})">' +
                   _ring(4, 11, 13, 0, col, edge, sw=1, op=.4) + f'<circle r="4.5" fill="{light(col, .55)}"/></g>')
    return ''.join(out)


def head_tulip(c1, c2):
    edge = dark(c2, .3)
    return (
        f'<path d="M-46 -4C-48-52-22-86 0-112C22-86 48-52 46-4C44 36 24 62 0 62C-24 62-44 36-46-4Z" fill="{mix(c1, c2, .3)}" stroke="{edge}" stroke-opacity=".45" stroke-width="2"/>'
        f'<path d="M-46 -4C-50-46-32-78-12-96C-6-60-8-14-2 62C-26 62-44 36-46-4Z" fill="{c1}" stroke="{edge}" stroke-opacity=".4" stroke-width="1.6"/>'
        f'<path d="M46 -4C50-46 32-78 12-96C6-60 8-14 2 62C26 62 44 36 46-4Z" fill="{light(c1, .12)}" stroke="{edge}" stroke-opacity=".4" stroke-width="1.6"/>'
        f'<path d="M0 -112C-14-70-12-20 0 62C12-20 14-70 0-112Z" fill="{c2}" opacity=".55"/>')


def head_daisy(c1, c2):
    return _ring(12, 56, 13, 0, '#ffffff', '#cdbfb5', ry=34, sw=1, op=.5) + '<circle r="20" fill="#f2c94c"/><circle r="11" fill="#e0a93c"/>'


HEADS = {'rose': head_rose, 'chrysanthemum': head_chrysanthemum, 'alstroemeria': head_alstroemeria,
         'hydrangea': head_hydrangea, 'tulip': head_tulip, 'daisy': head_daisy}


# ───────────── листья, стебли, обёртка ─────────────

def leaf_symbols():
    """Лист единичного размера по одному на каждый оттенок зелени; на странице повторяется через <use>."""
    return ''.join(
        f'<g id="lf{i}"><path d="M0 0C1 -.3 1 -.75 0 -1C-1 -.75 -1 -.3 0 0Z" fill="{c}"/>'
        f'<path d="M0 -.03L0 -.9" stroke="{dark(c, .25)}" stroke-width="1" opacity=".5" vector-effect="non-scaling-stroke"/></g>'
        for i, c in enumerate(GREENS))


def _leaf(x, y, ang, ln, wd, idx):
    """Лист: от (x, y) в направлении ang (градусы), длина ln, ширина wd."""
    return f'<use href="#lf{idx}" transform="translate({_f(x)} {_f(y)}) rotate({_f(ang)}) scale({_f(wd)} {_f(ln)})"/>'


def _sprig(rng, angle, length, idx):
    """Веточка зелени (эвкалипт): стебель и пары листьев вдоль него."""
    nx, ny = NECK
    a = math.radians(angle)
    ex, ey = nx + length * math.sin(a), ny - length * math.cos(a)
    out = [f'<path d="M{nx} {ny - 10}Q{_f((nx + ex) / 2 + 8 * math.cos(a))} {_f((ny + ey) / 2)} {_f(ex)} {_f(ey)}" '
           f'stroke="{dark(GREENS[idx], .25)}" stroke-width="2.4" fill="none" stroke-linecap="round"/>']
    for i in range(1, 6):
        t = i / 5.2
        px, py = nx + (ex - nx) * t, ny - 10 + (ey - ny + 10) * t
        for side in (-1, 1):
            out.append(_leaf(px, py, angle + side * (48 + rng.randint(-8, 8)), 22 + 10 * (1 - t), 9, idx))
    out.append(_leaf(ex, ey, angle, 26, 9, idx))
    return ''.join(out)


def _stem(x, y, color='#5f8a56'):
    nx, ny = NECK
    cx = (x + nx) / 2 + (x - nx) * .08
    return f'<path d="M{nx} {ny}Q{_f(cx)} {_f((y + ny) / 2)} {_f(x)} {_f(y)}" stroke="{color}" stroke-width="4" fill="none" stroke-linecap="round"/>'


def _wrap(scheme):
    lt, md, dk = WRAPS[scheme]
    rb, rd = RIBBONS[scheme]
    bow = (f'<g transform="translate(200 366)"><path d="M0 0C-34-26-60-14-52 8C-46 22-18 12 0 0Z" fill="{rb}" stroke="{rd}" stroke-width="1.5"/>'
           f'<path d="M0 0C34-26 60-14 52 8C46 22 18 12 0 0Z" fill="{rb}" stroke="{rd}" stroke-width="1.5"/>'
           f'<path d="M-4 6L-26 50" stroke="{rd}" stroke-width="7" stroke-linecap="round"/><path d="M4 6L26 50" stroke="{rb}" stroke-width="7" stroke-linecap="round"/>'
           f'<circle r="9" fill="{rd}"/></g>')
    return (
        f'<path d="M104 300Q200 352 296 300L216 486Q200 494 184 486Z" fill="{dk}"/>'
        f'<path d="M104 300Q150 336 200 346L186 488Q176 490 170 480Z" fill="{md}"/>'
        f'<path d="M296 300Q250 336 200 346L214 488Q224 490 230 480Z" fill="{lt}"/>'
        f'<path d="M200 346L200 490" stroke="{dk}" stroke-width="1.6" opacity=".7"/>'
        f'<path d="M104 300Q200 352 296 300" fill="none" stroke="{dark(dk, .15)}" stroke-width="1.4" opacity=".6"/>' + bow)


# ───────────── раскладка цветов ─────────────

def _dome(n, rng, cx=200, cy=214, rx=116, ry=96):
    """Точки кольцами: одна в центре, потом 6, 12, 18… Снаружи вовнутрь — чтобы центр рисовался сверху."""
    pts, rings, left, ring = [], [], n, 0
    while left > 0:
        cnt = 1 if ring == 0 else min(left, 6 * ring)
        rings.append(cnt)
        left -= cnt
        ring += 1
    for i, cnt in enumerate(rings):
        k = i / max(1, len(rings) - 1) if len(rings) > 1 else 0
        for j in range(cnt):
            a = 2 * math.pi * j / cnt + i * .6
            pts.append((cx + rx * k * math.cos(a) * 0.92 + rng.uniform(-5, 5), cy + ry * k * math.sin(a) + rng.uniform(-5, 5), 1 - k * .22))
    return list(reversed(pts))


def _fan(n, rng):
    """Тюльпаны: головки разной высоты веером."""
    pts = []
    for i in range(n):
        t = (i + .5) / n
        ang = (t - .5) * 64 + rng.uniform(-4, 4)
        ln = 196 + rng.uniform(-16, 26) - abs(t - .5) * 36
        a = math.radians(ang)
        pts.append((NECK[0] + ln * math.sin(a), NECK[1] - ln * math.cos(a) * .98, 1 - abs(t - .5) * .25))
    return sorted(pts, key=lambda p: -p[1])


def bouquet_svg(kind='rose', count=7, color_a='#fca8c0', color_b='#e0587c', seed='', label='Букет'):
    seed = f'{kind}|{count}|{color_a}|{color_b}|{seed}'
    rng = random.Random(int(md5(seed.encode()).hexdigest()[:8], 16))
    scheme = rng.choice(['sage', 'cream', 'blush']) if kind != 'rose' else rng.choice(['sage', 'cream', 'blush'])
    shown = {'rose': min(count, 19), 'chrysanthemum': min(count, 9), 'alstroemeria': min(count, 9),
             'hydrangea': min(count, 3), 'tulip': min(count, 15), 'mixed': 13}.get(kind, min(count, 12))

    defs, parts, uses = [], [], []
    stems = []

    def symbol(uid, body):
        defs.append(f'<g id="{uid}">{body}</g>')

    if kind == 'mixed':
        c1, c2 = color_a, color_b
        symbol('h1', head_rose(c1, c2))
        symbol('h2', head_chrysanthemum(light(c1, .35), mix(c2, c1, .5)))
        symbol('h3', head_daisy(c1, c2))
        pts = _dome(shown, rng, ry=100)
        kinds = ['h1', 'h1', 'h2', 'h3', 'h2', 'h1']
        base_r = 40
        for i, (x, y, s) in enumerate(pts):
            uid = kinds[i % len(kinds)]
            r = base_r * s * rng.uniform(.9, 1.1) * (.78 if uid == 'h3' else 1)
            stems.append(_stem(x, y))
            uses.append(f'<use href="#{uid}" transform="translate({_f(x)} {_f(y)}) rotate({rng.randint(0, 359)}) scale({_f(r / 100)})"/>')
    elif kind == 'tulip':
        c1, c2 = color_a, color_b
        for i, col in enumerate([(c1, c2), (light(c1, .18), c2), (mix(c1, c2, .3), c2)]):
            symbol(f'h{i}', head_tulip(*col))
        for i, (x, y, s) in enumerate(_fan(shown, rng)):
            stems.append(_stem(x, y + 40))
            uses.append(f'<use href="#h{i % 3}" transform="translate({_f(x)} {_f(y + 24)}) rotate({_f(rng.uniform(-9, 9))}) scale({_f(.46 * s)})"/>')
    elif kind == 'hydrangea':
        symbol('h0', head_hydrangea(color_a, color_b))
        spots = [(200, 214, 1.08), (132, 250, .86), (268, 250, .86)][:max(1, shown)] if shown > 1 else [(200, 224, 1.12)]
        for x, y, s in reversed(spots):
            stems.append(_stem(x, y))
            uses.append(f'<use href="#h0" transform="translate({x} {y}) scale({_f(s * .96)})"/>')
    else:
        fn = HEADS.get(kind, head_rose)
        c1, c2 = color_a, color_b
        for i, col in enumerate([(c1, c2), (light(c1, .16), mix(c2, c1, .15)), (mix(c1, c2, .22), dark(c2, .08))]):
            symbol(f'h{i}', fn(*col))
        pts = _dome(shown, rng)
        base_r = {'rose': 100 / math.sqrt(shown) * 1.05 + 6, 'chrysanthemum': 54, 'alstroemeria': 50}.get(kind, 46)
        base_r = min(base_r, 58 if shown > 1 else 78)
        for i, (x, y, s) in enumerate(pts):
            r = base_r * s * rng.uniform(.92, 1.08)
            stems.append(_stem(x, y))
            uses.append(f'<use href="#h{i % 3}" transform="translate({_f(x)} {_f(y)}) rotate({rng.randint(0, 359)}) scale({_f(r / 100)})"/>')

    sprigs = ''.join(_sprig(rng, a, rng.uniform(150, 190), rng.randrange(len(GREENS))) for a in (-62, -38, -14, 12, 36, 60))
    shadow = '<ellipse cx="200" cy="492" rx="74" ry="9" fill="#2b3a2c" opacity=".14"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {-10} {W} {H}" role="img" aria-label="{label}">'
            f'<defs>{leaf_symbols()}{"".join(defs)}</defs>{shadow}{sprigs}{"".join(stems)}{"".join(uses)}{_wrap(scheme)}</svg>')


if __name__ == '__main__':  # python art.py <папка> — рисует примеры, чтобы посмотреть
    import sys
    from pathlib import Path
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    samples = {
        'rose3': ('rose', 3, '#fca8c0', '#e0587c'), 'rose7': ('rose', 7, '#e63946', '#a4161a'), 'rose15': ('rose', 15, '#fca8c0', '#e0587c'),
        'rose25': ('rose', 25, '#ff9ebb', '#c2416c'), 'chrys': ('chrysanthemum', 7, '#f6e27a', '#e0a93c'),
        'alstro': ('alstroemeria', 9, '#fca8c0', '#d6336c'), 'hydr': ('hydrangea', 3, '#bcd0f0', '#7d9bd6'),
        'tulip': ('tulip', 25, '#fca8c0', '#e0587c'), 'mixed': ('mixed', 13, '#fca8c0', '#c2416c'),
    }
    for name, args in samples.items():
        (out / f'{name}.svg').write_text(bouquet_svg(*args), encoding='utf-8')
    print('ok', len(samples))
