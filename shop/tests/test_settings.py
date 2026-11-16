import os
from unittest import TestCase, mock

from django.core.exceptions import ImproperlyConfigured

from muzflowers import settings as conf


class DatabaseUrlTests(TestCase):
    def test_default_is_local_sqlite(self):
        with mock.patch.dict(os.environ, {"DJANGO_DB_URL": ""}):
            db = conf._database()
        self.assertEqual(db["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(db["NAME"], conf.DATA_DIR / "db.sqlite3")
        self.assertEqual(db["OPTIONS"]["transaction_mode"], "IMMEDIATE")

    def test_postgres_url_decodes_credentials_and_port(self):
        url = "postgresql://shop:p%40ss%2Fword@db.example:5433/muzflowers"
        with mock.patch.dict(os.environ, {"DJANGO_DB_URL": url}):
            db = conf._database()
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual((db["NAME"], db["USER"], db["PASSWORD"]), ("muzflowers", "shop", "p@ss/word"))
        self.assertEqual((db["HOST"], db["PORT"]), ("db.example", 5433))

    def test_unknown_database_scheme_is_rejected(self):
        with mock.patch.dict(os.environ, {"DJANGO_DB_URL": "mysql://user:pass@host/shop"}):
            with self.assertRaises(ImproperlyConfigured):
                conf._database()

    def test_production_drivers_are_installed(self):
        import psycopg  # noqa: F401
        import redis  # noqa: F401
