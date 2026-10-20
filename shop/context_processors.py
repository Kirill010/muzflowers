from django.conf import settings


def site(request):
    return {'site': {
        'phone': settings.SHOP_PHONE, 'email': settings.SHOP_EMAIL,
        'address': settings.SHOP_ADDRESS, 'hours': settings.SHOP_HOURS,
    }}
