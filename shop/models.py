from django.db import models
from django.urls import reverse
from taggit.managers import TaggableManager


class Category(models.Model):
    name = models.CharField(max_length=200, db_index=True, verbose_name="Название")
    slug = models.SlugField(max_length=200, unique=True, verbose_name="URL-идентификатор")
    image = models.ImageField(upload_to='categories/', blank=True, verbose_name="Изображение")
    description = models.TextField(blank=True, verbose_name="Описание")

    class Meta:
        ordering = ('name',)
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_list_by_category', args=[self.slug])


class Product(models.Model):
    OCCASION_CHOICES = [
        ('birthday', 'День рождения'),
        ('wedding', 'Свадьба'),
        ('anniversary', 'Годовщина'),
        ('romance', 'Романтика'),
        ('congratulations', 'Поздравление'),
        ('sympathy', 'Соболезнования'),
        ('other', 'Другое'),
    ]

    category = models.ForeignKey(
        Category, related_name='products',
        on_delete=models.CASCADE, verbose_name="Категория"
    )
    name = models.CharField(max_length=200, db_index=True, verbose_name="Название")
    slug = models.SlugField(max_length=200, db_index=True, verbose_name="URL-идентификатор")
    image = models.ImageField(upload_to='products/%Y/%m/%d', blank=True, verbose_name="Фото")
    description = models.TextField(blank=True, verbose_name="Описание")
    short_description = models.CharField(max_length=300, blank=True, verbose_name="Краткое описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Цена")
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                    verbose_name="Старая цена")
    occasion = models.CharField(max_length=20, choices=OCCASION_CHOICES, default='other',
                                verbose_name="Повод")
    tags = TaggableManager(blank=True, verbose_name="Теги")
    available = models.BooleanField(default=True, verbose_name="В наличии")
    stock = models.PositiveIntegerField(default=10, verbose_name="Количество на складе")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0,
                                 verbose_name="Рейтинг")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('name',)
        indexes = [models.Index(fields=['id', 'slug'])]
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('shop:product_detail', args=[self.id, self.slug])

    def get_discount_percent(self):
        if self.old_price and self.old_price > self.price:
            return int((self.old_price - self.price) / self.old_price * 100)
        return 0

    def update_rating(self):
        from django.db.models import Avg
        avg = self.reviews.filter(is_approved=True).aggregate(r=Avg('rating'))['r']
        self.rating = round(avg, 2) if avg else 0
        self.save(update_fields=['rating'])


class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('processing', 'В обработке'),
        ('assembled', 'Собран'),
        ('delivering', 'Доставляется'),
        ('delivered', 'Доставлен'),
        ('cancelled', 'Отменён'),
    ]

    user = models.ForeignKey(
        'auth.User', related_name='orders',
        on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Пользователь"
    )
    first_name = models.CharField(max_length=50, verbose_name="Имя")
    last_name = models.CharField(max_length=50, verbose_name="Фамилия")
    email = models.EmailField(verbose_name="Email")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    address = models.CharField(max_length=250, verbose_name="Адрес доставки")
    delivery_date = models.DateField(verbose_name="Дата доставки")
    delivery_time = models.CharField(max_length=20, blank=True, verbose_name="Время доставки")
    comment = models.TextField(blank=True, verbose_name="Комментарий к заказу")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new',
                              verbose_name="Статус")
    paid = models.BooleanField(default=False, verbose_name="Оплачен")
    promo_code = models.CharField(max_length=50, blank=True, verbose_name="Промокод")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                          verbose_name="Сумма скидки")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created',)
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def __str__(self):
        return f'Заказ {self.id}'

    def get_total_cost(self):
        return sum(item.get_cost() for item in self.items.all())

    def get_final_cost(self):
        return self.get_total_cost() - self.discount_amount


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, related_name='order_items', on_delete=models.CASCADE)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return str(self.id)

    def get_cost(self):
        return self.price * self.quantity


class ConsultationRequest(models.Model):
    name = models.CharField(max_length=100, verbose_name="Имя")
    phone = models.CharField(max_length=20, verbose_name="Телефон")
    email = models.EmailField(blank=True, verbose_name="Email")
    occasion = models.CharField(max_length=20, choices=Product.OCCASION_CHOICES,
                                default='other', verbose_name="Повод")
    budget_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     verbose_name="Бюджет от")
    budget_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                     verbose_name="Бюджет до")
    message = models.TextField(verbose_name="Пожелания")
    processed = models.BooleanField(default=False, verbose_name="Обработана")
    created = models.DateTimeField(auto_now_add=True, verbose_name="Создана")

    class Meta:
        ordering = ('-created',)
        verbose_name = 'Заявка на консультацию'
        verbose_name_plural = 'Заявки на консультацию'

    def __str__(self):
        return f'Заявка от {self.name} ({self.phone})'