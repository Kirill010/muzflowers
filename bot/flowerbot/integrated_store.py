from __future__ import annotations

import json
import secrets
from copy import deepcopy

from . import crm
from .db import Database

EMPTY_CART = {'lines': [], 'addons': [], 'promo': '', 'certificate_code': '', 'receive_method': 'pickup'}


class IntegratedStore:
    def __init__(self, db: Database):
        self.db = db

    def _get(self, key: str, default):
        raw = self.db.get_meta(key)
        try:
            return json.loads(raw) if raw else default
        except ValueError:
            return default

    def _set(self, key: str, value) -> None:
        self.db.set_meta(key, json.dumps(value, ensure_ascii=False, separators=(',', ':')))

    def cart(self, user_id: int) -> dict:
        value = self._get(f'integrated-cart:{user_id}', deepcopy(EMPTY_CART))
        if not isinstance(value, dict):
            return deepcopy(EMPTY_CART)
        result = deepcopy(EMPTY_CART)
        result.update(value)
        return result

    def save_cart(self, user_id: int, cart: dict) -> None:
        self._set(f'integrated-cart:{user_id}', cart)

    def clear_cart(self, user_id: int) -> None:
        self.save_cart(user_id, deepcopy(EMPTY_CART))

    def add_line(self, user_id: int, product: int, variant: int, qty: int = 1) -> None:
        cart = self.cart(user_id)
        for line in cart['lines']:
            if line['product'] == product and line['variant'] == variant:
                line['qty'] = min(50, line['qty'] + qty)
                break
        else:
            if len(cart['lines']) >= 30:
                raise ValueError('В корзине уже 30 разных позиций.')
            cart['lines'].append({'product': product, 'variant': variant, 'qty': min(50, qty)})
        self.save_cart(user_id, cart)

    def change_line(self, user_id: int, index: int, delta: int) -> None:
        cart = self.cart(user_id)
        if not 0 <= index < len(cart['lines']):
            return
        cart['lines'][index]['qty'] += delta
        if cart['lines'][index]['qty'] <= 0:
            cart['lines'].pop(index)
        else:
            cart['lines'][index]['qty'] = min(50, cart['lines'][index]['qty'])
        self.save_cart(user_id, cart)

    def toggle_addon(self, user_id: int, addon_id: int, note: str = '') -> bool:
        cart = self.cart(user_id)
        for addon in cart['addons']:
            if addon['id'] == addon_id:
                cart['addons'].remove(addon)
                self.save_cart(user_id, cart)
                return False
        cart['addons'].append({'id': addon_id, 'note': note[:200]})
        self.save_cart(user_id, cart)
        return True

    def contact(self, user_id: int) -> dict:
        row = crm.get_user(self.db, user_id)
        return {'name': row['name'] if row else '', 'phone': row['phone'] if row else ''}

    def save_contact(self, user_id: int, name: str, phone: str) -> None:
        crm.upsert_user(self.db, user_id, name, '', '')
        crm.save_contact(self.db, user_id, name=name, phone=phone)

    def operation_key(self, user_id: int, scope: str) -> str:
        key = f'integrated-operation:{scope}:{user_id}'
        value = self.db.get_meta(key)
        if not value:
            value = f'{scope}-{user_id}-{secrets.token_urlsafe(12)}'
            self.db.set_meta(key, value)
        return value

    def clear_operation(self, user_id: int, scope: str) -> None:
        self.db.set_meta(f'integrated-operation:{scope}:{user_id}', '')
