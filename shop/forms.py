from django import forms
from django.utils import timezone

from . import slots
from .models import Addon, Lead, Order, Shop, SiteSettings
from .orders import is_prepay_required, payment_options
from .utils import normalize_phone

PHONE_ERROR = 'Введите телефон полностью — например, +7 900 123-45-67'


def style_widgets(form):
    """Подключает к полям классы оформления сайта (галочки и переключатели рисуем в шаблоне сами)."""
    for field in form.fields.values():
        widget = field.widget
        if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.HiddenInput)):
            continue
        css = 'select' if isinstance(widget, forms.Select) else 'input input--area' if isinstance(widget, forms.Textarea) else 'input'
        widget.attrs['class'] = f'{widget.attrs.get("class", "")} {css}'.strip()


def clean_phone_value(value):
    phone = normalize_phone(value)
    if not phone:
        raise forms.ValidationError(PHONE_ERROR)
    return phone


class CheckoutForm(forms.Form):
    name = forms.CharField(label='Ваше имя', max_length=100)
    phone = forms.CharField(label='Телефон', max_length=30)
    email = forms.EmailField(label='Почта (необязательно)', required=False)

    receive_method = forms.ChoiceField(label='Как получите', choices=Order.Method.choices, widget=forms.RadioSelect,
                                       initial=Order.Method.PICKUP)
    shop = forms.ModelChoiceField(label='Где забрать', queryset=Shop.objects.none(), required=False, empty_label=None)
    address = forms.CharField(label='Адрес доставки', max_length=255, required=False)
    address_details = forms.CharField(label='Подъезд, этаж, домофон', max_length=120, required=False)
    other_recipient = forms.BooleanField(label='Получатель — другой человек', required=False)
    recipient_name = forms.CharField(label='Имя получателя', max_length=100, required=False)
    recipient_phone = forms.CharField(label='Телефон получателя', max_length=30, required=False)
    surprise = forms.BooleanField(label='Сюрприз: не звонить получателю и не говорить, от кого', required=False)

    date = forms.DateField(label='Дата', input_formats=['%Y-%m-%d'])
    time_slot = forms.CharField(label='Время', max_length=20)

    card_text = forms.CharField(label='Текст открытки', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    comment = forms.CharField(label='Пожелания к заказу', max_length=500, required=False, widget=forms.Textarea(attrs={'rows': 2}))
    promo = forms.CharField(label='Промокод', max_length=30, required=False)

    payment_method = forms.ChoiceField(label='Оплата', choices=Order.Pay.choices, widget=forms.RadioSelect)
    consent_pd = forms.BooleanField(error_messages={'required': 'Нужно согласие на обработку персональных данных'})
    consent_offer = forms.BooleanField(error_messages={'required': 'Нужно принять условия оферты'})
    marketing_consent = forms.BooleanField(label='Хочу получать новости и акции', required=False)
    website = forms.CharField(required=False)  # ловушка для роботов: человек это поле не видит и не заполняет

    def __init__(self, *args, site=None, cart=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.site = site or SiteSettings.load()
        self.cart = cart
        self.pickup_shops = list(Shop.objects.filter(is_active=True, is_pickup=True))
        self.fields['shop'].queryset = Shop.objects.filter(is_active=True, is_pickup=True)
        if len(self.pickup_shops) == 1:
            self.fields['shop'].initial = self.pickup_shops[0].pk
        self.addons = list(Addon.objects.filter(is_active=True))
        for addon in self.addons:
            self.fields[f'addon_{addon.pk}'] = forms.BooleanField(label=addon.name, required=False)
            self.fields[f'addon_{addon.pk}_note'] = forms.CharField(label=addon.note_label or 'Пожелание', max_length=200, required=False)
            if cart is not None and str(addon.pk) in cart.addons and not self.is_bound:
                self.initial[f'addon_{addon.pk}'] = True
                self.initial[f'addon_{addon.pk}_note'] = cart.addons[str(addon.pk)]
        self.fields['payment_method'].choices = [(o['value'], o['label']) for o in payment_options(False, self.site)] + \
                                                [(o['value'], o['label']) for o in payment_options(True, self.site)]
        for name, attrs in {
            'name': {'autocomplete': 'name', 'placeholder': 'Как к вам обращаться'},
            'phone': {'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '+7 900 000-00-00'},
            'email': {'autocomplete': 'email', 'inputmode': 'email', 'placeholder': 'name@mail.ru'},
            'address': {'autocomplete': 'street-address', 'placeholder': 'Улица, дом, квартира'},
            'recipient_phone': {'inputmode': 'tel', 'placeholder': '+7 900 000-00-00'},
            'card_text': {'placeholder': 'Напишем от руки. Например: «С днём рождения, мама!»'},
            'comment': {'placeholder': 'Любимый цвет, аллергия на запахи, как позвонить…'},
        }.items():
            self.fields[name].widget.attrs.update(attrs)
        style_widgets(self)
        # для шаблона: [(дополнение, галочка, поле для пожелания)]
        self.addon_rows = [(a, self[f'addon_{a.pk}'], self[f'addon_{a.pk}_note']) for a in self.addons]

    # --- отдельные поля ---
    def clean_phone(self):
        return clean_phone_value(self.cleaned_data['phone'])

    def clean_name(self):
        return self.cleaned_data['name'].strip()

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Не удалось отправить форму.')
        return ''

    # --- всё вместе ---
    def clean(self):
        data = super().clean()
        site = self.site
        if site.orders_paused:
            raise forms.ValidationError(site.pause_message or 'Сейчас не принимаем заказы на сайте.')
        method = data.get('receive_method')

        if method == Order.Method.DELIVERY:
            if not site.delivery_enabled:
                self.add_error('receive_method', 'Доставка сейчас не работает — выберите самовывоз.')
            if len((data.get('address') or '').strip()) < 5:
                self.add_error('address', 'Укажите адрес: улица, дом, квартира')
            if data.get('other_recipient'):
                if not data.get('recipient_name'):
                    self.add_error('recipient_name', 'Как зовут получателя?')
                try:
                    data['recipient_phone'] = clean_phone_value(data.get('recipient_phone'))
                except forms.ValidationError as exc:
                    self.add_error('recipient_phone', exc)
            else:
                data['recipient_name'] = data['recipient_phone'] = ''
        elif method == Order.Method.PICKUP:
            if not self.pickup_shops:
                self.add_error('receive_method', 'Самовывоз сейчас недоступен — выберите доставку.')
            elif not data.get('shop'):
                if len(self.pickup_shops) == 1:
                    data['shop'] = self.pickup_shops[0]
                else:
                    self.add_error('shop', 'Выберите, где забрать')
            data['recipient_name'] = data['recipient_phone'] = ''
            data['surprise'] = False

        day = data.get('date')
        if day and method:
            problem = slots.day_problem(day, method, site)
            if problem:
                self.add_error('date', problem)
            else:
                option = slots.pick_option(day, method, data.get('time_slot', ''), site)
                if option is None:
                    self.add_error('time_slot', 'Выберите время из списка')
                data['option'] = option
            allowed = {o['value'] for o in payment_options(is_prepay_required(day, site), site)}
            if data.get('payment_method') not in allowed:
                self.add_error('payment_method', 'Выберите способ оплаты из списка')

        selected = []
        for addon in self.addons:
            if data.get(f'addon_{addon.pk}'):
                note = (data.get(f'addon_{addon.pk}_note') or '').strip()
                if addon.note_required and not note:
                    self.add_error(f'addon_{addon.pk}_note', f'{addon.note_label or "Напишите пожелание"}')
                selected.append((addon, note))
        data['addons'] = selected
        return data


class LeadForm(forms.Form):
    """Заявка от офисов и на подписку."""
    name = forms.CharField(label='Ваше имя', max_length=100)
    company = forms.CharField(label='Компания', max_length=120, required=False)
    phone = forms.CharField(label='Телефон', max_length=30)
    email = forms.EmailField(label='Почта', required=False)
    message = forms.CharField(label='Что нужно', max_length=1000, required=False, widget=forms.Textarea(attrs={'rows': 3}))
    consent = forms.BooleanField(error_messages={'required': 'Нужно согласие на обработку персональных данных'})
    website = forms.CharField(required=False)

    def __init__(self, *args, kind=Lead.Kind.OFFICE, **kwargs):
        super().__init__(*args, **kwargs)
        self.kind = kind
        self.fields['phone'].widget.attrs.update({'autocomplete': 'tel', 'inputmode': 'tel', 'placeholder': '+7 900 000-00-00'})
        self.fields['name'].widget.attrs.update({'autocomplete': 'name'})
        self.fields['email'].widget.attrs.update({'autocomplete': 'email'})
        placeholder = {
            Lead.Kind.OFFICE: 'Как часто нужны цветы, сколько человек, адрес офиса…',
            Lead.Kind.SUBSCRIPTION: 'Какие цветы любите, куда и в какой день недели привозить…',
        }.get(kind, 'Ваш вопрос')
        self.fields['message'].widget.attrs['placeholder'] = placeholder
        if kind == Lead.Kind.OFFICE:
            self.fields['company'].label = 'Компания или офис'
        style_widgets(self)

    def clean_phone(self):
        return clean_phone_value(self.cleaned_data['phone'])

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('Не удалось отправить форму.')
        return ''
