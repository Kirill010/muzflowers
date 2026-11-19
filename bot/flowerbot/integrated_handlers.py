from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, Message, ReplyKeyboardMarkup, URLInputFile

from . import notify
from .config import Settings
from .db import Database
from .integrated_store import IntegratedStore
from .shop_api import ShopApiError, ShopClient
from .util import esc, phone_from_input, rub

router = Router(name='vykhino-integrated')
MENU = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text='🌸 Каталог'), KeyboardButton(text='🛒 Корзина')],
    [KeyboardButton(text='🧾 Мои заказы'), KeyboardButton(text='🎁 Сертификат')],
    [KeyboardButton(text='🚚 Доставка'), KeyboardButton(text='💬 Менеджер')],
    [KeyboardButton(text='👑 Панель')],
], resize_keyboard=True)


class Flow(StatesGroup):
    contact = State()
    address = State()
    recipient_name = State()
    recipient_phone = State()
    comment = State()
    code = State()
    addon_note = State()
    certificate_amount = State()
    certificate_check = State()
    manager_contact = State()
    manager_text = State()
    review_text = State()


@dataclass
class IntegratedContext:
    settings: Settings
    db: Database
    client: ShopClient
    store: IntegratedStore
    bot_username: str = ''
    cached: dict = field(default_factory=dict)
    cached_at: float = 0
    nudged: dict = field(default_factory=dict)

    async def bootstrap(self, force: bool = False) -> dict:
        if force or time.monotonic() - self.cached_at > 60 or not self.cached:
            self.cached = await self.client.post('bootstrap', {})
            self.cached_at = time.monotonic()
        return self.cached

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.settings.admin_ids

    def now(self) -> datetime:
        return self.db.clock()

    def local_now(self) -> datetime:
        return self.now().astimezone()

    @property
    def shop(self) -> dict:
        return self.cached.get('shop', {})


def buttons(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, callback_data=data) for text, data in row] for row in rows])


def links(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=text, url=url) for text, url in row] for row in rows])


async def answer(message: Message, text: str, markup=None) -> None:
    await message.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def edit(call: CallbackQuery, text: str, markup=None) -> None:
    if call.message is None:
        return
    try:
        if call.message.photo:
            await call.message.edit_caption(caption=text, reply_markup=markup)
        else:
            await call.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception as exc:
        if 'message is not modified' not in str(exc):
            await call.message.answer(text, reply_markup=markup, disable_web_page_preview=True)


def product_by_id(data: dict, product_id: int) -> dict | None:
    return next((product for product in data['products'] if product['id'] == product_id), None)


def variant_by_id(product: dict, variant_id: int) -> dict | None:
    variants = product.get('variants', [])
    if not variants:
        return None
    return next((variant for variant in variants if variant['id'] == variant_id), variants[0])


def line_names(data: dict, lines: list[dict]) -> list[str]:
    names = []
    for line in lines:
        product = product_by_id(data, line['product'])
        if product is None:
            continue
        variant = variant_by_id(product, line['variant'])
        suffix = f" · {variant['name']}" if variant else ''
        names.append(f"• {esc(product['name'])}{esc(suffix)} × {line['qty']} — {rub((variant or product)['price'] * line['qty'])}")
    return names


def quote_payload(ctx: IntegratedContext, user_id: int, extra: dict | None = None) -> dict:
    cart = ctx.store.cart(user_id)
    payload = {**cart, 'date': date.today().isoformat()}
    payload.update(extra or {})
    return payload


async def get_quote(ctx: IntegratedContext, user_id: int, extra: dict | None = None) -> dict:
    return await ctx.client.post('quote', quote_payload(ctx, user_id, extra))


async def show_catalog(message: Message, ctx: IntegratedContext, page: int = 0, user_id: int | None = None) -> None:
    data = await ctx.bootstrap()
    products = data['products']
    pages = max(1, (len(products) + 5) // 6)
    page = max(0, min(page, pages - 1))
    rows = []
    for product in products[page * 6:(page + 1) * 6]:
        marker = '' if product['available'] else ' · уточнить'
        rows.append([(f"{product['name']} · {rub(product['price'])}{marker}", f"p:{product['id']}")])
    if pages > 1:
        rows.append([('◀', f'cl:{(page - 1) % pages}'), (f'{page + 1}/{pages}', 'noop'), ('▶', f'cl:{(page + 1) % pages}')])
    cart = ctx.store.cart(user_id or message.from_user.id)
    if cart['lines']:
        rows.append([('🛒 Открыть корзину', 'cart')])
    await answer(message, '🌸 <b>Каталог MuzFlowers Выхино</b>\nВыберите букет — покажу фото, состав и варианты.', buttons(rows))


async def show_product(call: CallbackQuery, ctx: IntegratedContext, product_id: int, state: FSMContext) -> None:
    data = await ctx.bootstrap()
    product = product_by_id(data, product_id)
    if product is None:
        await call.answer('Этот букет больше не продаётся.', show_alert=True)
        return
    saved = await state.get_data()
    variant_id = saved.get(f'variant:{product_id}', (product['variants'][0]['id'] if product['variants'] else 0))
    variant = variant_by_id(product, variant_id)
    if variant:
        variant_id = variant['id']
    price = (variant or product)['price']
    text = f"<b>{esc(product['name'])}</b> · <b>{rub(price)}</b>\n\n{esc(product['tagline'])}"
    if product['description']:
        text += f"\n\n{esc(product['description'])}"
    if product['illustration']:
        text += '\n\n<i>Показана иллюстрация, не фото готового букета.</i>'
    if not product['available']:
        text += f"\n\n⚠️ {esc(product['unavailable_reason'])}"
    rows = []
    if len(product['variants']) > 1:
        rows.append([(v['name'], f"v:{product_id}:{v['id']}") for v in product['variants']])
    if product['available']:
        rows.append([('🛒 Добавить в корзину', f'a:{product_id}:{variant_id}')])
    rows.append([('🌸 Каталог', 'catalog'), ('🛒 Корзина', 'cart')])
    markup = buttons(rows)
    if call.message and product['image'].lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
        if call.message.photo:
            await edit(call, text, markup)
        else:
            await call.message.answer_photo(URLInputFile(product['image']), caption=text, reply_markup=markup)
    else:
        await edit(call, text, markup)


async def show_cart(message: Message, ctx: IntegratedContext, extra: dict | None = None, user_id: int | None = None) -> None:
    data = await ctx.bootstrap()
    user_id = user_id or message.from_user.id
    cart = ctx.store.cart(user_id)
    if not cart['lines']:
        await answer(message, '🛒 <b>Корзина пуста</b>\nВыберите букет в каталоге 🌸', buttons([[('🌸 Каталог', 'catalog')]]))
        return
    quote = await get_quote(ctx, user_id, extra)
    lines = ['🛒 <b>Ваша корзина</b>', '', *line_names(data, cart['lines'])]
    for addon in cart['addons']:
        item = next((a for a in data['addons'] if a['id'] == addon['id']), None)
        if item:
            lines.append(f"• {esc(item['name'])} — {rub(item['price'])}")
    if quote['discount']:
        lines.append(f'Скидка: −{rub(quote["discount"])}')
    if quote['delivery']:
        lines.append(f'Доставка: {rub(quote["delivery"])}')
    if quote['certificate_amount']:
        lines.append(f'Сертификат: −{rub(quote["certificate_amount"])}')
    lines.append(f'<b>Итого: {rub(quote["total"])}</b>')
    if quote['promo_error']:
        lines.append(f'⚠️ {esc(quote["promo_error"])}')
    if quote['certificate_error']:
        lines.append(f'⚠️ {esc(quote["certificate_error"])}')
    rows = []
    for index, line in enumerate(cart['lines']):
        product = product_by_id(data, line['product'])
        name = product['name'][:14] if product else 'Позиция'
        rows.append([('−', f'q:{index}:-1'), (f'{name} × {line["qty"]}', 'noop'), ('+', f'q:{index}:1')])
    rows += [[('🎵 Дополнения', 'addons'), ('🏷 Промокод / сертификат', 'code')],
             [('✅ Оформить заказ', 'checkout')], [('🌸 Добавить ещё', 'catalog'), ('🧹 Очистить', 'clear')]]
    await answer(message, '\n'.join(lines), buttons(rows))


async def ask_method(message: Message, ctx: IntegratedContext) -> None:
    shop = (await ctx.bootstrap())['shop']
    rows = []
    if shop['delivery_enabled']:
        rows.append([('🚚 Доставка', 'm:delivery')])
    rows.append([('🛍 Самовывоз', 'm:pickup')])
    await answer(message, f"📍 <b>Как получите заказ?</b>\nСамовывоз: {esc(shop['address'])}\n{esc(shop['hours'])}", buttons(rows))


async def ask_date(message: Message, ctx: IntegratedContext) -> None:
    today = date.today()
    rows = []
    for offset in range(4):
        day = today + timedelta(days=offset)
        label = 'Сегодня' if offset == 0 else 'Завтра' if offset == 1 else day.strftime('%d.%m')
        rows.append([(label, f'd:{day.isoformat()}')])
    await answer(message, '🗓 <b>На какую дату?</b>', buttons(rows))


async def ask_legal(message: Message, ctx: IntegratedContext) -> None:
    shop = (await ctx.bootstrap())['shop']
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📄 Согласие на обработку данных', url=shop['consent_url'])],
        [InlineKeyboardButton(text='📄 Публичная оферта', url=shop['offer_url'])],
        [InlineKeyboardButton(text='✅ Прочитал(а) и принимаю', callback_data='legal')],
    ])
    await answer(message, 'Перед заказом откройте документы и подтвердите согласие. Это обязательный шаг.', markup)


async def show_summary(message: Message, ctx: IntegratedContext, state: FSMContext, user_id: int | None = None) -> None:
    user_id = user_id or message.from_user.id
    data = await state.get_data()
    quote = await get_quote(ctx, user_id, {'date': data['date'], 'receive_method': data['receive_method']})
    await state.update_data(expected_total=quote['total'])
    cart = ctx.store.cart(user_id)
    catalog = await ctx.bootstrap()
    lines = ['🧾 <b>Проверьте заказ</b>', '', *line_names(catalog, cart['lines']),
             f"🗓 {esc(data['date'])}, {esc(data['time_slot'])}",
             f"👤 {esc(data['name'])}, {esc(data['phone'])}",
             f"📍 {'Доставка' if data['receive_method'] == 'delivery' else 'Самовывоз'}", '',
             f'<b>К оплате: {rub(quote["total"])}</b>']
    if data.get('comment'):
        lines.append(f"💌 {esc(data['comment'])}")
    rows = [[(method['label'], f"pay:{method['value']}")] for method in quote['payment_methods']]
    rows += [[('💌 Открытка / комментарий', 'comment')], [('⬅️ Изменить дату', 'change_date')]]
    await answer(message, '\n'.join(lines), buttons(rows))


async def order_detail(call: CallbackQuery, ctx: IntegratedContext, order_id: int) -> None:
    result = await ctx.client.post('orders/detail', {'telegram_user_id': call.from_user.id, 'order': order_id})
    order = result['order']
    lines = [f"📦 <b>Заказ №{order['id']}</b>", f"Статус: {esc(order['status'])}",
             f"🗓 {esc(order['date'])}, {esc(order['time'])}", f"📍 {esc(order['address'])}",
             f"💰 {rub(order['total'])} · {esc(order['payment_status'])}"]
    lines += [f"• {esc(item['name'])} × {item['qty']}" for item in order['items']]
    if order.get('certificate'):
        cert = order['certificate']
        lines += ['', f"🎁 <b>{cert['code']}</b>", f"Остаток: {rub(cert['balance'])} · до {cert['expires_at']}"]
    rows = []
    if order['pay_url'] and order['payment_status'] == 'pending':
        rows.append([('💳 Оплатить', f"paylink:{order_id}")])
    if order['status'] == 'new' and order['payment_status'] != 'paid' and order['kind'] == 'products':
        rows.append([('❌ Отменить заказ', f"oc:{order_id}")])
    if order['status'] == 'done' and order['kind'] == 'products':
        rows.append([('⭐ Оставить отзыв', f"rw:{order_id}")])
    if order['kind'] == 'products':
        rows.append([('🔁 Повторить', f"or:{order_id}")])
    rows.append([('🧾 Мои заказы', 'orders')])
    markup = buttons(rows)
    if order.get('delivery_photo'):
        await call.message.answer_photo(URLInputFile(order['delivery_photo']), caption='Фото вашего букета перед выдачей или доставкой')
    await edit(call, '\n'.join(lines), markup)


@router.message(CommandStart())
async def start(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    await state.clear()
    shop = (await ctx.bootstrap())['shop']
    await answer(message, f"🌸 <b>{esc(shop['name'])} · Выхино</b>\n\nБукеты с доставкой и самовывозом. Здесь те же цены и наличие, что на сайте.\n\nВыберите действие:", MENU)


@router.message(Command('myid'))
async def my_id(message: Message) -> None:
    await answer(message, f'Ваш Telegram ID: <code>{message.from_user.id}</code>')


@router.message(F.text == '🌸 Каталог')
@router.message(Command('catalog'))
async def catalog(message: Message, ctx: IntegratedContext) -> None:
    await show_catalog(message, ctx)


@router.callback_query(F.data == 'catalog')
async def catalog_callback(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await call.answer()
    await call.message.delete()
    await show_catalog(call.message, ctx, user_id=call.from_user.id)


@router.callback_query(F.data.startswith('cl:'))
async def catalog_page(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await call.answer()
    await call.message.delete()
    await show_catalog(call.message, ctx, int(call.data.split(':')[1]), call.from_user.id)


@router.callback_query(F.data.startswith('p:'))
async def product(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    await call.answer()
    await show_product(call, ctx, int(call.data.split(':')[1]), state)


@router.callback_query(F.data.startswith('v:'))
async def variant(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    _, product_id, variant_id = call.data.split(':')
    await state.update_data(**{f'variant:{int(product_id)}': int(variant_id)})
    await call.answer('Вариант выбран')
    await show_product(call, ctx, int(product_id), state)


@router.callback_query(F.data.startswith('a:'))
async def add(call: CallbackQuery, ctx: IntegratedContext) -> None:
    _, product_id, variant_id = call.data.split(':')
    try:
        ctx.store.add_line(call.from_user.id, int(product_id), int(variant_id))
    except ValueError as exc:
        await call.answer(str(exc), show_alert=True)
        return
    await call.answer('Добавлено в корзину ✅')
    await show_cart(call.message, ctx, user_id=call.from_user.id)


@router.message(F.text == '🛒 Корзина')
@router.message(Command('cart'))
async def cart(message: Message, ctx: IntegratedContext) -> None:
    await show_cart(message, ctx)


@router.callback_query(F.data == 'cart')
async def cart_callback(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await call.answer()
    await show_cart(call.message, ctx, user_id=call.from_user.id)


@router.callback_query(F.data.startswith('q:'))
async def quantity(call: CallbackQuery, ctx: IntegratedContext) -> None:
    _, index, delta = call.data.split(':')
    ctx.store.change_line(call.from_user.id, int(index), int(delta))
    await call.answer()
    await show_cart(call.message, ctx, user_id=call.from_user.id)


@router.callback_query(F.data == 'clear')
async def clear(call: CallbackQuery, ctx: IntegratedContext) -> None:
    ctx.store.clear_cart(call.from_user.id)
    await call.answer('Корзина очищена')
    await show_cart(call.message, ctx, user_id=call.from_user.id)


@router.callback_query(F.data == 'addons')
async def addons(call: CallbackQuery, ctx: IntegratedContext) -> None:
    data = await ctx.bootstrap()
    cart = ctx.store.cart(call.from_user.id)
    chosen = {addon['id'] for addon in cart['addons']}
    rows = [[(('✅ ' if addon['id'] in chosen else '➕ ') + addon['name'], f"ad:{addon['id']}")] for addon in data['addons']]
    rows.append([('🛒 Корзина', 'cart')])
    await edit(call, 'Выберите дополнения к заказу:', buttons(rows))


@router.callback_query(F.data.startswith('ad:'))
async def addon(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    addon_id = int(call.data.split(':')[1])
    data = await ctx.bootstrap()
    addon = next(item for item in data['addons'] if item['id'] == addon_id)
    cart = ctx.store.cart(call.from_user.id)
    if addon['note_required'] and addon_id not in {item['id'] for item in cart['addons']}:
        await state.set_state(Flow.addon_note)
        await state.update_data(addon_id=addon_id)
        await answer(call.message, esc(addon['note_label'] or 'Напишите пожелание:'))
        return
    ctx.store.toggle_addon(call.from_user.id, addon_id)
    await call.answer()
    await show_cart(call.message, ctx, user_id=call.from_user.id)


@router.message(Flow.addon_note, F.text)
async def addon_note(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    data = await state.get_data()
    ctx.store.toggle_addon(message.from_user.id, data['addon_id'], message.text.strip())
    await state.clear()
    await show_cart(message, ctx)


@router.callback_query(F.data == 'code')
async def code(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.code)
    await answer(call.message, 'Введите промокод или код сертификата вида ABCD-EFGH-JKLM:')


@router.message(Flow.code, F.text)
async def save_code(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    cart = ctx.store.cart(message.from_user.id)
    value = message.text.strip()
    if len(value.replace('-', '').replace(' ', '')) == 12:
        cart['certificate_code'] = value
        cart['promo'] = ''
    else:
        cart['promo'] = value
        cart['certificate_code'] = ''
    ctx.store.save_cart(message.from_user.id, cart)
    await state.clear()
    await show_cart(message, ctx)


@router.callback_query(F.data == 'checkout')
async def checkout(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    contact = ctx.store.contact(call.from_user.id)
    if contact['name'] and contact['phone']:
        await state.update_data(name=contact['name'], phone=contact['phone'])
        await ask_method(call.message, ctx)
        return
    await state.set_state(Flow.contact)
    markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='📞 Поделиться номером', request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
    await answer(call.message, 'Поделитесь номером или напишите имя и телефон через пробел:', markup)


@router.message(Flow.contact, F.contact | F.text)
async def contact(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    if message.contact:
        phone = phone_from_input(message.contact.phone_number)
        name = message.contact.first_name or message.from_user.first_name
    else:
        phone = phone_from_input(message.text)
        name = ' '.join(part for part in message.text.split() if not any(char.isdigit() for char in part))
        if not name:
            await answer(message, 'Добавьте имя, например: Анна +7 900 123-45-67')
            return
    if not phone:
        await answer(message, 'Не удалось распознать телефон. Попробуйте ещё раз.')
        return
    ctx.store.save_contact(message.from_user.id, name[:100], phone)
    data = await state.get_data()
    if data.get('certificate_amount'):
        await state.clear()
        await purchase_certificate(message, ctx, data['certificate_amount'])
        return
    await state.update_data(name=name[:100], phone=phone)
    await state.set_state(None)
    await ask_method(message, ctx)


@router.callback_query(F.data.startswith('m:'))
async def method(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    method_value = call.data.split(':')[1]
    cart = ctx.store.cart(call.from_user.id)
    cart['receive_method'] = method_value
    ctx.store.save_cart(call.from_user.id, cart)
    await state.update_data(receive_method=method_value)
    if method_value == 'delivery':
        await state.set_state(Flow.address)
        await answer(call.message, 'Укажите адрес доставки: улица, дом, квартира. Можно добавить подъезд и домофон.')
    else:
        await state.update_data(shop=(await ctx.bootstrap())['shop']['shop_id'], address='')
        await ask_date(call.message, ctx)


@router.message(Flow.address, F.text)
async def address(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    await state.update_data(address=message.text.strip())
    await state.set_state(None)
    await ask_date(message, ctx)


@router.callback_query(F.data.startswith('d:'))
@router.callback_query(F.data == 'change_date')
async def choose_date(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    if call.data == 'change_date':
        await ask_date(call.message, ctx)
        return
    day = call.data.split(':')[1]
    data = await state.get_data()
    result = await ctx.client.post('availability', {'date': day, 'receive_method': data['receive_method']})
    if not result['ok']:
        await call.answer(result['problem'], show_alert=True)
        return
    await state.update_data(date=day)
    rows = [[(option['label'], f"t:{option['value']}")] for option in result['options']]
    await edit(call, 'Выберите удобное время:', buttons(rows))


@router.callback_query(F.data.startswith('t:'))
async def time_slot(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    await state.update_data(time_slot=call.data.split(':', 1)[1])
    data = await state.get_data()
    if data['receive_method'] == 'delivery':
        await edit(call, 'Заказ для вас?', buttons([[('Для меня', 'r:skip'), ('Другой получатель', 'r:other')]]))
    else:
        await ask_legal(call.message, ctx)


@router.callback_query(F.data.startswith('r:'))
async def recipient(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    if call.data == 'r:skip':
        await state.update_data(other_recipient=False, recipient_name='', recipient_phone='')
        await ask_legal(call.message, ctx)
    else:
        await state.set_state(Flow.recipient_name)
        await answer(call.message, 'Имя получателя:')


@router.message(Flow.recipient_name, F.text)
async def recipient_name(message: Message, state: FSMContext) -> None:
    await state.update_data(other_recipient=True, recipient_name=message.text.strip())
    await state.set_state(Flow.recipient_phone)
    await answer(message, 'Телефон получателя:')


@router.message(Flow.recipient_phone, F.text)
async def recipient_phone(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    phone = phone_from_input(message.text)
    if not phone:
        await answer(message, 'Проверьте телефон получателя.')
        return
    await state.update_data(recipient_phone=phone)
    await ask_legal(message, ctx)


@router.callback_query(F.data == 'legal')
async def legal(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    await show_summary(call.message, ctx, state, call.from_user.id)


@router.callback_query(F.data == 'comment')
async def comment(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.comment)
    await answer(call.message, 'Напишите текст открытки или пожелание, либо «пропустить»:')


@router.message(Flow.comment, F.text)
async def comment_text(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    value = '' if message.text.lower() == 'пропустить' else message.text.strip()
    await state.update_data(comment=value)
    await show_summary(message, ctx, state)


@router.callback_query(F.data.startswith('pay:'))
async def pay(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    method_value = call.data.split(':')[1]
    data = await state.get_data()
    cart = ctx.store.cart(call.from_user.id)
    required = ('name', 'phone', 'receive_method', 'date', 'time_slot', 'expected_total')
    if not cart['lines'] or any(key not in data for key in required):
        await call.answer('Этот заказ уже оформлен или оформление устарело. Проверьте «Мои заказы».', show_alert=True)
        return
    payload = {
        **cart, **data, 'telegram_user_id': call.from_user.id, 'payment_method': method_value,
        'consent_pd': True, 'consent_offer': True, 'expected_total': data.get('expected_total', -1),
    }
    try:
        result = await ctx.client.post('orders', payload, idempotency_key=ctx.store.operation_key(call.from_user.id, 'order'))
    except ShopApiError as exc:
        await call.answer(str(exc)[:180], show_alert=True)
        return
    ctx.store.clear_cart(call.from_user.id)
    ctx.store.clear_operation(call.from_user.id, 'order')
    await state.clear()
    order = result.get('order', result)
    rows = [[('🧾 Открыть заказ', f"o:{order['id']}")]]
    if order.get('pay_url'):
        rows.insert(0, [('💳 Оплатить', f"paylink:{order['id']}")])
    await answer(call.message, f"✅ <b>Заказ №{order['id']} принят</b>\nСумма: {rub(order['total'])}\n{esc(result.get('payment_error', ''))}", buttons(rows))


@router.callback_query(F.data.startswith('paylink:'))
async def payment_link(call: CallbackQuery, ctx: IntegratedContext) -> None:
    order_id = int(call.data.split(':')[1])
    result = await ctx.client.post('orders/payment', {'telegram_user_id': call.from_user.id, 'order': order_id})
    order = result['order']
    if order['pay_url']:
        await answer(call.message, 'Оплата на защищённой странице банка. После оплаты вернитесь сюда и откройте заказ.',
                     InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='💳 Оплатить', url=order['pay_url'])],
                                                          [InlineKeyboardButton(text='🔄 Проверить заказ', callback_data=f'o:{order_id}')]]))
    else:
        await order_detail(call, ctx, order_id)


@router.message(F.text == '🧾 Мои заказы')
@router.message(Command('orders'))
async def orders(message: Message, ctx: IntegratedContext, user_id: int | None = None) -> None:
    result = await ctx.client.post('orders/list', {'telegram_user_id': user_id or message.from_user.id})
    if not result['orders']:
        await answer(message, 'Пока заказов нет. Выберите первый букет 🌸', buttons([[('🌸 Каталог', 'catalog')]]))
        return
    rows = [[(f"№{order['id']} · {order['date']} · {rub(order['total'])}", f"o:{order['id']}")] for order in result['orders'][:10]]
    await answer(message, '🧾 <b>Ваши заказы</b>', buttons(rows))


@router.callback_query(F.data == 'orders')
async def orders_callback(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await orders(call.message, ctx, call.from_user.id)


@router.callback_query(F.data.startswith('o:'))
async def open_order(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await call.answer()
    await order_detail(call, ctx, int(call.data.split(':')[1]))


@router.callback_query(F.data.startswith('oc:'))
async def cancel_order(call: CallbackQuery, ctx: IntegratedContext) -> None:
    order_id = int(call.data.split(':')[1])
    result = await ctx.client.post('orders/cancel', {'telegram_user_id': call.from_user.id, 'order': order_id},
                                   idempotency_key=ctx.store.operation_key(call.from_user.id, f'cancel-{order_id}'))
    await call.answer('Заказ отменён')
    await order_detail(call, ctx, result['order']['id'])


@router.callback_query(F.data.startswith('or:'))
async def repeat_order(call: CallbackQuery, ctx: IntegratedContext) -> None:
    order_id = int(call.data.split(':')[1])
    result = await ctx.client.post('orders/detail', {'telegram_user_id': call.from_user.id, 'order': order_id})
    for item in result['order']['items']:
        ctx.store.add_line(call.from_user.id, item['product_id'], item['variant_id'] or 0, item['qty'])
    await call.answer('Товары добавлены в корзину')
    await show_cart(call.message, ctx, user_id=call.from_user.id)


@router.message(F.text == '🎁 Сертификат')
async def certificates(message: Message, ctx: IntegratedContext) -> None:
    shop = (await ctx.bootstrap())['shop']
    rows = [[(f'{rub(amount)}', f'ca:{amount}')] for amount in shop['certificate_amounts']]
    rows += [[('Другая сумма', 'cother')], [('Мои сертификаты', 'cmine')], [('Проверить код', 'ccheck')]]
    await answer(message, '🎁 <b>Подарочный сертификат</b>\nМожно оплатить заказ полностью или частично — на сайте и в боте.', buttons(rows))


@router.callback_query(F.data == 'cmine')
async def my_certificates(call: CallbackQuery, ctx: IntegratedContext) -> None:
    result = await ctx.client.post('certificates/list', {'telegram_user_id': call.from_user.id})
    if not result['certificates']:
        await call.answer('У вас пока нет сертификатов', show_alert=True)
        return
    lines = ['🎁 <b>Ваши сертификаты</b>']
    for cert in result['certificates']:
        lines.append(f"<code>{cert['code']}</code> · {rub(cert['balance'])} · до {cert['expires_at']}")
    await edit(call, '\n'.join(lines), buttons([[('🎁 Сертификаты', 'certificates')]]))


@router.callback_query(F.data == 'certificates')
async def certificates_callback(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await certificates(call.message, ctx)


@router.callback_query(F.data.startswith('ca:'))
async def certificate_amount(call: CallbackQuery, ctx: IntegratedContext) -> None:
    amount = int(call.data.split(':')[1])
    shop = (await ctx.bootstrap())['shop']
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📄 Согласие', url=shop['consent_url']), InlineKeyboardButton(text='📄 Оферта', url=shop['offer_url'])],
        [InlineKeyboardButton(text=f'✅ Принимаю и перейти к оплате {rub(amount)}', callback_data=f'cb:{amount}')],
    ])
    await edit(call, 'Для покупки сертификата подтвердите документы:', markup)


@router.callback_query(F.data == 'cother')
async def certificate_other(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.certificate_amount)
    await answer(call.message, 'Введите сумму от 500 до 30 000 ₽:')


@router.message(Flow.certificate_amount, F.text)
async def certificate_custom(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    try:
        amount = int(message.text)
    except ValueError:
        amount = 0
    if not 500 <= amount <= 30000:
        await answer(message, 'Нужна сумма от 500 до 30 000 ₽.')
        return
    await state.clear()
    shop = (await ctx.bootstrap())['shop']
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📄 Согласие', url=shop['consent_url']), InlineKeyboardButton(text='📄 Оферта', url=shop['offer_url'])],
        [InlineKeyboardButton(text=f'✅ Принимаю и перейти к оплате {rub(amount)}', callback_data=f'cb:{amount}')],
    ])
    await answer(message, 'Подтвердите документы для покупки:', markup)


@router.callback_query(F.data.startswith('cb:'))
async def certificate_buy(call: CallbackQuery, state: FSMContext, ctx: IntegratedContext) -> None:
    amount = int(call.data.split(':')[1])
    contact = ctx.store.contact(call.from_user.id)
    if not contact['name'] or not contact['phone']:
        await state.set_state(Flow.contact)
        await state.update_data(certificate_amount=amount)
        markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='📞 Поделиться номером', request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await answer(call.message, 'Для чека и связи по сертификату поделитесь номером или напишите имя и телефон:', markup)
        return
    await purchase_certificate(call.message, ctx, amount)


async def purchase_certificate(message: Message, ctx: IntegratedContext, amount: int) -> None:
    contact = ctx.store.contact(message.from_user.id)
    result = await ctx.client.post('certificates/purchase', {
        'telegram_user_id': message.from_user.id, 'amount': amount, **contact,
        'consent_pd': True, 'consent_offer': True,
    }, idempotency_key=ctx.store.operation_key(message.from_user.id, f'certificate-{amount}'))
    ctx.store.clear_operation(message.from_user.id, f'certificate-{amount}')
    order = result['order']
    rows = [[('🧾 Открыть сертификат', f"o:{order['id']}")]]
    if order.get('pay_url'):
        rows.insert(0, [('💳 Оплатить', f"paylink:{order['id']}")])
    await answer(message, f'Заказ на сертификат №{order["id"]} создан. После оплаты код появится в заказе.', buttons(rows))


@router.callback_query(F.data == 'ccheck')
async def certificate_check_start(call: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(Flow.certificate_check)
    await answer(call.message, 'Введите код сертификата:')


@router.message(Flow.certificate_check, F.text)
async def certificate_check_text(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    try:
        result = await ctx.client.post('certificates/check', {'telegram_user_id': message.from_user.id, 'code': message.text})
    except ShopApiError as exc:
        await answer(message, f'⚠️ {esc(str(exc))}')
        return
    cert = result['certificate']
    await state.clear()
    await answer(message, f"🎁 <code>{cert['code']}</code>\nБаланс: <b>{rub(cert['balance'])}</b>\nДействует до {cert['expires_at']}")


@router.message(F.text == '💬 Менеджер')
async def manager(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    contact = ctx.store.contact(message.from_user.id)
    if not contact['phone']:
        await state.set_state(Flow.manager_contact)
        markup = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='📞 Поделиться номером', request_contact=True)]], resize_keyboard=True, one_time_keyboard=True)
        await answer(message, 'Чтобы менеджер мог ответить, поделитесь номером или напишите его:', markup)
    else:
        await state.set_state(Flow.manager_text)
        await answer(message, 'Напишите вопрос или пришлите фото букета, который нравится. Менеджер ответит в рабочее время.')


@router.message(Flow.manager_contact, F.contact | F.text)
async def manager_contact(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    phone = phone_from_input(raw)
    if not phone:
        await answer(message, 'Проверьте номер телефона.')
        return
    ctx.store.save_contact(message.from_user.id, message.from_user.first_name or 'Клиент', phone)
    await state.set_state(Flow.manager_text)
    await answer(message, 'Спасибо! Теперь напишите ваш вопрос:')


@router.message(Flow.manager_text, F.text | F.photo)
async def manager_text(message: Message, state: FSMContext, ctx: IntegratedContext, bot: Bot) -> None:
    contact = ctx.store.contact(message.from_user.id)
    text = message.caption or message.text or 'Клиент прислал фото букета'
    result = await ctx.client.post('leads', {
        'telegram_user_id': message.from_user.id, **contact, 'message': text, 'consent_pd': True,
    })
    if message.photo:
        await notify.copy_to_staff(bot, ctx, message.chat.id, [message.message_id])
    await state.clear()
    await answer(message, 'Спасибо! Обращение передано менеджеру. Ответим в рабочее время 🌸', MENU)


@router.callback_query(F.data == 'reviews')
async def reviews(call: CallbackQuery, ctx: IntegratedContext) -> None:
    result = await ctx.client.post('reviews/list', {})
    if not result['reviews']:
        await answer(call.message, 'Скоро здесь появятся проверенные отзывы покупателей.')
        return
    lines = ['⭐ <b>Отзывы покупателей</b>', '']
    for review in result['reviews'][:5]:
        lines.append(f"{'★' * review['rating']}\n{esc(review['text'])}\n— {esc(review['name'])}, {esc(review['source'])}\n")
    await edit(call, '\n'.join(lines))


@router.callback_query(F.data.startswith('rw:'))
async def review_start(call: CallbackQuery, state: FSMContext) -> None:
    order_id = int(call.data.split(':')[1])
    await state.update_data(review_order=order_id)
    await edit(call, 'Оцените заказ от 1 до 5:', buttons([[(str(value), f'rr:{order_id}:{value}') for value in range(1, 6)]]))


@router.callback_query(F.data.startswith('rr:'))
async def review_rating(call: CallbackQuery, state: FSMContext) -> None:
    _, order_id, rating = call.data.split(':')
    await state.update_data(review_order=int(order_id), review_rating=int(rating))
    await state.set_state(Flow.review_text)
    await answer(call.message, 'Напишите несколько слов о букете и сервисе:')


@router.message(Flow.review_text, F.text)
async def review_text(message: Message, state: FSMContext, ctx: IntegratedContext) -> None:
    data = await state.get_data()
    result = await ctx.client.post('reviews', {
        'telegram_user_id': message.from_user.id, 'order': data['review_order'], 'rating': data['review_rating'],
        'name': message.from_user.first_name or 'Покупатель', 'text': message.text.strip(),
    })
    await state.clear()
    await answer(message, result['message'])


@router.message(F.text == '🚚 Доставка')
async def delivery(message: Message, ctx: IntegratedContext) -> None:
    shop = (await ctx.bootstrap())['shop']
    lines = ['🚚 <b>Доставка и самовывоз</b>', '', f"Доставка: {rub(shop['delivery_cost'])}"]
    if shop['free_delivery_from']:
        lines.append(f"Бесплатно от {rub(shop['free_delivery_from'])}")
    lines += [f"Самовывоз: {esc(shop['address'])}", f"Скидка при самовывозе: {shop['pickup_discount_percent']}%",
              f"🕒 {esc(shop['hours'])}", f"📞 {esc(shop['phone'])}", f"✉️ {esc(shop['email'])}"]
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🗺 Яндекс Карты', url=shop['map_url'])],
        [InlineKeyboardButton(text='Telegram', url=shop['telegram']), InlineKeyboardButton(text='MAX', url=shop['max_url'])],
        [InlineKeyboardButton(text='⭐ Отзывы', callback_data='reviews')],
    ])
    await answer(message, '\n'.join(lines), markup)


@router.message(F.text == '👑 Панель')
@router.message(Command('admin'))
async def staff(message: Message, ctx: IntegratedContext, user_id: int | None = None) -> None:
    user_id = user_id or message.from_user.id
    if not ctx.is_admin(user_id):
        await answer(message, 'Этот раздел доступен только сотрудникам.')
        return
    result = await ctx.client.post('staff/orders', {'telegram_user_id': user_id})
    rows = [[(f"№{order['id']} · {order['date']} · {order['status']}", f"so:{order['id']}")] for order in result['orders'][:15]]
    rows.append([('📦 Наличие', 'stock')])
    await answer(message, '👑 <b>Панель Выхино</b>\nАктивные заказы:', buttons(rows))


@router.callback_query(F.data == 'stock')
async def stock(call: CallbackQuery, ctx: IntegratedContext) -> None:
    if not ctx.is_admin(call.from_user.id):
        await call.answer('Недостаточно прав', show_alert=True)
        return
    data = await ctx.bootstrap(force=True)
    rows = [[((f"✅ {p['name']}" if p['in_stock'] else f"⛔ {p['name']}"), f"stk:{p['id']}")] for p in data['products'][:25]]
    rows.append([('👑 Панель', 'staff')])
    await edit(call, 'Нажмите на товар, чтобы изменить наличие:', buttons(rows))


@router.callback_query(F.data.startswith('stk:'))
async def stock_toggle(call: CallbackQuery, ctx: IntegratedContext) -> None:
    if not ctx.is_admin(call.from_user.id):
        await call.answer('Недостаточно прав', show_alert=True)
        return
    product_id = int(call.data.split(':')[1])
    data = await ctx.bootstrap()
    product = product_by_id(data, product_id)
    result = await ctx.client.post('staff/stock', {
        'telegram_user_id': call.from_user.id, 'product': product_id, 'in_stock': not product['in_stock'],
    }, idempotency_key=ctx.store.operation_key(call.from_user.id, f'stock-{product_id}-{time.time_ns()}'))
    await call.answer('Наличие обновлено')
    await ctx.bootstrap(force=True)
    await stock(call, ctx)


@router.callback_query(F.data == 'staff')
async def staff_callback(call: CallbackQuery, ctx: IntegratedContext) -> None:
    await staff(call.message, ctx, call.from_user.id)


@router.callback_query(F.data.startswith('so:'))
async def staff_order(call: CallbackQuery, ctx: IntegratedContext) -> None:
    if not ctx.is_admin(call.from_user.id):
        await call.answer('Недостаточно прав', show_alert=True)
        return
    result = await ctx.client.post('staff/orders', {'telegram_user_id': call.from_user.id})
    order_id = int(call.data.split(':')[1])
    order = next((item for item in result['orders'] if item['id'] == order_id), None)
    if order is None:
        await call.answer('Заказ уже закрыт или не найден', show_alert=True)
        return
    next_status = {'new': 'confirmed', 'confirmed': 'ready', 'ready': 'delivering' if order['method'] == 'delivery' else 'done',
                   'delivering': 'done'}.get(order['status'])
    rows = []
    if next_status:
        rows.append([(f'➡️ {next_status}', f"ss:{order_id}:{next_status}")])
    if order['payment_status'] != 'paid':
        rows.append([('💳 Оплата получена', f"sp:{order_id}")])
    rows.append([('👑 Панель', 'staff')])
    text = '\n'.join([
        f"📦 <b>Заказ №{order['id']}</b> · {order['status']}", f"🗓 {order['date']} · {order['time']}",
        f"👤 {esc(order['name'])}, {esc(order['phone'])}", f"📍 {esc(order['address'])}",
        *[f"• {esc(item['name'])} × {item['qty']}" for item in order['items']],
        f"💰 <b>{rub(order['total'])}</b> · {order['payment_status']}",
    ])
    await edit(call, text, buttons(rows))


@router.callback_query(F.data.startswith('ss:'))
async def staff_status(call: CallbackQuery, ctx: IntegratedContext) -> None:
    if not ctx.is_admin(call.from_user.id):
        await call.answer('Недостаточно прав', show_alert=True)
        return
    _, order_id, status = call.data.split(':')
    result = await ctx.client.post('staff/status', {'telegram_user_id': call.from_user.id, 'order': int(order_id), 'status': status},
                                   idempotency_key=ctx.store.operation_key(call.from_user.id, f'staff-{order_id}-{status}-{time.time_ns()}'))
    await call.answer('Статус обновлён')
    await edit(call, f"✅ Заказ №{order_id}: {status}\nКлиент видит обновление по ссылке на заказ.", buttons([[('👑 Панель', 'staff')]]))


@router.callback_query(F.data.startswith('sp:'))
async def staff_paid(call: CallbackQuery, ctx: IntegratedContext) -> None:
    if not ctx.is_admin(call.from_user.id):
        await call.answer('Недостаточно прав', show_alert=True)
        return
    order_id = int(call.data.split(':')[1])
    await ctx.client.post('staff/paid', {'telegram_user_id': call.from_user.id, 'order': order_id},
                          idempotency_key=ctx.store.operation_key(call.from_user.id, f'paid-{order_id}-{time.time_ns()}'))
    await call.answer('Оплата отмечена')
    await edit(call, f'✅ Оплата заказа №{order_id} отмечена.', buttons([[('👑 Панель', 'staff')]]))


@router.callback_query(F.data == 'noop')
async def noop(call: CallbackQuery) -> None:
    await call.answer()
