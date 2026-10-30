from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.generic import View

from .forms import AuthForm, RegistrationForm


class AuthView(View):
    """Авторизация"""

    def get(self, request):
        return render(request, "user/auth.html", {"form": AuthForm()})

    def post(self, request):
        form = AuthForm(request.POST)
        if not form.is_valid():
            return render(request, "user/auth.html", {"form": form})

        user = authenticate(
            request,
            username=form.cleaned_data["email"],
            password=form.cleaned_data["password"],
        )
        if user is not None:
            login(request, user)
            return redirect("dashboard:index")

        return render(
            request,
            "user/auth.html",
            {
                "form": form,
                "error": "Неверный логин или пароль! Повторите попытку.",
            },
        )


class RegistrationView(View):
    """Регистрация"""

    def get(self, request):
        return render(
            request, "user/registration.html", {"form": RegistrationForm()}
        )

    def post(self, request):
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("dashboard:index")

        return render(request, "user/registration.html", {"form": form})


class LogoutView(View):
    """Выход"""

    def get(self, request):
        logout(request)
        return redirect("dashboard:index")
