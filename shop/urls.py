from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic import RedirectView

from . import bot_api, cart_views, certificate_views, checkout_views, seo, views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<slug:slug>/', views.catalog, name='category'),
    path('product/<slug:slug>/', views.product, name='product'),
    path('search/suggest/', views.suggest, name='suggest'),
    path('bouquet/', views.bouquet_builder, name='bouquet_builder'),
    path('balloons/', views.balloons, name='balloons'),
    path('souvenirs/', views.souvenirs, name='souvenirs'),

    path('cart/', cart_views.cart_page, name='cart'),
    path('cart/add/', cart_views.cart_add, name='cart_add'),
    path('cart/update/', cart_views.cart_update, name='cart_update'),
    path('cart/remove/', cart_views.cart_remove, name='cart_remove'),
    path('cart/addon/', cart_views.cart_addon, name='cart_addon'),
    path('cart/promo/', cart_views.cart_promo, name='cart_promo'),
    path('cart/fragment/', cart_views.cart_fragment, name='cart_fragment'),

    path('checkout/', checkout_views.checkout, name='checkout'),
    path('checkout/state/', checkout_views.checkout_state, name='checkout_state'),
    path('order/<str:token>/', checkout_views.order_status, name='order_status'),
    path('order/<str:token>/pay/', checkout_views.order_pay, name='order_pay'),
    path('payments/webhook/<str:provider>/', checkout_views.payment_webhook, name='payment_webhook'),
    path('certificates/', certificate_views.certificate_purchase, name='certificates'),

    path('api/bot/v1/bootstrap/', bot_api.bootstrap, name='bot_bootstrap'),
    path('api/bot/v1/quote/', bot_api.quote, name='bot_quote'),
    path('api/bot/v1/availability/', bot_api.availability, name='bot_availability'),
    path('api/bot/v1/orders/', bot_api.order_create, name='bot_order_create'),
    path('api/bot/v1/orders/list/', bot_api.order_list, name='bot_order_list'),
    path('api/bot/v1/orders/detail/', bot_api.order_detail, name='bot_order_detail'),
    path('api/bot/v1/orders/cancel/', bot_api.order_cancel, name='bot_order_cancel'),
    path('api/bot/v1/orders/payment/', bot_api.payment_link, name='bot_payment_link'),
    path('api/bot/v1/certificates/purchase/', bot_api.certificate_purchase, name='bot_certificate_purchase'),
    path('api/bot/v1/certificates/check/', bot_api.certificate_check, name='bot_certificate_check'),
    path('api/bot/v1/certificates/list/', bot_api.certificate_list, name='bot_certificate_list'),
    path('api/bot/v1/leads/', bot_api.lead_create, name='bot_lead_create'),
    path('api/bot/v1/reviews/', bot_api.review_create, name='bot_review_create'),
    path('api/bot/v1/reviews/list/', bot_api.review_list, name='bot_review_list'),
    path('api/bot/v1/staff/orders/', bot_api.staff_orders, name='bot_staff_orders'),
    path('api/bot/v1/staff/status/', bot_api.staff_status, name='bot_staff_status'),
    path('api/bot/v1/staff/paid/', bot_api.staff_paid, name='bot_staff_paid'),
    path('api/bot/v1/staff/stock/', bot_api.staff_stock, name='bot_staff_stock'),

    path('music/', views.music, name='music'),
    path('offices/', views.offices, name='offices'),
    path('subscription/', views.subscription, name='subscription'),
    path('delivery/', views.delivery, name='delivery'),
    path('care/', views.care, name='care'),
    path('about/', views.about, name='about'),
    path('presentation/', RedirectView.as_view(pattern_name='shop:about', permanent=True), name='presentation'),
    path('contacts/', views.contacts, name='contacts'),
    path('faq/', views.faq, name='faq'),
    path('privacy/', views.privacy, name='privacy'),
    path('offer/', views.offer, name='offer'),
    path('legal/', views.legal, name='legal'),
    path('consent/', views.consent, name='consent'),
    path('marketing-consent/', views.marketing_consent, name='marketing_consent'),
    path('cookies/', views.cookies, name='cookies'),

    path('art/<slug:kind>/<int:count>/<str:a>/<str:b>.svg', views.art, name='art'),
    path('art/stem/<slug:kind>.svg', views.stem_art, name='stem_art'),
    path('favicon.ico', views.favicon, name='favicon'),
    path('robots.txt', seo.robots, name='robots'),
    path('sitemap.xml', sitemap, {'sitemaps': seo.SITEMAPS}, name='sitemap'),
    path('manifest.webmanifest', seo.manifest, name='manifest'),
    path('health/', views.health, name='health'),
]
