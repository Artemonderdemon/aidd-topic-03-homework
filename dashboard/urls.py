from django.urls import include, path

from dashboard.views import (
    ShareCreateView,
    ShareDeleteView,
    ShareDetailView,
    ShareListView,
    ShareUpdateView,
    NotificationListView,
    PortfolioCreateView,
    PortfolioDetailView,
    PortfolioListView,
    PriceHistoryView,
    StrategyCreateView,
    StrategyListView,
    WatchlistCreateView,
    WatchlistDeleteView,
    WatchlistListView,
    health,

)

app_name = "dashboard"

urlpatterns = [
    path("", ShareListView.as_view(), name="index"),
    path("<int:pk>/", ShareDetailView.as_view(), name="detail"),
    path("create/", ShareCreateView.as_view(), name="create"),
    path("update/<int:pk>/", ShareUpdateView.as_view(), name="update"),
    path("delete/<int:pk>/", ShareDeleteView.as_view(), name="delete"),
    path("api/", include("dashboard.api.urls")),
    path("health/", health, name="health"),

    path("watchlist/", WatchlistListView.as_view(), name="watchlist"),
    path("watchlist/create/", WatchlistCreateView.as_view(), name="watchlist_create"),
    path("watchlist/<int:pk>/delete/", WatchlistDeleteView.as_view(), name="watchlist_delete"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),

    path("portfolios/", PortfolioListView.as_view(), name="portfolios"),
    path("portfolios/create/", PortfolioCreateView.as_view(), name="portfolio_create"),
    path("portfolios/<int:pk>/", PortfolioDetailView.as_view(), name="portfolio_detail"),

    path("strategies/", StrategyListView.as_view(), name="strategies"),
    path("strategies/create/", StrategyCreateView.as_view(), name="strategy_create"),

    path("shares/<int:pk>/price-history/", PriceHistoryView.as_view(), name="price_history"),
]
