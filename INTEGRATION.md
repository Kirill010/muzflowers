# Muzflowers — подключение витрины к Django

Файлы лежат в тех же папках, что и в вашем репозитории:
`shop/`, `templates/shop/index.html`, `static/shop/{css,js}`.

## 1. Если в `shop/` уже есть свои модели
Сравните с `shop/models.py` и перенесите недостающее. Для витрины нужны у букета:
`name, description, price, image, badge, color_a, color_b, petals, popularity, is_active`, у категории — `name`.
Если ваши модели уже готовы, правится только `index()` в `shop/views.py` (сборка списка `products`).

## 2. requirements.txt
    Django>=4.2
    Pillow>=10

## 3. muzflowers/settings.py
    INSTALLED_APPS += ['shop']                      # если ещё не добавлено
    TEMPLATES[0]['DIRS'] = [BASE_DIR / 'templates']
    STATICFILES_DIRS = [BASE_DIR / 'static']
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    LANGUAGE_CODE = 'ru'
    TIME_ZONE = 'Europe/Moscow'                     # ваш часовой пояс
    SHOP_FREE_DELIVERY_FROM = 3000                  # необязательно
    SHOP_DELIVERY_COST = 300                        # необязательно

## 4. muzflowers/urls.py
    from django.conf import settings
    from django.conf.urls.static import static
    from django.contrib import admin
    from django.urls import include, path

    urlpatterns = [
        path('admin/', admin.site.urls),
        path('', include('shop.urls')),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

## 5. Запуск
    pip install -r requirements.txt
    python manage.py makemigrations shop
    python manage.py migrate
    python manage.py seed_shop        # демо-букеты и промокод MUZ10
    python manage.py createsuperuser
    python manage.py test shop
    python manage.py runserver

В `/admin/` — букеты (с загрузкой фото), промокоды и заказы со сменой статуса.
Фото не загружено — на витрине рисуется цветок по цветам `color_a`/`color_b`.

## Как это устроено
- Витрина получает букеты из БД через `json_script`, без лишних запросов.
- Корзина хранится в браузере (localStorage), заказ уходит на `/api/order/`.
- Сервер сам пересчитывает цены, скидку по промокоду и доставку, данным клиента он не доверяет.
- CSRF-токен берётся из cookie, дата доставки и телефон проверяются на сервере.

## Что стоит сделать дальше
- Уведомление о новом заказе (Telegram-бот или email) — сигнал `post_save` на `Order`.
- Оплата онлайн (ЮKassa) после создания заказа.
- Мета-теги и sitemap, `whitenoise` и настройки `DEBUG=False` для продакшена.
- Если в `accounts` есть пользователи, привязать `Order.user` и сделать историю заказов.
