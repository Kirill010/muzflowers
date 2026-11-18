import secrets
from datetime import date, time
from decimal import Decimal
from urllib.parse import urlparse

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format

from .thumbs import process_upload, validate_image_size
from .utils import format_phone, unique_slug

HEX_COLOR = RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Цвет в формате #RRGGBB, например #f4a6b8')
MONTHS = [(i, m) for i, m in enumerate(
    ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь'], 1)]


def format_day(day):
    """сегодня / завтра / 12 ноября"""
    today = timezone.localdate()
    if day == today:
        return 'сегодня'
    if (day - today).days == 1:
        return 'завтра'
    return date_format(day, 'j E')


# ───────────────────────────── настройки магазина ─────────────────────────────

class SiteSettings(models.Model):
    """Одна запись с настройками магазина. Меняется в панели: «Настройки сайта»."""
    CACHE_KEY = 'mz:site-settings'

    shop_name = models.CharField('Название магазина', max_length=60, default='MuzFlowers')
    phone = models.CharField('Телефон', max_length=30, default='+7 (995) 152-21-31')
    email = models.EmailField('Почта магазина', blank=True, default='muzflowers@ya.ru', help_text='Показывается на сайте и в письмах клиентам')
    telegram = models.CharField('Telegram-канал (без @)', max_length=40, blank=True, default='muzflowers')
    max_url = models.URLField('MAX: ссылка на контакт или канал', blank=True, default='https://web.max.ru/-73754300368320',
                              help_text='Полная ссылка, начинается с https://. Пусто — ссылку не показываем')
    yandex_maps_url = models.URLField('Карточка в Яндекс Картах (ссылка)', blank=True,
                                      default='https://yandex.ru/maps/?text=%D0%9C%D0%BE%D1%81%D0%BA%D0%B2%D0%B0%2C%20%D1%83%D0%BB.%20%D0%92%D0%B5%D1%88%D0%BD%D1%8F%D0%BA%D0%BE%D0%B2%D1%81%D0%BA%D0%B0%D1%8F%2C%2039%D0%93')
    yandex_rating = models.DecimalField('Рейтинг в Яндекс Картах', max_digits=2, decimal_places=1, null=True, blank=True,
                                        help_text='Поменяйте вручную, когда рейтинг изменится. Пусто — не показываем')
    yandex_votes = models.PositiveIntegerField('Сколько оценок в Яндекс Картах', null=True, blank=True)

    open_time = models.TimeField('Открываемся в', default=time(9, 0))
    close_time = models.TimeField('Закрываемся в', default=time(21, 0))
    hours_text = models.CharField('Часы работы (как написать на сайте)', max_length=80, blank=True,
                                  help_text='Если пусто — напишем «Ежедневно, 09:00–21:00» по времени выше')

    orders_paused = models.BooleanField('Пауза: временно не принимать заказы', default=False,
                                        help_text='Включите, если не успеваете. Букеты видно, но заказать нельзя')
    pause_message = models.CharField('Что написать клиентам во время паузы', max_length=160, blank=True,
                                     default='Сейчас не принимаем заказы на сайте — позвоните нам, соберём вручную.')
    delivery_enabled = models.BooleanField('Доставка включена', default=True)
    delivery_cost = models.PositiveIntegerField('Стоимость доставки, ₽', default=300)
    free_delivery_from = models.PositiveIntegerField('Бесплатная доставка от суммы, ₽', default=3000, help_text='0 — бесплатной доставки нет')
    min_order = models.PositiveIntegerField('Минимальная сумма заказа, ₽', default=0, help_text='0 — без ограничения')
    delivery_area_text = models.CharField('Куда доставляем (текст на сайте)', max_length=200,
                                          default='Доставляем по Москве. За МКАД и в другие города — по договорённости.')
    pickup_lead_minutes = models.PositiveSmallIntegerField('Самовывоз: за сколько минут готовим', default=20,
                                                           help_text='Ближайшее время выдачи = сейчас + столько минут')
    pickup_discount_percent = models.PositiveSmallIntegerField('Скидка при самовывозе, %', default=10,
                                                                validators=[MaxValueValidator(100)], help_text='0 — без скидки. Считается от букетов после промокода')
    delivery_lead_minutes = models.PositiveSmallIntegerField('Доставка: минимум минут до приезда', default=60)
    delivery_window_hours = models.PositiveSmallIntegerField('Доставка: длина окна, часов', default=2,
                                                             validators=[MinValueValidator(1), MaxValueValidator(6)])
    max_days_ahead = models.PositiveSmallIntegerField('На сколько дней вперёд можно заказать', default=60)
    daily_order_limit = models.PositiveSmallIntegerField('Сколько заказов принимать на один день', default=0,
                                                         help_text='0 — без ограничения. Для праздников можно задать свой лимит в «Особых днях»')

    prepay_future_orders = models.BooleanField('Заказ на другой день — только с предоплатой', default=True,
                                               help_text='Правило магазина: букет на определённую дату — только с полной предоплатой')
    allow_pay_on_receipt = models.BooleanField('Можно платить при получении (если нет предоплаты)', default=True)
    payment_details = models.TextField('Как оплатить переводом', blank=True,
                                       help_text='Например: «Перевод по СБП на +7 900 000-00-00 (Т-Банк), получатель — Имя Ф.». Клиент увидит это после заказа')

    announcement = models.CharField('Объявление над шапкой сайта', max_length=160, blank=True,
                                    help_text='Например: «Предзаказ на 8 Марта открыт». Пусто — полоски не будет')

    legal_name = models.CharField('Продавец (например, ИП Иванов Иван Иванович)', max_length=160, blank=True)
    inn = models.CharField('ИНН', max_length=12, blank=True)
    ogrnip = models.CharField('ОГРНИП / ОГРН', max_length=15, blank=True)
    legal_address = models.CharField('Юридический адрес', max_length=200, blank=True)

    metrika_id = models.CharField('Номер счётчика Яндекс Метрики', max_length=12, blank=True,
                                  help_text='Только цифры. Пусто — статистику не собираем')

    class Meta:
        verbose_name = 'Настройки сайта'
        verbose_name_plural = 'Настройки сайта'

    def __str__(self):
        return 'Настройки сайта'

    @classmethod
    def load(cls):
        obj = cache.get(cls.CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, obj, 30)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    def delete(self, *args, **kwargs):  # настройки нельзя удалить — только изменить
        return 0, {}

    @property
    def phone_href(self):
        return 'tel:+' + ''.join(ch for ch in self.phone if ch.isdigit())

    @property
    def telegram_url(self):
        return f'https://t.me/{self.telegram.lstrip("@")}' if self.telegram else ''

    @property
    def yandex_reviews_url(self):
        return self.yandex_maps_url.rstrip('/') + '/reviews/' if '/org/' in self.yandex_maps_url else ''

    @staticmethod
    def _hm(t):
        return t.strftime('%H:%M')

    @property
    def hours_display(self):
        return self.hours_text or f'Ежедневно, {self._hm(self.open_time)}–{self._hm(self.close_time)}'

    @property
    def has_requisites(self):
        return bool(self.legal_name and self.inn)


class Shop(models.Model):
    """Точка, где можно забрать заказ."""
    name = models.CharField('Название', max_length=60)
    address = models.CharField('Адрес', max_length=200, blank=True)
    landmark = models.CharField('Как найти', max_length=200, blank=True, help_text='Например: «рядом с выходом из метро»')
    phone = models.CharField('Телефон точки', max_length=30, blank=True, help_text='Пусто — покажем общий телефон магазина')
    hours_text = models.CharField('Часы работы', max_length=80, blank=True, help_text='Пусто — покажем общие часы')
    map_url = models.URLField('Ссылка на карту', blank=True)
    is_pickup = models.BooleanField('Можно забрать заказ здесь', default=True)
    is_active = models.BooleanField('Показывать на сайте', default=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Точка (магазин)'
        verbose_name_plural = 'Точки (магазины)'

    def __str__(self):
        return self.name

    @property
    def full_address(self):
        return ', '.join(x for x in (self.address, self.landmark) if x)

    @property
    def phone_href(self):
        return 'tel:+' + ''.join(ch for ch in self.phone if ch.isdigit()) if self.phone else ''


# ───────────────────────────── каталог ─────────────────────────────

class Category(models.Model):
    name = models.CharField('Название', max_length=60)
    slug = models.SlugField('Адрес страницы', unique=True, blank=True)
    description = models.TextField('Описание раздела', blank=True, help_text='Короткий текст над букетами (полезно для поиска в Яндексе)')
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Показывать на сайте', default=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Раздел каталога'
        verbose_name_plural = 'Разделы каталога'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Category, self.name, self)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:category', args=[self.slug])


class Product(models.Model):
    ART_KINDS = [
        ('rose', 'Розы'), ('chrysanthemum', 'Хризантемы'), ('alstroemeria', 'Альстромерии'),
        ('hydrangea', 'Гортензии'), ('tulip', 'Тюльпаны'), ('mixed', 'Авторский микс'),
    ]
    OCCASIONS = [
        ('birthday', 'День рождения'), ('love', 'Любимой'), ('thanks', 'Сказать спасибо'),
        ('celebration', 'Большое событие'), ('just_because', 'Просто порадовать'),
    ]

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products', verbose_name='Раздел')
    name = models.CharField('Название', max_length=120)
    slug = models.SlugField('Адрес страницы', unique=True, blank=True, max_length=100)
    tagline = models.CharField('Коротко: что в букете', max_length=140, blank=True, help_text='Например: «7 роз, зелень, упаковка»')
    description = models.TextField('Описание', blank=True)
    occasion = models.CharField('Повод для подбора', max_length=20, choices=OCCASIONS, blank=True,
                                help_text='Выберите основной повод: букет попадёт в быстрый подбор на главной и в фильтр каталога')
    price = models.PositiveIntegerField('Цена, ₽', validators=[MinValueValidator(1)])
    old_price = models.PositiveIntegerField('Старая цена, ₽', null=True, blank=True,
                                            help_text='Только для акции: покажем зачёркнутой. Обычно пусто')
    image = models.ImageField('Главное фото', upload_to='products/', blank=True, validators=[validate_image_size],
                              help_text='Без фото сайт нарисует букет сам. Лучше вертикальное фото, 4 к 5')
    badge = models.CharField('Плашка на фото', max_length=24, blank=True, help_text='Например: Хит, Новинка, Сезон')
    is_ready = models.BooleanField('Готовый букет (за 2 минуты в магазине)', default=False)
    is_active = models.BooleanField('Показывать на сайте', default=True)
    in_stock = models.BooleanField('Есть сегодня', default=True, help_text='Сняли галочку — букет виден, но заказать нельзя (например, нет цветов)')
    season_from = models.PositiveSmallIntegerField('Сезон: с месяца', choices=MONTHS, null=True, blank=True)
    season_to = models.PositiveSmallIntegerField('Сезон: по месяц', choices=MONTHS, null=True, blank=True,
                                                 help_text='Для сезонных цветов (тюльпаны — с февраля по май). Вне сезона заказать нельзя')
    popularity = models.PositiveIntegerField('Порядок показа', default=0, help_text='Чем больше число, тем выше букет в каталоге')

    art_kind = models.CharField('Рисунок, если нет фото', max_length=14, choices=ART_KINDS, default='rose')
    art_count = models.PositiveSmallIntegerField('Сколько цветков нарисовать', default=7, validators=[MinValueValidator(1), MaxValueValidator(25)])
    color_a = models.CharField('Цвет 1', max_length=7, default='#fca8c0', validators=[HEX_COLOR])
    color_b = models.CharField('Цвет 2', max_length=7, default='#e0587c', validators=[HEX_COLOR])

    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-popularity', 'name']
        verbose_name = 'Букет'
        verbose_name_plural = 'Букеты'
        indexes = [models.Index(fields=['is_active', '-popularity'])]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Product, self.name, self)
        if self.image and not self.image._committed:  # новое фото: поворачиваем и уменьшаем
            self.image = process_upload(self.image)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:product', args=[self.slug])

    @property
    def art_url(self):
        """Адрес нарисованного букета (пока нет фото). В адресе все параметры рисунка — поэтому его можно кэшировать навсегда."""
        return reverse('shop:art', args=[self.art_kind, self.art_count, self.color_a.lstrip('#').lower(), self.color_b.lstrip('#').lower()])

    # --- наличие ---
    def in_season(self, today=None):
        if not (self.season_from and self.season_to):
            return True
        month = (today or timezone.localdate()).month
        if self.season_from <= self.season_to:
            return self.season_from <= month <= self.season_to
        return month >= self.season_from or month <= self.season_to  # сезон через Новый год

    @property
    def unavailable_reason(self):
        """Пустая строка — заказать можно. Иначе — что показать вместо кнопки."""
        if not self.is_active or not self.in_stock:
            return 'Сегодня нет в наличии'
        if not self.in_season():
            return f'Сезон: с {self.get_season_from_display()} по {self.get_season_to_display()}'
        return ''

    @property
    def is_orderable(self):
        return not self.unavailable_reason

    # --- цены и размеры (всё берётся из уже подгруженных данных, лишних запросов нет) ---
    @property
    def active_variants(self):
        return sorted((v for v in self.variants.all() if v.is_active), key=lambda v: (v.order, v.price))

    @property
    def default_variant(self):
        variants = self.active_variants
        return variants[0] if variants else None

    @property
    def price_from(self):
        """Цена для каталога. Если есть размеры — самая низкая из них (на сайте «от …»)."""
        variants = self.active_variants
        return min(v.price for v in variants) if variants else self.price

    @property
    def has_choice(self):
        return len(self.active_variants) > 1

    @property
    def discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return round((self.old_price - self.price) * 100 / self.old_price)
        return 0

    @property
    def cover(self):
        """Файл главного фото или первого из галереи; None — рисуем букет сами."""
        if self.image:
            return self.image
        for photo in self.photos.all():
            return photo.image
        return None

    @property
    def gallery(self):
        files = [(self.image, self.name)] if self.image else []
        files += [(p.image, p.alt or self.name) for p in self.photos.all()]
        return files


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos', verbose_name='Букет')
    image = models.ImageField('Фото', upload_to='products/', validators=[validate_image_size])
    alt = models.CharField('Подпись к фото', max_length=120, blank=True, help_text='Например: «в руке — чтобы был виден размер»')
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Дополнительное фото'
        verbose_name_plural = 'Дополнительные фото'

    def __str__(self):
        return f'Фото {self.pk} · {self.product}'

    def save(self, *args, **kwargs):
        if self.image and not self.image._committed:
            self.image = process_upload(self.image)
        super().save(*args, **kwargs)


class Variant(models.Model):
    """Размер или вариант букета со своей ценой (например «25 роз» / «51 роза»). Необязательно."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants', verbose_name='Букет')
    name = models.CharField('Название варианта', max_length=60, help_text='Например: «Стандарт», «Большой»')
    price = models.PositiveIntegerField('Цена, ₽', validators=[MinValueValidator(1)])
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Показывать', default=True)

    class Meta:
        ordering = ['order', 'price']
        verbose_name = 'Размер / вариант'
        verbose_name_plural = 'Размеры / варианты'

    def __str__(self):
        return f'{self.product} — {self.name}'


class Addon(models.Model):
    """Дополнение к заказу: музыкальная открытка, упаковка «В дорогу» и т. п."""
    name = models.CharField('Название', max_length=80)
    description = models.CharField('Пояснение для клиента', max_length=200, blank=True)
    price = models.PositiveIntegerField('Цена, ₽', default=0, help_text='0 — бесплатно')
    note_label = models.CharField('Что спросить у клиента', max_length=80, blank=True,
                                  help_text='Например: «Какая песня? Название и исполнитель или ссылка». Пусто — ничего не спрашиваем')
    note_required = models.BooleanField('Ответ обязателен', default=False)
    is_music = models.BooleanField('Это музыкальная открытка', default=False, help_text='Нужно, чтобы на сайте показать блок «Цветы, которые звучат»')
    is_active = models.BooleanField('Показывать', default=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Дополнение к заказу'
        verbose_name_plural = 'Дополнения к заказу'

    def __str__(self):
        return self.name


class PromoCode(models.Model):
    class Kind(models.TextChoices):
        PERCENT = 'percent', 'Скидка в процентах'
        FIXED = 'fixed', 'Скидка в рублях'

    code = models.CharField('Код', max_length=30, unique=True)
    kind = models.CharField('Тип скидки', max_length=8, choices=Kind.choices, default=Kind.PERCENT)
    value = models.PositiveIntegerField('Размер скидки', validators=[MinValueValidator(1)], help_text='Проценты или рубли — смотря какой тип выбран')
    min_order = models.PositiveIntegerField('Действует от суммы букетов, ₽', default=0)
    valid_from = models.DateField('Действует с', null=True, blank=True)
    valid_until = models.DateField('Действует до', null=True, blank=True, help_text='Постоянных скидок у магазина нет — ставьте срок')
    usage_limit = models.PositiveIntegerField('Сколько раз можно применить', null=True, blank=True, help_text='Пусто — без ограничения')
    used_count = models.PositiveIntegerField('Уже применили', default=0, editable=False)
    is_active = models.BooleanField('Включён', default=True)
    note = models.CharField('Заметка для себя', max_length=120, blank=True, help_text='Для какой акции этот код')

    class Meta:
        verbose_name = 'Промокод (акция)'
        verbose_name_plural = 'Промокоды (акции)'

    def __str__(self):
        return f'{self.code} ({self.value}{"%" if self.kind == self.Kind.PERCENT else " ₽"})'

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        if self.kind == self.Kind.PERCENT:
            self.value = min(self.value, 90)
        super().save(*args, **kwargs)

    def problem(self, subtotal, today=None):
        """Возвращает текст ошибки или пустую строку, если код подходит."""
        today = today or timezone.localdate()
        if not self.is_active:
            return 'Этот промокод не действует'
        if self.valid_from and today < self.valid_from:
            return f'Промокод заработает {date_format(self.valid_from, "j E")}'
        if self.valid_until and today > self.valid_until:
            return 'Срок действия промокода закончился'
        if self.usage_limit is not None and self.used_count >= self.usage_limit:
            return 'Этот промокод уже использован'
        if subtotal < self.min_order:
            return f'Промокод действует от {self.min_order} ₽ за букеты'
        return ''

    def discount_for(self, subtotal):
        if self.kind == self.Kind.PERCENT:
            return round(subtotal * self.value / 100)
        return min(self.value, subtotal)


class SpecialDay(models.Model):
    """Особый день: выходной, праздник с другим лимитом заказов или просто пометка."""
    date = models.DateField('Дата', unique=True)
    is_closed = models.BooleanField('Заказы на этот день не принимаем', default=False)
    limit = models.PositiveSmallIntegerField('Сколько заказов принять в этот день', null=True, blank=True,
                                             help_text='Пусто — как в общих настройках. 0 — без ограничения')
    note = models.CharField('Заметка', max_length=120, blank=True, help_text='Например: «8 Марта — только по предзаказу»')

    class Meta:
        ordering = ['date']
        verbose_name = 'Особый день'
        verbose_name_plural = 'Особые дни (праздники, выходные)'

    def __str__(self):
        return f'{date_format(self.date, "j E Y")}{" — закрыто" if self.is_closed else ""}'


# ───────────────────────────── заказы ─────────────────────────────

def _new_token():
    return secrets.token_urlsafe(12)


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтверждён'
        READY = 'ready', 'Собран'
        DELIVERING = 'delivering', 'В пути'
        DONE = 'done', 'Выдан / доставлен'
        CANCELED = 'canceled', 'Отменён'

    class Method(models.TextChoices):
        PICKUP = 'pickup', 'Самовывоз'
        DELIVERY = 'delivery', 'Доставка'

    class Pay(models.TextChoices):
        ONLINE = 'online', 'Онлайн (картой или СБП)'
        TRANSFER = 'transfer', 'Переводом'
        ON_RECEIPT = 'on_receipt', 'При получении'

    class PayStatus(models.TextChoices):
        UNPAID = 'unpaid', 'Не оплачен'
        PENDING = 'pending', 'Ждём оплату'
        PAID = 'paid', 'Оплачен'
        REFUNDED = 'refunded', 'Возврат'

    token = models.CharField('Секретная ссылка', max_length=24, unique=True, default=_new_token, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders', verbose_name='Покупатель (аккаунт)')

    name = models.CharField('Имя клиента', max_length=100)
    phone = models.CharField('Телефон клиента', max_length=20)
    email = models.EmailField('Почта клиента', blank=True)

    receive_method = models.CharField('Как получит', max_length=10, choices=Method.choices, default=Method.PICKUP)
    shop = models.ForeignKey(Shop, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders', verbose_name='Где забрать')
    address = models.CharField('Адрес доставки', max_length=255, blank=True)
    address_details = models.CharField('Подъезд, этаж, домофон', max_length=120, blank=True)
    recipient_name = models.CharField('Кто получит', max_length=100, blank=True)
    recipient_phone = models.CharField('Телефон получателя', max_length=20, blank=True)
    surprise = models.BooleanField('Сюрприз: получателю не звонить и не говорить, от кого', default=False)

    date = models.DateField('Дата')
    time_from = models.TimeField('С', null=True, blank=True)
    time_to = models.TimeField('До', null=True, blank=True)
    asap = models.BooleanField('Как можно скорее', default=False)

    card_text = models.TextField('Текст открытки', blank=True, max_length=500)
    comment = models.TextField('Пожелания', blank=True, max_length=500)
    staff_note = models.TextField('Заметка сотрудников (клиент не видит)', blank=True)

    promo_code = models.CharField('Промокод', max_length=30, blank=True)
    subtotal = models.PositiveIntegerField('Букеты, ₽')
    discount = models.PositiveIntegerField('Скидка, ₽', default=0)
    addons_total = models.PositiveIntegerField('Дополнения, ₽', default=0)
    delivery_cost = models.PositiveIntegerField('Доставка, ₽', default=0)
    total = models.PositiveIntegerField('Итого, ₽')

    payment_method = models.CharField('Способ оплаты', max_length=12, choices=Pay.choices, default=Pay.ON_RECEIPT)
    payment_status = models.CharField('Оплата', max_length=10, choices=PayStatus.choices, default=PayStatus.UNPAID)
    prepay_required = models.BooleanField('Нужна предоплата', default=False)
    paid_at = models.DateTimeField('Оплачен', null=True, blank=True)
    pay_provider = models.CharField(max_length=12, blank=True, editable=False)
    pay_external_id = models.CharField(max_length=64, blank=True, editable=False)
    pay_url = models.URLField(max_length=500, blank=True, editable=False)

    status = models.CharField('Статус', max_length=12, choices=Status.choices, default=Status.NEW)
    delivery_photo = models.ImageField('Фото букета перед выдачей или доставкой', upload_to='order-photos/', blank=True,
                                       validators=[validate_image_size],
                                       help_text='Только букет: без людей, адреса, документов и посторонних данных. Клиент увидит фото по ссылке на заказ')
    source = models.CharField('Откуда пришёл клиент', max_length=40, blank=True)
    marketing_consent = models.BooleanField('Согласен получать акции и новости', default=False)
    created = models.DateTimeField('Создан', auto_now_add=True)
    updated = models.DateTimeField('Изменён', auto_now=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        indexes = [models.Index(fields=['date', 'status']), models.Index(fields=['phone'])]

    def __str__(self):
        return f'Заказ №{self.pk} — {self.name}'

    def save(self, *args, **kwargs):
        if self.delivery_photo and not self.delivery_photo._committed:
            self.delivery_photo = process_upload(self.delivery_photo)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('shop:order_status', args=[self.token])

    @property
    def number(self):
        return self.pk

    def set_status(self, status):
        """Меняет статус. Заказ «при получении» в момент выдачи считается оплаченным."""
        self.status = status
        fields = ['status', 'updated']
        if status == self.Status.DONE and self.payment_status == self.PayStatus.UNPAID and self.payment_method == self.Pay.ON_RECEIPT:
            self.payment_status, self.paid_at = self.PayStatus.PAID, timezone.now()
            fields += ['payment_status', 'paid_at']
        self.save(update_fields=fields)

    def mark_paid(self):
        if self.payment_status != self.PayStatus.PAID:
            self.payment_status, self.paid_at = self.PayStatus.PAID, timezone.now()
            self.save(update_fields=['payment_status', 'paid_at', 'updated'])

    @property
    def is_paid(self):
        return self.payment_status == self.PayStatus.PAID

    @property
    def is_active(self):
        return self.status not in (self.Status.DONE, self.Status.CANCELED)

    @property
    def display_phone(self):
        return format_phone(self.phone)

    @property
    def display_recipient_phone(self):
        return format_phone(self.recipient_phone)

    @property
    def time_display(self):
        if self.asap:
            return 'как можно скорее'
        if self.time_from and self.time_to:
            return f'{self.time_from:%H:%M}–{self.time_to:%H:%M}'
        if self.time_from:
            return f'к {self.time_from:%H:%M}'
        return ''

    @property
    def when_display(self):
        return ', '.join(x for x in (format_day(self.date), self.time_display) if x)

    @property
    def sort_time(self):
        return self.time_from or time(0, 0)

    @property
    def place_display(self):
        if self.receive_method == self.Method.DELIVERY:
            return ' '.join(x for x in (self.address, self.address_details) if x)
        return f'Самовывоз: {self.shop.name}' if self.shop else 'Самовывоз'

    @property
    def status_steps(self):
        """Шаги для полоски статуса на странице клиента."""
        S = self.Status
        if self.receive_method == self.Method.DELIVERY:
            return [(S.NEW, 'Принят'), (S.CONFIRMED, 'Подтверждён'), (S.READY, 'Собран'), (S.DELIVERING, 'В пути'), (S.DONE, 'Доставлен')]
        return [(S.NEW, 'Принят'), (S.CONFIRMED, 'Подтверждён'), (S.READY, 'Готов к выдаче'), (S.DONE, 'Выдан')]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Букет')
    variant = models.ForeignKey(Variant, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField('Название (на момент заказа)', max_length=120)
    variant_name = models.CharField('Размер', max_length=60, blank=True)
    price = models.PositiveIntegerField('Цена, ₽')
    qty = models.PositiveSmallIntegerField('Кол-во')

    class Meta:
        verbose_name = 'Букет в заказе'
        verbose_name_plural = 'Состав заказа'

    def __str__(self):
        return f'{self.full_name} × {self.qty}'

    @property
    def full_name(self):
        return f'{self.name} ({self.variant_name})' if self.variant_name else self.name

    @property
    def line_total(self):
        return self.price * self.qty


class OrderAddon(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='addons')
    addon = models.ForeignKey(Addon, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField('Название', max_length=80)
    price = models.PositiveIntegerField('Цена, ₽', default=0)
    note = models.CharField('Ответ клиента (например, песня)', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Дополнение в заказе'
        verbose_name_plural = 'Дополнения в заказе'

    def __str__(self):
        return self.name


# ───────────────────────────── тексты и заявки ─────────────────────────────

class Review(models.Model):
    """Настоящие отзывы клиентов (с их разрешения). Выдуманных отзывов на сайте нет."""
    class Source(models.TextChoices):
        YANDEX = 'yandex', 'Яндекс Карты'
        GIS = '2gis', '2ГИС'
        SITE = 'site', 'Написал нам'
        OTHER = 'other', 'Другое'

    name = models.CharField('Имя', max_length=60)
    text = models.TextField('Отзыв', max_length=600)
    rating = models.PositiveSmallIntegerField('Оценка', null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    source = models.CharField('Где оставили', max_length=8, choices=Source.choices, default=Source.YANDEX)
    source_url = models.URLField('Ссылка на оригинальный отзыв', blank=True)
    permission_given = models.BooleanField('Отзыв проверен и разрешён к публикации', default=False,
                                           help_text='Ставьте только после проверки настоящего отзыва и права на его публикацию')
    is_published = models.BooleanField('Показывать на сайте', default=True)
    created = models.DateTimeField('Добавлен', default=timezone.now)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'

    def clean(self):
        errors = {}
        if self.is_published and not self.permission_given:
            errors['permission_given'] = 'Перед публикацией проверьте отзыв и подтвердите разрешение.'
        if self.source_url and urlparse(self.source_url).scheme not in ('http', 'https'):
            errors['source_url'] = 'Допустима только ссылка http или https.'
        if self.is_published and self.source == self.Source.YANDEX:
            parsed = urlparse(self.source_url)
            host = (parsed.hostname or '').lower()
            if parsed.scheme != 'https' or not (host == 'yandex.ru' or host.endswith('.yandex.ru')) or '/maps/org/' not in parsed.path:
                errors['source_url'] = 'Добавьте полную ссылку на отзыв в карточке организации на Яндекс Картах.'
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f'{self.name}: {self.text[:30]}'


class Lead(models.Model):
    """Заявка с сайта: офисы, подписка, вопрос или своя композиция."""
    class Kind(models.TextChoices):
        OFFICE = 'office', 'Цветы для офиса'
        SUBSCRIPTION = 'subscription', 'Подписка на цветы'
        QUESTION = 'question', 'Вопрос'
        BOUQUET = 'bouquet', 'Свой букет'
        BALLOONS = 'balloons', 'Шары'
        SOUVENIRS = 'souvenirs', 'Сувениры'

    class Status(models.TextChoices):
        NEW = 'new', 'Новая'
        WORK = 'work', 'В работе'
        DONE = 'done', 'Закрыта'

    kind = models.CharField('Тип заявки', max_length=14, choices=Kind.choices)
    name = models.CharField('Имя', max_length=100)
    company = models.CharField('Компания', max_length=120, blank=True)
    phone = models.CharField('Телефон', max_length=20)
    email = models.EmailField('Почта', blank=True)
    message = models.TextField('Сообщение', blank=True, max_length=1000)
    layout = models.JSONField('Эскиз композиции', default=dict, blank=True)
    status = models.CharField('Статус', max_length=6, choices=Status.choices, default=Status.NEW)
    staff_note = models.TextField('Заметка (клиент не видит)', blank=True)
    source = models.CharField('Откуда пришёл клиент', max_length=40, blank=True)
    created = models.DateTimeField('Пришла', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'

    def __str__(self):
        return f'{self.get_kind_display()} — {self.name}'

    @property
    def display_phone(self):
        return format_phone(self.phone)


class LegalAcceptance(models.Model):
    """Кто, когда и какую редакцию документа принял; записи не редактируются через панель."""
    class Kind(models.TextChoices):
        OFFER = 'offer', 'Публичная оферта'
        PERSONAL = 'personal', 'Согласие на обработку ПДн'
        MARKETING = 'marketing', 'Согласие на рекламные сообщения'

    class Action(models.TextChoices):
        ACCEPTED = 'accepted', 'Принято'
        WITHDRAWN = 'withdrawn', 'Отозвано'

    kind = models.CharField('Документ', max_length=12, choices=Kind.choices)
    action = models.CharField('Действие', max_length=10, choices=Action.choices, default=Action.ACCEPTED)
    version = models.CharField('Редакция', max_length=12)
    reference = models.CharField('Заказ / заявка / аккаунт', max_length=80, blank=True)
    contact = models.CharField('Контакт для связи с субъектом', max_length=254, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='legal_acceptances')
    ip_address = models.CharField('IP при выборе', max_length=64, blank=True)
    user_agent = models.CharField('Браузер при выборе', max_length=300, blank=True)
    created = models.DateTimeField('Дата и время', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Акцепт / согласие'
        verbose_name_plural = 'Журнал акцептов и согласий'
        indexes = [models.Index(fields=['kind', 'created']), models.Index(fields=['reference'])]

    def __str__(self):
        return f'{self.get_kind_display()} · {self.get_action_display()} · {self.created:%d.%m.%Y %H:%M}'


class FAQ(models.Model):
    question = models.CharField('Вопрос', max_length=160)
    answer = models.TextField('Ответ')
    order = models.PositiveSmallIntegerField('Порядок', default=0)
    is_active = models.BooleanField('Показывать', default=True)

    class Meta:
        ordering = ['order', 'id']
        verbose_name = 'Вопрос и ответ'
        verbose_name_plural = 'Вопросы и ответы'

    def __str__(self):
        return self.question
