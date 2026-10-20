from django.core.management.base import BaseCommand

from shop.models import Category, Product, PromoCode

DATA = [
    ('Розы', 'Нежность', '25 розовых роз в крафте', 4900, '#f4a6b8', '#e0587c', 12, 'Хит'),
    ('Розы', 'Алый рассвет', '15 красных роз с зеленью', 3600, '#e63946', '#a4161a', 12, ''),
    ('Пионы', 'Облако пионов', '9 нежных пионов', 5400, '#ffd6e0', '#ff9ebb', 16, 'Сезон'),
    ('Тюльпаны', 'Весенний каприз', '31 тюльпан-микс', 3200, '#ffd166', '#f77f00', 6, ''),
    ('Тюльпаны', 'Розовый микс', '15 тюльпанов нежных оттенков', 2100, '#ffc2d4', '#ff8fab', 6, ''),
    ('Композиции', 'Шляпная коробка', 'Розы и эустома в коробке', 6800, '#d0a9f5', '#9d4edd', 10, 'Новинка'),
    ('Композиции', 'Лавандовый сон', 'Лаванда, эустома, эвкалипт', 2900, '#cdb4db', '#a2a6ff', 8, ''),
    ('Композиции', 'Ромашковое лето', 'Букет из 25 ромашек', 1900, '#ffffff', '#f1e9e4', 14, ''),
]


class Command(BaseCommand):
    help = 'Создаёт демо-категории, букеты и промокод MUZ10'

    def handle(self, *args, **opts):
        for i, (cat, name, desc, price, a, b, k, badge) in enumerate(DATA):
            c, _ = Category.objects.get_or_create(name=cat, defaults={'slug': {'Розы': 'roses', 'Пионы': 'peonies', 'Тюльпаны': 'tulips', 'Композиции': 'compositions'}[cat], 'order': i})
            Product.objects.get_or_create(name=name, defaults=dict(
                category=c, description=desc, price=price, color_a=a, color_b=b, petals=k, badge=badge, popularity=100 - i))
        PromoCode.objects.get_or_create(code='MUZ10', defaults={'percent': 10})
        self.stdout.write(self.style.SUCCESS('Готово: демо-данные созданы'))
