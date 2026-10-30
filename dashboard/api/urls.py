from django.urls import include, path

urlpatterns = [
    path("v1/", include("dashboard.api.v1.urls")),
]
