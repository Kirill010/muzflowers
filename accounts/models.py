from django.conf import settings
from django.db import models

from shop.utils import format_phone, normalize_phone


class Profile(models.Model):
    """Дополнительные данные покупателя: телефон и адрес подставляются при оформлении заказа."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Телефон', max_length=20, blank=True)
    address = models.CharField('Адрес доставки по умолчанию', max_length=255, blank=True)
    marketing_consent = models.BooleanField('Согласен получать акции и новости', default=False)

    class Meta:
        verbose_name = 'Профиль покупателя'
        verbose_name_plural = 'Профили покупателей'

    def __str__(self):
        return f'Профиль: {self.user}'

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    @property
    def display_phone(self):
        return format_phone(self.phone)


def profile_of(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile
