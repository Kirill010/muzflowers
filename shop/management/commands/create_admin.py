from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
import os


class Command(BaseCommand):
    help = 'Создаёт суперпользователя без интерактивного ввода'

    def handle(self, *args, **options):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME', 'admin')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@muzflowers.ru')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD', 'MuzFlowers2026!')

        user, created = User.objects.get_or_create(
            username=username,
            defaults={'email': email},
        )
        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(
                f'✅ Суперпользователь "{username}" создан. Пароль: {password}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Пользователь "{username}" уже был. Пароль обновлён.'
            ))