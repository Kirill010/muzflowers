from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import datetime
from .models import Order, ConsultationRequest


class OrderCreateForm(forms.ModelForm):
    promo_code = forms.CharField(max_length=50, required=False, label="Промокод")

    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'email', 'phone',
                  'address', 'delivery_date', 'delivery_time', 'comment']
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'delivery_time': forms.TimeInput(attrs={'type': 'time'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Иван'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Иванов'}),
            'email': forms.EmailInput(attrs={'placeholder': 'ivan@example.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+7 (999) 123-45-67'}),
            'address': forms.TextInput(attrs={'placeholder': 'г. Москва, ул. Пушкина, д. 1'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Текст открытки или пожелания'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        cleaned = ''.join(filter(str.isdigit, phone))
        if len(cleaned) < 10:
            raise ValidationError("Введите корректный номер (минимум 10 цифр).")
        return phone

    def clean_delivery_date(self):
        delivery_date = self.cleaned_data['delivery_date']
        today = timezone.now().date()
        if delivery_date < today:
            raise ValidationError("Дата доставки не может быть в прошлом.")
        max_date = today + datetime.timedelta(days=30)
        if delivery_date > max_date:
            raise ValidationError(f"Дата не может быть позже {max_date.strftime('%d.%m.%Y')}.")
        return delivery_date


class ConsultationForm(forms.ModelForm):
    class Meta:
        model = ConsultationRequest
        fields = ['name', 'phone', 'email', 'occasion', 'budget_min', 'budget_max', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Опишите, какой букет вы хотите...'}),
            'name': forms.TextInput(attrs={'placeholder': 'Ваше имя'}),
            'phone': forms.TextInput(attrs={'placeholder': '+7 (999) 123-45-67'}),
        }