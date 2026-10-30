from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import FormView, View

from .forms import AuthForm, RegistrationForm


class _RedirectAuthenticatedMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard:index")
        return super().dispatch(request, *args, **kwargs)


class _NextUrlMixin:
    success_url = reverse_lazy("dashboard:index")

    def get_success_url(self) -> str:
        next_url = self.request.POST.get("next") or self.request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        ):
            return next_url
        return str(self.success_url)


class AuthView(_RedirectAuthenticatedMixin, _NextUrlMixin, FormView):
    """Authenticate a user by email and password."""

    template_name = "user/auth.html"
    form_class = AuthForm

    def form_valid(self, form):
        login(self.request, form.user)
        return super().form_valid(form)


class RegistrationView(_RedirectAuthenticatedMixin, _NextUrlMixin, FormView):
    """Register a user and log them in immediately."""

    template_name = "user/registration.html"
    form_class = RegistrationForm

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)


@method_decorator(login_required, name="dispatch")
class LogoutView(View):
    """Log out via POST to avoid CSRF-triggered state changes."""

    def post(self, request):
        logout(request)
        return redirect("dashboard:index")
