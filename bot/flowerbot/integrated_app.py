from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramNetworkError, TelegramUnauthorizedError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, ErrorEvent

from . import backup, notify
from .app import ConnectionProblem, make_session, set_default_descriptions
from .config import ConfigError, Settings
from .db import Database
from .integrated_handlers import IntegratedContext, router
from .integrated_store import IntegratedStore
from .middlewares import Throttle, UserMiddleware
from .shop_api import ShopClient

log = logging.getLogger('flowerbot')
COMMANDS = [BotCommand(command='catalog', description='Каталог'), BotCommand(command='cart', description='Корзина'),
            BotCommand(command='orders', description='Мои заказы'), BotCommand(command='help', description='Помощь')]


async def reminders_loop(ctx: IntegratedContext, bot: Bot) -> None:
    while True:
        await asyncio.sleep(60)
        try:
            result = await ctx.client.post('staff/orders', {'telegram_user_id': ctx.settings.admin_ids[0] if ctx.settings.admin_ids else 0})
            now = datetime.now(timezone.utc)
            for order in result['orders']:
                if order['status'] != 'new' or not order.get('created'):
                    continue
                age = now - datetime.fromisoformat(order['created'])
                level = 1 if age >= timedelta(minutes=15) else 2 if age >= timedelta(hours=1) else 0
                key = order['id']
                if level and ctx.nudged.get(key) != level:
                    ctx.nudged[key] = level
                    await notify.to_staff(bot, ctx, f"⏰ Заказ №{order['id']} ждёт подтверждения уже {int(age.total_seconds() // 60)} мин.")
        except Exception as exc:
            log.warning('Не удалось проверить ожидающие заказы: %s', exc)


async def run_integrated(settings: Settings) -> None:
    db = Database(settings.db_path)
    client = ShopClient(settings)
    store = IntegratedStore(db)
    ctx = IntegratedContext(settings=settings, db=db, client=client, store=store)
    bot = Bot(settings.bot_token, session=make_session(settings),
              default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    tasks = []
    try:
        try:
            me = await bot.get_me()
            await ctx.bootstrap()
        except TelegramUnauthorizedError:
            raise ConfigError('Telegram не принял BOT_TOKEN. Отзовите старый и вставьте новый ключ.') from None
        except (TelegramNetworkError, asyncio.TimeoutError, OSError) as exc:
            raise ConnectionProblem(f'Нет связи: {exc}') from exc
        ctx.bot_username = me.username or ''
        await bot.delete_webhook(drop_pending_updates=False)
        await bot.set_my_commands(COMMANDS)
        await set_default_descriptions(bot, 'MuzFlowers Выхино')
        dp = Dispatcher(storage=MemoryStorage())
        dp['ctx'] = ctx
        for observer in (dp.message, dp.callback_query):
            observer.outer_middleware(Throttle())
            observer.outer_middleware(UserMiddleware())
        dp.include_router(router)

        @dp.errors()
        async def on_error(event: ErrorEvent) -> bool:
            log.error('Ошибка интегрированного бота: %r', event.exception, exc_info=event.exception)
            update = event.update
            try:
                if update.message:
                    await update.message.answer('Не получилось выполнить действие. Попробуйте ещё раз или напишите менеджеру.')
                elif update.callback_query:
                    await update.callback_query.answer('Не получилось. Попробуйте ещё раз.', show_alert=True)
            except TelegramAPIError:
                pass
            return True

        tasks = [asyncio.create_task(backup.backup_loop(ctx)), asyncio.create_task(reminders_loop(ctx, bot))]
        await notify.to_staff(bot, ctx, '🌸 Бот Выхино запущен. Заказы и каталог — из общей базы сайта.')
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await client.close()
        await bot.session.close()
        db.close()
