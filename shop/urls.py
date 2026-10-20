from django.urls import path

from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.index, name='index'),
    path('privacy/', views.privacy, name='privacy'),
    path('api/promo/', views.promo_check, name='promo'),
    path('api/order/', views.order_create, name='order'),
]
