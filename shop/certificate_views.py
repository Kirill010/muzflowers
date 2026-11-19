import secrets

from django import forms
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from . import notifications, payments
from .forms import clean_phone_value, style_widgets
from .legal import record_acceptance
from .models import Order
from .throttle import throttled
from .views import origin_of


class CertificatePurchaseForm(forms.Form):
    amount = forms.ChoiceField(label='Сумма сертификата', choices=[(1000, '1 000 ₽'), (3000, '3 000 ₽'), (5000, '5 000 ₽')],
                               initial=1000, widget=forms.RadioSelect)
    custom_amount = forms.IntegerField(label='Или своя сумма, от 500 до 30 000 ₽', required=False, min_value=500, max_value=30000)
    name = forms.CharField(label='Ваше имя', max_length=100)
    phone = forms.CharField(label='Телефон', max_length=30)
    email = forms.EmailField(label='Почта для ссылки (необязательно)', required=False)
    consent_pd = forms.BooleanField(label='Согласен на обработку персональных данных')
    consent_offer = forms.BooleanField(label='Принимаю условия оферты')
    operation_id = forms.CharField(widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        style_widgets(self)

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data['phone'])

    def clean(self):
        data = super().clean()
        custom = data.get('custom_amount')
        data['final_amount'] = custom or int(data.get('amount') or 0)
        return data


def certificate_purchase(request):
    site_url = origin_of(request)
    if request.method != 'POST':
        request.session['certificate_operation'] = secrets.token_urlsafe(16)
    form = CertificatePurchaseForm(request.POST if request.method == 'POST' else None,
                                   initial={'operation_id': request.session.get('certificate_operation', '')})
    if request.method == 'POST' and form.is_valid():
        if throttled(request, 'certificate', 10, 3600):
            form.add_error(None, 'Слишком много операций. Попробуйте позже.')
        elif not payments.is_configured():
            form.add_error(None, 'Онлайн-оплата ещё не подключена. Позвоните нам — поможем оформить сертификат.')
        elif form.cleaned_data['operation_id'] != request.session.get('certificate_operation'):
            form.add_error(None, 'Форма устарела или уже использована. Откройте страницу ещё раз.')
        else:
            data = form.cleaned_data
            amount = data['final_amount']
            order = Order.objects.create(
                kind=Order.Kind.CERTIFICATE, name=data['name'], phone=data['phone'], email=data.get('email', ''),
                date=timezone.localdate(), asap=True, subtotal=amount, total=amount,
                payment_method=Order.Pay.ONLINE, payment_status=Order.PayStatus.PENDING, source='site-certificate',
            )
            record_acceptance(request, 'offer', reference=f'order:{order.pk}', contact=order.email or order.phone)
            record_acceptance(request, 'personal', reference=f'order:{order.pk}', contact=order.email or order.phone)
            request.session.pop('certificate_operation', None)
            transaction.on_commit(lambda: notifications.dispatch(order.pk, site_url))
            return redirect('shop:order_pay', token=order.token)
    return render(request, 'shop/certificate.html', {'form': form, 'online_payment': payments.is_configured()})
