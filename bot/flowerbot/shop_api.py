from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

import aiohttp

from .config import Settings


class ShopApiError(Exception):
    def __init__(self, message: str, status: int = 0, data: dict | None = None):
        super().__init__(message)
        self.status, self.data = status, data or {}


class ShopClient:
    def __init__(self, settings: Settings, *, session: aiohttp.ClientSession | None = None):
        self.base_url = settings.shop_api_url.rstrip('/')
        self.secret = settings.shop_api_secret.encode()
        self.session = session
        self._owns_session = session is None

    async def close(self) -> None:
        if self._owns_session and self.session and not self.session.closed:
            await self.session.close()

    async def post(self, endpoint: str, data: dict[str, Any], *, idempotency_key: str = '') -> dict[str, Any]:
        url = self.base_url + '/' + endpoint.strip('/') + '/'
        body = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()
        timestamp = str(int(time.time()))
        request_path = url.split('://', 1)[1]
        request_path = request_path[request_path.index('/'):]
        signed = timestamp.encode() + b'.' + request_path.encode() + b'.' + body
        signature = hmac.new(self.secret, signed, hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/json; charset=utf-8',
            'X-Muz-Timestamp': timestamp,
            'X-Muz-Nonce': secrets.token_urlsafe(18),
            'X-Muz-Signature': signature,
        }
        if idempotency_key:
            headers['X-Idempotency-Key'] = idempotency_key
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        try:
            async with self.session.post(url, data=body, headers=headers) as response:
                try:
                    result = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError) as exc:
                    raise ShopApiError('Сайт вернул непонятный ответ.', response.status) from exc
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise ShopApiError('Нет связи с магазином. Попробуйте ещё раз через минуту.') from exc
        if response.status >= 400 or not result.get('ok', True):
            raise ShopApiError(str(result.get('error') or 'Не удалось выполнить операцию.'), response.status, result)
        return result
