from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone

HEX_COLOR = RegexValidator(r'^#[0-9a-fA-F]{6}$', 'Цвет в формате #RRGGBB')


class Category(models.Model):
    name = models.CharField('Название', max_length=60)
    slug = models.SlugField('Слаг', unique=True)
    order = models.PositiveSmallIntegerField('Порядок', default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products', verbose_name='Категория')
    name = models.CharField('Название', max_length=120)
    description = models.CharField('Описание', max_length=200, blank=True)
    price = models.PositiveIntegerField('Цена, ₽')
    image = models.ImageField('Фото', upload_to='products/', blank=True)
    badge = models.CharField('Плашка', max_length=20, blank=True, help_text='Например: Хит, Новинка')
    color_a = models.CharField('Цвет лепестков 1', max_length=7, default='#f4a6b8', validators=[HEX_COLOR])
    color_b = models.CharField('Цвет лепестков 2', max_length=7, default='#e0587c', validators=[HEX_COLOR])
    petals = models.PositiveSmallIntegerField('Лепестков в рисунке', default=10, validators=[MinValueValidator(3), MaxValueValidator(24)])
    popularity = models.PositiveIntegerField('Популярность', default=0)
    is_active = models.BooleanField('Показывать на сайте', default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-popularity', '-created']
        verbose_name = 'Букет'
        verbose_name_plural = 'Букеты'

    def __str__(self):
        return self.name


class PromoCode(models.Model):
    code = models.CharField('Код', max_length=30, unique=True)
    percent = models.PositiveSmallIntegerField('Скидка, %', validators=[MinValueValidator(1), MaxValueValidator(90)])
    is_active = models.BooleanField('Активен', default=True)
    valid_until = models.DateField('Действует до', null=True, blank=True)

    class Meta:
        verbose_name = 'Промокод'
        verbose_name_plural = 'Промокоды'

    def is_valid(self):
        return self.is_active and (self.valid_until is None or self.valid_until >= timezone.localdate())

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.percent = min(self.percent, 90)
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code} (−{self.percent}%)'


class Order(models.Model):
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        CONFIRMED = 'confirmed', 'Подтверждён'
        DELIVERING = 'delivering', 'В доставке'
        DONE = 'done', 'Выполнен'
        CANCELED = 'canceled', 'Отменён'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='orders', verbose_name='Пользователь')
    name = models.CharField('Имя', max_length=100)
    phone = models.CharField('Телефон', max_length=30)
    address = models.CharField('Адрес', max_length=255)
    delivery_date = models.DateField('Дата доставки')
    delivery_slot = models.CharField('Время', max_length=20)
    card_text = models.TextField('Текст открытки', blank=True, max_length=500)
    promo_code = models.CharField('Промокод', max_length=30, blank=True)
    subtotal = models.PositiveIntegerField('Товары, ₽')
    discount = models.PositiveIntegerField('Скидка, ₽', default=0)
    delivery_cost = models.PositiveIntegerField('Доставка, ₽', default=0)
    total = models.PositiveIntegerField('Итого, ₽')
    status = models.CharField('Статус', max_length=12, choices=Status.choices, default=Status.NEW)
    created = models.DateTimeField('Создан', auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f'Заказ №{self.pk} — {self.name}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True)
    name = models.CharField('Название (на момент заказа)', max_length=120)
    price = models.PositiveIntegerField('Цена, ₽')
    qty = models.PositiveSmallIntegerField('Кол-во')

    def __str__(self):
        return f'{self.name} × {self.qty}'


class Review(models.Model):
    name = models.CharField('Имя', max_length=60)
    text = models.TextField('Отзыв', max_length=400)
    is_published = models.BooleanField('Показывать на сайте', default=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created']
        verbose_name = 'Отзыв'
        verbose_name_plural = 'Отзывы'

    def __str__(self):
        return f'{self.name}: {self.text[:30]}'
