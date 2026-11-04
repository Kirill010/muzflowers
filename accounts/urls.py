from django.contrib.auth import views as auth_views
from django.contrib.auth.views import LogoutView
from django.urls import path, reverse_lazy

from . import views
from .forms import StyledPasswordChangeForm, StyledSetPasswordForm

app_name = 'accounts'

urlpatterns = [
    path('login/', views.ThrottledLoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', views.register, name='register'),
    path('profile/', views.profile, name='profile'),
    path('orders/<int:pk>/repeat/', views.repeat_order, name='repeat'),
    path('setup/', views.setup, name='setup'),

    path('password/change/', auth_views.PasswordChangeView.as_view(
        template_name='accounts/password_change.html', form_class=StyledPasswordChangeForm,
        success_url=reverse_lazy('accounts:password_change_done')), name='password_change'),
    path('password/change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='accounts/password_change_done.html'), name='password_change_done'),
    path('password/reset/', views.ThrottledPasswordResetView.as_view(), name='password_reset'),
    path('password/reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'), name='password_reset_done'),
    path('password/reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html', form_class=StyledSetPasswordForm,
        success_url=reverse_lazy('accounts:password_reset_complete')), name='password_reset_confirm'),
    path('password/reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'), name='password_reset_complete'),
]
