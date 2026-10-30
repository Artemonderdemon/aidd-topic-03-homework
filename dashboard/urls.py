from django.urls import include, path

from dashboard.views import (
    AlertNotificationListView,
    AlertNotificationReadView,
    PriceAlertCreateView,
    PriceAlertDeleteView,
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
    WatchlistItemCreateView,
    WatchlistItemDeleteView,
    WatchlistView,
)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("<int:pk>", ShareDetailView.as_view(), name="detail"),
    path("create", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>", ShareDeleteView.as_view(), name="delete"),
    path("watchlist/", WatchlistView.as_view(), name="watchlist"),
    path(
        "watchlist/add/",
        WatchlistItemCreateView.as_view(),
        name="watchlist-add",
    ),
    path(
        "watchlist/<int:pk>/remove/",
        WatchlistItemDeleteView.as_view(),
        name="watchlist-remove",
    ),
    path(
        "watchlist/<int:item_pk>/alerts/add/",
        PriceAlertCreateView.as_view(),
        name="alert-add",
    ),
    path(
        "alerts/<int:pk>/remove/",
        PriceAlertDeleteView.as_view(),
        name="alert-remove",
    ),
    path("notifications/", AlertNotificationListView.as_view(), name="notifications"),
    path(
        "notifications/<int:pk>/read/",
        AlertNotificationReadView.as_view(),
        name="notification-read",
    ),
    path("api/", include("dashboard.api.urls")),
]
