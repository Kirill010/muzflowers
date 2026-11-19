from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import BotOperation


class Command(BaseCommand):
    help = 'Удаляет ответы служебного API старше 90 дней по правилам хранения'

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(days=90)
        count, _ = BotOperation.objects.filter(created__lt=cutoff).delete()
        self.stdout.write(f'Удалено старых операций бота: {count}')
