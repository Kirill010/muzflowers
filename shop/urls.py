from django.contrib.sitemaps.views import sitemap
from django.urls import path
from django.views.generic import RedirectView

from . import cart_views, checkout_views, seo, views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<slug:slug>/', views.catalog, name='category'),
    path('product/<slug:slug>/', views.product, name='product'),
    path('search/suggest/', views.suggest, name='suggest'),
    path('bouquet/', views.bouquet_builder, name='bouquet_builder'),

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
