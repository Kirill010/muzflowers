"""Публикация версии юридических текстов и доказательственный журнал акцептов."""
from .models import LegalAcceptance
from .throttle import client_ip

DOCUMENT_VERSION = '1.0'
DOCUMENT_DATE = '17.11.2026'


def record_acceptance(request, kind, *, reference='', contact='', user=None, action='accepted'):
    """Сохраняет минимальные сведения, необходимые для доказательства конкретного выбора пользователя."""
    user = user if user is not None and user.is_authenticated else None
    return LegalAcceptance.objects.create(
        kind=kind, action=action, version=DOCUMENT_VERSION, reference=reference[:80], contact=contact[:254],
        user=user, ip_address=client_ip(request)[:64], user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
    )
