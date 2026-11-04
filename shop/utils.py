import re

from django.utils.text import slugify

_TRANSLIT = dict(zip(
    'абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
    ['a', 'b', 'v', 'g', 'd', 'e', 'e', 'zh', 'z', 'i', 'y', 'k', 'l', 'm', 'n', 'o', 'p', 'r', 's', 't', 'u',
     'f', 'h', 'ts', 'ch', 'sh', 'sch', '', 'y', '', 'e', 'yu', 'ya']))


def slugify_ru(text):
    """«Облако гортензий» → «oblako-gortenziy» (адреса страниц — латиницей)."""
    latin = ''.join(_TRANSLIT.get(ch, ch) for ch in str(text).lower())
    return slugify(latin) or 'item'


def unique_slug(model, text, instance=None):
    base = slugify_ru(text)[:90]
    slug, n = base, 2
    qs = model.objects.all()
    if instance is not None and instance.pk:
        qs = qs.exclude(pk=instance.pk)
    while qs.filter(slug=slug).exists():
        slug = f'{base}-{n}'
        n += 1
    return slug


def normalize_phone(raw):
    """Приводит телефон к виду +79175494941. Если цифр меньше 10 — возвращает пустую строку."""
    digits = re.sub(r'\D', '', str(raw or ''))
    if len(digits) == 11 and digits[0] in '78':
        digits = '7' + digits[1:]
    elif len(digits) == 10:
        digits = '7' + digits
    if not 10 <= len(digits) <= 15:
        return ''
    return '+' + digits


def format_phone(phone):
    """+79175494941 → +7 (917) 549-49-41."""
    digits = re.sub(r'\D', '', str(phone or ''))
    if len(digits) == 11 and digits[0] == '7':
        return f'+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}'
    return str(phone or '')


def plural_ru(n, one, few, many):
    """plural_ru(3, 'букет', 'букета', 'букетов') → 'букета'."""
    n = abs(int(n))
    if 11 <= n % 100 <= 14:
        return many
    last = n % 10
    if last == 1:
        return one
    return few if 2 <= last <= 4 else many


def rub(amount):
    """1990 → «1 990 ₽» (с неразрывными пробелами, чтобы цена не рвалась на две строки)."""
    return f'{int(amount):,}'.replace(',', ' ') + ' ₽'
