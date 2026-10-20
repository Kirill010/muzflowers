from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.shortcuts import redirect, render

from shop.throttle import throttled

from .forms import RegisterForm


class ThrottledLoginView(LoginView):
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if throttled(request, 'login', 10, 600):
            return HttpResponse('Слишком много попыток входа. Попробуйте через 10 минут.', status=429)
        return super().post(request, *args, **kwargs)


def register(request):
    if request.user.is_authenticated:
        return redirect('accounts:profile')
    if request.method == 'POST':
        if throttled(request, 'register', 10, 3600):
            return HttpResponse('Слишком много попыток. Попробуйте позже.', status=429)
        form = RegisterForm(request.POST)
        if form.is_valid():
            login(request, form.save())
            return redirect('shop:index')
    else:
        form = RegisterForm()
    return render(request, 'accounts/register.html', {'form': form})


@login_required
def profile(request):
    orders = request.user.orders.prefetch_related('items')
    return render(request, 'accounts/profile.html', {'orders': orders})
