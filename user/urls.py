from django.urls import path

from user.views import AuthView, LogoutView, RegistrationView

app_name = "user"

urlpatterns = [
    path("login/", AuthView.as_view(), name="auth"),
    path("registration/", RegistrationView.as_view(), name="registration"),
    path("logout/", LogoutView.as_view(), name="logout"),
]
