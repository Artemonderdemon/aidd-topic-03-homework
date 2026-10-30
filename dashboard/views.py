from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.generic import (
    CreateView,
    DeleteView,
    ListView,
    View,
    UpdateView,
)

from .forms import PriceAlertForm, ShareModelForm, WatchlistItemForm
from .models import AlertNotification, PriceAlert, Share, WatchlistItem
from .services.graph import get_graph


class IsUserAuthenticatedMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated

    @staticmethod
    def handle_no_permission():
        return redirect("dashboard:index")


class ShareListView(ListView):
    """Список акций"""

    model = Share
    template_name = "dashboard/list.html"
    paginate_by = 100
    ordering = ["name"]


class ShareDetailView(View):
    @staticmethod
    def get(request, pk):
        share = get_object_or_404(Share, pk=pk)

        return render(
            request,
            "dashboard/detail.html",
            {"plot_div": get_graph(share), "share": share},
        )


class ShareCreateView(IsUserAuthenticatedMixin, CreateView):
    """Добавление инструмента"""

    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class WatchlistView(IsUserAuthenticatedMixin, ListView):
    model = WatchlistItem
    template_name = "dashboard/watchlist.html"
    context_object_name = "watchlist_items"

    def get_queryset(self):
        return (
            WatchlistItem.objects.filter(user=self.request.user)
            .select_related("share")
            .prefetch_related("price_alerts__notifications")
        )


class WatchlistItemCreateView(IsUserAuthenticatedMixin, CreateView):
    model = WatchlistItem
    form_class = WatchlistItemForm
    template_name = "dashboard/watchlist_item_form.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)


class WatchlistItemDeleteView(IsUserAuthenticatedMixin, DeleteView):
    model = WatchlistItem
    template_name = "dashboard/watchlist_item_confirm_delete.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_queryset(self):
        return WatchlistItem.objects.filter(user=self.request.user)


class PriceAlertCreateView(IsUserAuthenticatedMixin, CreateView):
    model = PriceAlert
    form_class = PriceAlertForm
    template_name = "dashboard/price_alert_form.html"

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        self.watchlist_item = get_object_or_404(
            WatchlistItem, pk=kwargs["item_pk"], user=request.user
        )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["watchlist_item"] = self.watchlist_item
        return kwargs

    def form_valid(self, form):
        form.instance.watchlist_item = self.watchlist_item
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy("dashboard:watchlist")


class PriceAlertDeleteView(IsUserAuthenticatedMixin, DeleteView):
    model = PriceAlert
    template_name = "dashboard/price_alert_confirm_delete.html"
    success_url = reverse_lazy("dashboard:watchlist")

    def get_queryset(self):
        return PriceAlert.objects.filter(watchlist_item__user=self.request.user)


class AlertNotificationListView(IsUserAuthenticatedMixin, ListView):
    model = AlertNotification
    template_name = "dashboard/notifications.html"
    context_object_name = "notifications"
    paginate_by = 50

    def get_queryset(self):
        return (
            AlertNotification.objects.filter(
                price_alert__watchlist_item__user=self.request.user
            )
            .select_related("price_alert__watchlist_item__share")
        )


class AlertNotificationReadView(IsUserAuthenticatedMixin, View):
    def post(self, request, pk):
        notification = get_object_or_404(
            AlertNotification,
            pk=pk,
            price_alert__watchlist_item__user=request.user,
        )
        if notification.read_at is None:
            notification.read_at = timezone.now()
            notification.save(update_fields=("read_at",))
        return redirect("dashboard:notifications")


class ShareUpdateView(IsUserAuthenticatedMixin, UpdateView):
    """Редактирование инструмента"""

    model = Share
    template_name = "dashboard/create.html"
    form_class = ShareModelForm
    success_url = reverse_lazy("dashboard:index")


class ShareDeleteView(IsUserAuthenticatedMixin, DeleteView):
    """Удаление задачи"""

    model = Share
    template_name = "dashboard/delete.html"
    success_url = reverse_lazy("dashboard:index")
