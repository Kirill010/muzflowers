from django.conf import settings
from django.core.cache import cache


def client_ip(request):
    header = settings.SHOP_CLIENT_IP_HEADER
    return (request.META.get(header, '') if header else '') or request.META.get('REMOTE_ADDR', '')


def throttled(request, scope, limit, window):
    """True, если с этого IP за `window` секунд было больше `limit` запросов."""
    key = f'mz:{scope}:{client_ip(request)}'
    cache.add(key, 0, window)
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.set(key, 1, window)
        return False
