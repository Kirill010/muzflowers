from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

from shop.utils import normalize_phone


class EmailOrPhoneBackend(ModelBackend):
    """Войти можно по email, по телефону или по логину (так входит владелец в админку)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            username = kwargs.get(get_user_model().USERNAME_FIELD)
        if not username or password is None:
            return None
        user = self._find(str(username).strip())
        if user is None:
            get_user_model()().set_password(password)  # одинаковое время ответа: не выдаём, есть ли такой аккаунт
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    @staticmethod
    def _find(identifier):
        User = get_user_model()
        if '@' in identifier:
            return User.objects.filter(email__iexact=identifier).first() or User.objects.filter(username__iexact=identifier).first()
        phone = normalize_phone(identifier)
        if phone:
            from .models import Profile
            profile = Profile.objects.filter(phone=phone).select_related('user').first()
            if profile:
                return profile.user
        return User.objects.filter(username__iexact=identifier).first()
