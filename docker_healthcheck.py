import json
import os
import urllib.request
from urllib.parse import urlparse

host = urlparse(os.environ.get("SITE_URL", "")).hostname or "localhost"
request = urllib.request.Request(
    "http://127.0.0.1:8000/health/",
    headers={"Host": host, "X-Forwarded-Proto": "https"},
)
with urllib.request.urlopen(request, timeout=3) as response:
    if json.load(response) != {"ok": True}:
        raise RuntimeError("Проверка здоровья сайта вернула неожиданный ответ")
