from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, PasswordResetForm, SetPasswordForm

from shop.forms import style_widgets
from shop.utils import normalize_phone

from .models import Profile, profile_of

User = get_user_model()
PHONE_ERROR = 'Введите телефон полностью — например, +7 900 123-45-67'


class LoginForm(AuthenticationForm):
    username = forms.CharField(label='Почта или телефон', widget=forms.TextInput(attrs={'autocomplete': 'username', 'autofocus': True}))
    password = forms.CharField(label='Пароль', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}))
    error_messages = {'invalid_login': 'Неверная почта (телефон) или пароль.', 'inactive': 'Этот аккаунт отключён.'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)


class _PasswordsMixin:
    """Два поля пароля с проверкой надёжности."""

    def _check_passwords(self, user):
        p1, p2 = self.cleaned_data.get('password1'), self.cleaned_data.get('password2')
        if p1 and p2:
            if p1 != p2:
                self.add_error('password2', 'Пароли не совпадают')
            else:
                try:
                    password_validation.validate_password(p2, user)
                except forms.ValidationError as exc:
                    self.add_error('password2', exc)


class RegisterForm(_PasswordsMixin, forms.Form):
    name = forms.CharField(label='Ваше имя', max_length=60, widget=forms.TextInput(attrs={'autocomplete': 'given-name'}))
    email = forms.EmailField(label='Почта', max_length=150, widget=forms.EmailInput(attrs={'autocomplete': 'email'}))
    phone = forms.CharField(label='Телефон (необязательно)', max_length=30, required=False, widget=forms.TextInput(attrs={'autocomplete': 'tel', 'inputmode': 'tel'}))
    password1 = forms.CharField(label='Пароль', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
                                help_text='Не короче 8 символов, не только цифры.')
    password2 = forms.CharField(label='Повторите пароль', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    consent = forms.BooleanField(error_messages={'required': 'Нужно согласие на обработку персональных данных'})
    website = forms.CharField(required=False)  # ловушка для роботов

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError('Такая почта уже зарегистрирована — попробуйте войти.')
        return email

    def clean_phone(self):
        raw = self.cleaned_data.get('phone', '')
        if not raw:
            return ''
        phone = normalize_phone(raw)
        if not phone:
            raise forms.ValidationError(PHONE_ERROR)
        if Profile.objects.filter(phone=phone).exists():
            raise forms.ValidationError('Этот телефон уже привязан к другому аккаунту.')
        return phone

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Не удалось отправить форму.')
        return ''

    def clean(self):
        data = super().clean()
        self._check_passwords(User(username=data.get('email', ''), email=data.get('email', ''), first_name=data.get('name', '')))
        return data

    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(username=d['email'], email=d['email'], password=d['password1'], first_name=d['name'])
        Profile.objects.create(user=user, phone=d.get('phone', ''))
        return user


class ProfileForm(forms.Form):
    name = forms.CharField(label='Имя', max_length=60)
    email = forms.EmailField(label='Почта', max_length=150)
    phone = forms.CharField(label='Телефон', max_length=30, required=False)
    address = forms.CharField(label='Адрес доставки по умолчанию', max_length=255, required=False)
    marketing_consent = forms.BooleanField(label='Хочу получать новости и акции', required=False)

    def __init__(self, *args, user, **kwargs):
        self.user = user
        profile = profile_of(user)
        initial = {'name': user.first_name, 'email': user.email, 'phone': profile.phone, 'address': profile.address,
                   'marketing_consent': profile.marketing_consent}
        super().__init__(*args, initial=initial, **kwargs)
        style_widgets(self)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError('Эта почта уже используется в другом аккаунте.')
        return email

    def clean_phone(self):
        raw = self.cleaned_data.get('phone', '')
        if not raw:
            return ''
        phone = normalize_phone(raw)
        if not phone:
            raise forms.ValidationError(PHONE_ERROR)
        if Profile.objects.filter(phone=phone).exclude(user=self.user).exists():
            raise forms.ValidationError('Этот телефон уже привязан к другому аккаунту.')
        return phone

    def save(self):
        d, user = self.cleaned_data, self.user
        if user.username == user.email:  # логин — почта: меняем вместе
            user.username = d['email']
        user.first_name, user.email = d['name'], d['email']
        user.save()
        profile = profile_of(user)
        profile.phone, profile.address, profile.marketing_consent = d['phone'], d['address'], d['marketing_consent']
        profile.save()


class SetupForm(_PasswordsMixin, forms.Form):
    """Первый запуск: владелец сам придумывает логин и пароль для панели."""
    name = forms.CharField(label='Ваше имя', max_length=60)
    email = forms.EmailField(label='Почта (это будет ваш логин)', max_length=150)
    password1 = forms.CharField(label='Пароль', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
                                help_text='Придумайте длинный пароль и запишите его в надёжное место.')
    password2 = forms.CharField(label='Повторите пароль', strip=False, widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}))
    token = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)

    def clean(self):
        data = super().clean()
        self._check_passwords(User(username=data.get('email', ''), email=data.get('email', ''), first_name=data.get('name', '')))
        return data

    def save(self):
        d = self.cleaned_data
        email = d['email'].strip().lower()
        return User.objects.create_superuser(username=email, email=email, password=d['password1'], first_name=d['name'])


class StyledPasswordResetForm(PasswordResetForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = 'Почта'
        style_widgets(self)


class StyledSetPasswordForm(SetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)


class StyledPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)
