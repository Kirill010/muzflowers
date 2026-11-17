import secrets

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordResetView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from shop.cart import Cart
from shop.legal import record_acceptance
from shop.models import Order
from shop.throttle import throttled

from .forms import LoginForm, ProfileForm, RegisterForm, SetupForm, StyledPasswordResetForm
from .models import profile_of

BACKEND = 'accounts.backends.EmailOrPhoneBackend'


class ThrottledLoginView(LoginView):
    template_name = 'accounts/login.html'
    form_class = LoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if throttled(request, 'login', 10, 600):
            form = self.get_form()
            form.add_error(None, 'Слишком много попыток входа. Попробуйте через 10 минут.')
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)


class ThrottledPasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    form_class = StyledPasswordResetForm
    success_url = reverse_lazy('accounts:password_reset_done')

    def post(self, request, *args, **kwargs):
        if throttled(request, 'reset', 5, 3600):
            return self.render_to_response(self.get_context_data(form=self.get_form(), throttled=True), status=429)
        return super().post(request, *args, **kwargs)


def _safe_next(request, default):
    target = request.POST.get('next') or request.GET.get('next') or ''
    return target if url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}) else default


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST':
        if throttled(request, 'register', 10, 3600):
            form.add_error(None, 'Слишком много попыток. Попробуйте позже.')
        elif form.is_valid():
            user = form.save()
            record_acceptance(request, 'personal', reference=f'account:{user.pk}', contact=user.email, user=user)
            login(request, user, backend=BACKEND)
            # заказ, оформленный в этом браузере до регистрации, привязываем к новому аккаунту
            Order.objects.filter(token=request.session.get('mz_last_order', ''), user__isnull=True).update(user=user)
            messages.success(request, f'Добро пожаловать, {user.first_name}!')
            return redirect(_safe_next(request, 'accounts:profile'))
    return render(request, 'accounts/register.html', {'form': form, 'next': request.GET.get('next', '')})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        was_marketing = profile_of(request.user).marketing_consent
        form.save()
        is_marketing = form.cleaned_data['marketing_consent']
        if was_marketing != is_marketing:
            record_acceptance(request, 'marketing', reference=f'account:{request.user.pk}', contact=request.user.email,
                              user=request.user, action='accepted' if is_marketing else 'withdrawn')
        messages.success(request, 'Данные сохранены.')
        return redirect('accounts:profile')
    orders = request.user.orders.select_related('shop').prefetch_related('items', 'addons')
    return render(request, 'accounts/profile.html', {'form': form, 'orders': orders})


@login_required
@require_POST
def repeat_order(request, pk):
    """«Повторить заказ»: кладём в корзину те же букеты (если они ещё продаются)."""
    order = get_object_or_404(request.user.orders.prefetch_related('items__product__variants'), pk=pk)
    cart, added = Cart(request), 0
    for item in order.items.all():
        product = item.product
        if product is None or not product.is_active:
            continue
        variant_ids = {v.pk for v in product.active_variants}
        variant_id = item.variant_id if item.variant_id in variant_ids else (product.default_variant.pk if variant_ids else 0)
        cart.add(product.pk, variant_id, item.qty)
        added += 1
    if added:
        messages.success(request, 'Букеты из прошлого заказа — в корзине. Проверьте и оформите.')
        return redirect('shop:cart')
    messages.error(request, 'Этих букетов сейчас нет в каталоге.')
    return redirect('accounts:profile')


def _is_local(request):
    """Запрос с этого же компьютера (не через прокси, где все посетители выглядят как 127.0.0.1)."""
    return not settings.BEHIND_PROXY and request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1')


def setup(request):
    """Первый запуск: владелец придумывает логин и пароль прямо в браузере. Работает, пока нет ни одного владельца."""
    if get_user_model().objects.filter(is_superuser=True).exists():
        raise Http404
    given = request.POST.get('token') or request.GET.get('token') or ''
    token_ok = bool(settings.SETUP_TOKEN) and secrets.compare_digest(given, settings.SETUP_TOKEN)
    if not (_is_local(request) or token_ok):
        return render(request, 'accounts/setup_locked.html', status=403)
    form = SetupForm(request.POST or None, initial={'token': given})
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user, backend=BACKEND)
        messages.success(request, 'Готово! Вы вошли в панель владельца.')
        return redirect('/' + settings.ADMIN_URL)
    return render(request, 'accounts/setup.html', {'form': form})
