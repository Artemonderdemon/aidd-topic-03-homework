from django.conf import settings
from django.db import models


class Share(models.Model):
    """Акция"""

    figi = models.CharField(max_length=255, unique=True)
    isin = models.CharField(max_length=255)
    name = models.CharField(max_length=255, verbose_name="Наименование компании")
    ticker = models.CharField(max_length=10, unique=True, verbose_name="Тикер")
    currency = models.CharField(max_length=20, verbose_name="Валюта")
    uid = models.CharField(max_length=255, unique=True)
    last_price = models.FloatField(blank=True, null=True, verbose_name="Текущая цена")
    is_trend_high = models.BooleanField(
        blank=True, null=True, verbose_name="Растет цена"
    )
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"

    def __str__(self):
        return f"{self.ticker} — {self.name}"


class WatchlistItem(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="watchlist_items",
    )
    share = models.ForeignKey(
        Share, on_delete=models.CASCADE, related_name="watchlist_items"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("share__name",)
        constraints = [
            models.UniqueConstraint(
                fields=("user", "share"), name="unique_user_watchlist_share"
            )
        ]

    def __str__(self):
        return f"{self.user} — {self.share}"


class PriceAlert(models.Model):
    watchlist_item = models.ForeignKey(
        WatchlistItem, on_delete=models.CASCADE, related_name="price_alerts"
    )
    target_price = models.DecimalField(max_digits=20, decimal_places=8)
    is_active = models.BooleanField(default=True)
    last_observed_above = models.BooleanField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("target_price",)
        constraints = [
            models.UniqueConstraint(
                fields=("watchlist_item", "target_price"),
                name="unique_watchlist_target_price",
            ),
            models.CheckConstraint(
                condition=models.Q(target_price__gt=0),
                name="price_alert_target_positive",
            ),
        ]

    def __str__(self):
        return f"{self.watchlist_item.share.ticker} @ {self.target_price}"


class AlertNotification(models.Model):
    price_alert = models.ForeignKey(
        PriceAlert, on_delete=models.CASCADE, related_name="notifications"
    )
    observed_price = models.DecimalField(max_digits=20, decimal_places=8)
    triggered_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-triggered_at",)

    @property
    def user(self):
        return self.price_alert.watchlist_item.user
