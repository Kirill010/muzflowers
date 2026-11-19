from __future__ import annotations

import hashlib
import hmac
import unittest

from aiohttp import web
from aiohttp.test_utils import TestServer

from flowerbot.config import ConfigError
from flowerbot.shop_api import ShopApiError, ShopClient

from .helpers import VALID_TOKEN, make_settings

SECRET = 'test-secret-0123456789abcdef0123456789'


class ShopClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.headers = {}

        async def handler(request):
            self.headers = request.headers
            body = await request.read()
            signed = self.headers['X-Muz-Timestamp'].encode() + b'.' + request.path.encode() + b'.' + body
            expected = hmac.new(SECRET.encode(), signed, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, self.headers['X-Muz-Signature']):
                return web.json_response({'ok': False, 'error': 'bad signature'}, status=403)
            if request.path.endswith('error/'):
                return web.json_response({'ok': False, 'error': 'Проверьте данные'}, status=400)
            return web.json_response({'ok': True, 'received': True})

        self.server = TestServer(web.Application())
        self.server.app.router.add_post('/api/bot/v1/bootstrap/', handler)
        self.server.app.router.add_post('/api/bot/v1/error/', handler)
        await self.server.start_server()
        self.addCleanup(self.server.close)
        self.settings = make_settings(SHOP_API_URL=str(self.server.make_url('/api/bot/v1')), SHOP_API_SECRET=SECRET)

    async def test_signature_path_and_idempotency_header(self):
        client = ShopClient(self.settings)
        self.addCleanup(client.close)
        result = await client.post('bootstrap', {'telegram_user_id': 123}, idempotency_key='operation-123')
        self.assertTrue(result['received'])
        self.assertEqual(self.headers['X-Idempotency-Key'], 'operation-123')
        self.assertNotIn(SECRET, str(self.headers))

    async def test_api_error_is_human_readable(self):
        client = ShopClient(self.settings)
        self.addCleanup(client.close)
        with self.assertRaises(ShopApiError) as caught:
            await client.post('error', {})
        self.assertEqual((str(caught.exception), caught.exception.status), ('Проверьте данные', 400))


class IntegratedSettingsTests(unittest.TestCase):
    def test_requires_url_and_secret_together(self):
        with self.assertRaises(ConfigError):
            make_settings(SHOP_API_URL='https://shop.example/api/bot/v1')
        with self.assertRaises(ConfigError):
            make_settings(SHOP_API_SECRET=SECRET)

    def test_integrated_bot_cannot_have_own_bank_keys(self):
        with self.assertRaises(ConfigError):
            make_settings(SHOP_API_URL='https://shop.example/api/bot/v1', SHOP_API_SECRET=SECRET,
                          YOOKASSA_SHOP_ID='123456', YOOKASSA_SECRET_KEY='test_' + 'A' * 30)

    def test_integrated_mode(self):
        settings = make_settings(SHOP_API_URL='https://shop.example/api/bot/v1', SHOP_API_SECRET=SECRET)
        self.assertTrue(settings.integrated)
        self.assertFalse(settings.yookassa_enabled)
