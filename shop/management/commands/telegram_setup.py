import json
import urllib.error
import urllib.request

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop import notifications


class Command(BaseCommand):
    help = ('Помогает подключить уведомления о заказах в Telegram. Без параметров показывает номера чатов, '
            'из которых писали вашему боту (нужны для TELEGRAM_CHAT_ID). С параметром --test отправляет пробное сообщение.')

    def add_arguments(self, parser):
        parser.add_argument('--test', action='store_true', help='Отправить пробное сообщение в чаты из TELEGRAM_CHAT_ID')

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            raise CommandError('В файле .env не указан TELEGRAM_BOT_TOKEN (ключ бота от @BotFather).')
        if options['test']:
            if not settings.TELEGRAM_CHAT_ID:
                raise CommandError('В файле .env не указан TELEGRAM_CHAT_ID. Сначала запустите эту команду без --test.')
            try:
                notifications.send_telegram('✅ MuzFlowers: уведомления о заказах подключены.')
            except (urllib.error.URLError, OSError) as exc:
                raise CommandError(f'Telegram не принял сообщение: {exc}') from exc
            self.stdout.write(self.style.SUCCESS('Пробное сообщение отправлено — проверьте чат.'))
            return

        try:
            with urllib.request.urlopen(f'https://api.telegram.org/bot{token}/getUpdates', timeout=15) as response:  # noqa: S310
                data = json.loads(response.read().decode('utf-8'))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise CommandError(f'Не удалось связаться с Telegram (проверьте ключ и интернет): {exc}') from exc

        chats = {}
        for update in data.get('result', []):
            for key in ('message', 'channel_post', 'edited_message', 'my_chat_member'):
                chat = (update.get(key) or {}).get('chat')
                if chat:
                    chats[chat['id']] = chat.get('title') or chat.get('first_name') or chat.get('username') or 'без названия'
        if not chats:
            self.stdout.write('Чатов пока нет. Добавьте бота в группу (или напишите ему сами), отправьте любое сообщение и запустите команду снова.')
            return
        self.stdout.write('Чаты, из которых писали вашему боту:')
        for chat_id, title in chats.items():
            self.stdout.write(f'  TELEGRAM_CHAT_ID={chat_id}    ({title})')
        self.stdout.write('Впишите нужную строку в файл .env, перезапустите сайт и проверьте: telegram_setup --test')
