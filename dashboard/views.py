from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from config.settings import logger

from .forms import ShareModelForm
from .models import Share
from .services.graph import get_graph
from .services.market_data import MarketDataError


class ShareListView(ListView):
    """Public list of shares."""

    model = Share
    template_name = "dashboard/list.html"
    context_object_name = "share_list"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(DetailView):
    """Public share details with a 180-day price chart."""

    model = Share
    template_name = "dashboard/detail.html"
    context_object_name = "share"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["plot_div"] = ""
        context["graph_error"] = ""
        try:
            context["plot_div"] = get_graph(self.object)
        except MarketDataError as exc:
            logger.warning("Failed to build graph for share %s: %s", self.object.pk, exc)
            context["graph_error"] = (
                "График временно недоступен: не удалось получить рыночные данные."
            )
        return context


class ShareCreateView(LoginRequiredMixin, CreateView):
    """Create a share; authentication is required."""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")
    login_url = reverse_lazy("user:auth")


class ShareUpdateView(LoginRequiredMixin, UpdateView):
    """Update a share; authentication is required."""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")
    login_url = reverse_lazy("user:auth")


class ShareDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a share after POST confirmation."""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")
    login_url = reverse_lazy("user:auth")


def health(request):
    """Small readiness endpoint for Docker and monitoring."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:  # pragma: no cover - depends on infrastructure
        logger.exception("Health check failed: %s", exc)
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok", "database": "ok"})
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse_lazy

from .forms import PortfolioForm, StrategyForm, TradeForm, WatchlistItemForm
from .models import (
    Notification,
    Portfolio,
    Share,
    Strategy,
    WatchlistItem,
)
from .services.alerts import evaluate_watchlist
from .services.portfolio import PortfolioServiceError, execute_trade, portfolio_summary
from .services.strategies import evaluate_strategies


class WatchlistListView(LoginRequiredMixin, ListView):
    model = WatchlistItem
    template_name = "dashboard/watchlist.html"
    context_object_name = "items"

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user).select_related("share")


class WatchlistCreateView(LoginRequiredMixin, CreateView):
    model = WatchlistItem
    form_class = WatchlistItemForm
    template_name = "dashboard/watchlist_form.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class WatchlistDeleteView(LoginRequiredMixin, DeleteView):
    model = WatchlistItem
    template_name = "dashboard/watchlist_delete.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user)


class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = "dashboard/notifications.html"
    context_object_name = "notifications"

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def post(self, request, *args, **kwargs):
        Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
        return redirect("dashboard:notifications")


class PortfolioListView(LoginRequiredMixin, ListView):
    model = Portfolio
    template_name = "dashboard/portfolios.html"
    context_object_name = "portfolios"

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user)


class PortfolioCreateView(LoginRequiredMixin, CreateView):
    model = Portfolio
    form_class = PortfolioForm
    template_name = "dashboard/portfolio_form.html"
    success_url = reverse_lazy("dashboard:portfolios")

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class PortfolioDetailView(LoginRequiredMixin, DetailView):
    model = Portfolio
    template_name = "dashboard/portfolio_detail.html"
    context_object_name = "portfolio"

    def get_queryset(self):
        return Portfolio.objects.filter(user=self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["summary"] = portfolio_summary(self.object)
        context["trade_form"] = TradeForm()
        context["trades"] = self.object.trades.select_related("share")[:50]
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = TradeForm(request.POST)
        if form.is_valid():
            try:
                execute_trade(
                    portfolio=self.object,
                    share=form.cleaned_data["share"],
                    side=form.cleaned_data["side"],
                    quantity=form.cleaned_data["quantity"],
                    price=form.cleaned_data["price"],
                )
            except PortfolioServiceError as exc:
                form.add_error(None, str(exc))
                context = self.get_context_data()
                context["trade_form"] = form
                return self.render_to_response(context)
        context = self.get_context_data()
        context["trade_form"] = form
        return self.render_to_response(context)


class StrategyListView(LoginRequiredMixin, ListView):
    model = Strategy
    template_name = "dashboard/strategies.html"
    context_object_name = "strategies"

    def get_queryset(self):
        return Strategy.objects.filter(user=self.request.user).select_related(
            "portfolio", "share"
        )


class StrategyCreateView(LoginRequiredMixin, CreateView):
    model = Strategy
    form_class = StrategyForm
    template_name = "dashboard/strategy_form.html"
    success_url = reverse_lazy("dashboard:strategies")

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["portfolio"].queryset = Portfolio.objects.filter(user=self.request.user)
        form.fields["share"].queryset = Share.objects.order_by("ticker")
        return form

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class PriceHistoryView(LoginRequiredMixin, DetailView):
    model = Share
    template_name = "dashboard/price_history.html"
    context_object_name = "share"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        history = self.object.price_history.order_by("recorded_at")
        context["history"] = history
        prices = [float(item.price) for item in history]
        context["first_price"] = prices[0] if prices else None
        context["last_price"] = prices[-1] if prices else None
        if len(prices) >= 2:
            context["absolute_change"] = prices[-1] - prices[0]
            context["percent_change"] = ((prices[-1] - prices[0]) / prices[0]) * 100
        else:
            context["absolute_change"] = None
            context["percent_change"] = None
        return context

