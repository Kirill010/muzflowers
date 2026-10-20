import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from shop.models import Category, Product, PromoCode, Review

SLUGS = {'Розы': 'roses', 'Пионы': 'peonies', 'Тюльпаны': 'tulips', 'Композиции': 'compositions'}
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
REVIEWS = [
    ('Анна', 'Букет был ровно такой, как на фото, и приехал вовремя. Мама счастлива!'),
    ('Дмитрий', 'Пионы простояли почти две недели. Беру только здесь.'),
    ('Мария', 'Приятно, что прислали фото перед доставкой. Очень внимательный сервис.'),
]


class Command(BaseCommand):
    help = 'Добавляет демо-букеты, отзывы и промокод MUZ10 (только в пустой магазин) и создаёт админа, если его нет'

    def handle(self, *args, **options):
        if not Product.objects.exists():
            for i, (cat, name, desc, price, a, b, k, badge) in enumerate(DATA):
                c, _ = Category.objects.get_or_create(slug=SLUGS[cat], defaults={'name': cat, 'order': list(SLUGS).index(cat)})
                Product.objects.create(category=c, name=name, description=desc, price=price,
                                       color_a=a, color_b=b, petals=k, badge=badge, popularity=100 - i)
            PromoCode.objects.get_or_create(code='MUZ10', defaults={'percent': 10})
            Review.objects.bulk_create(Review(name=n, text=t) for n, t in REVIEWS)
            self.stdout.write(self.style.SUCCESS('Демо-данные добавлены (удалите или замените их в админке)'))
        User = get_user_model()
        if not User.objects.filter(is_superuser=True).exists():
            password = secrets.token_urlsafe(9)
            User.objects.create_superuser('admin', 'admin@example.com', password)
            self.stdout.write(self.style.WARNING(f'\n  ВХОД В АДМИНКУ:  логин: admin   пароль: {password}\n  (пароль показан один раз — сохраните его)\n'))
