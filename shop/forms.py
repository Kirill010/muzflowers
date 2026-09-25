from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import datetime
from .models import Order


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['first_name', 'last_name', 'email', 'phone',
                  'address', 'delivery_date', 'comment']
        widgets = {
            'delivery_date': forms.DateInput(attrs={'type': 'date'}),
            'first_name': forms.TextInput(attrs={'placeholder': 'Иван'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Иванов'}),
            'email': forms.EmailInput(attrs={'placeholder': 'ivan@example.com'}),
            'phone': forms.TextInput(attrs={'placeholder': '+7 (999) 123-45-67'}),
            'address': forms.TextInput(attrs={'placeholder': 'г. Москва, ул. Пушкина, д. 1, кв. 1'}),
            'comment': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Текст открытки или пожелания'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data['phone']
        cleaned_phone = ''.join(filter(str.isdigit, phone))
        if len(cleaned_phone) < 10:
            raise ValidationError("Введите корректный номер (минимум 10 цифр).")
        return phone

    def clean_delivery_date(self):
        delivery_date = self.cleaned_data['delivery_date']
        today = timezone.now().date()
        if delivery_date < today:
            raise ValidationError("Дата доставки не может быть в прошлом.")
        max_date = today + datetime.timedelta(days=30)
        if delivery_date > max_date:
            raise ValidationError(
                f"Дата не может быть позже {max_date.strftime('%d.%m.%Y')}."
            )
        return delivery_date