from django.db import models
from django.utils import timezone


class Share(models.Model):
    """A tradable share imported from Tinkoff Invest API."""

    figi = models.CharField("FIGI", max_length=255, unique=True)
    isin = models.CharField("ISIN", max_length=255)
    name = models.CharField("Наименование компании", max_length=255, db_index=True)
    ticker = models.CharField("Тикер", max_length=20, unique=True)
    currency = models.CharField("Валюта", max_length=20)
    uid = models.CharField("UID инструмента", max_length=255, unique=True)
    last_price = models.DecimalField(
        "Текущая цена",
        max_digits=20,
        decimal_places=9,
        blank=True,
        null=True,
    )
    is_trend_high = models.BooleanField(
        "Растет цена",
        blank=True,
        null=True,
        default=None,
        help_text="True — цена выросла относительно предыдущего значения, "
        "False — снизилась, NULL — данных для сравнения нет.",
    )
    created_at = models.DateTimeField("Создано", default=timezone.now, editable=False)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Акция"
        verbose_name_plural = "Акции"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.ticker} — {self.name}"
from django.conf import settings


class PriceHistory(models.Model):
    """Stored market price snapshot for a share."""

    share = models.ForeignKey(
        "Share", on_delete=models.CASCADE, related_name="price_history"
    )
    price = models.DecimalField(max_digits=20, decimal_places=9)
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        verbose_name = "История цены"
        verbose_name_plural = "История цен"

    def __str__(self) -> str:
        return f"{self.share.ticker}: {self.price} @ {self.recorded_at:%Y-%m-%d %H:%M}"


class WatchlistItem(models.Model):
    """A personal price alert for a share."""

    CONDITION_ABOVE = "above"
    CONDITION_BELOW = "below"
    CONDITION_CHOICES = (
        (CONDITION_ABOVE, "Цена достигла или превысила"),
        (CONDITION_BELOW, "Цена опустилась до или ниже"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="watchlist"
    )
    share = models.ForeignKey(
        "Share", on_delete=models.CASCADE, related_name="watchers"
    )
    target_price = models.DecimalField(max_digits=20, decimal_places=9)
    condition = models.CharField(
        max_length=10, choices=CONDITION_CHOICES, default=CONDITION_ABOVE
    )
    is_active = models.BooleanField(default=True)
    triggered = models.BooleanField(default=False)
    triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Элемент списка наблюдения"
        verbose_name_plural = "Список наблюдения"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "share", "target_price", "condition"),
                name="unique_watchlist_alert",
            )
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.share.ticker} {self.condition} {self.target_price}"


class Notification(models.Model):
    """In-app notification generated for a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    share = models.ForeignKey(
        "Share", on_delete=models.SET_NULL, null=True, blank=True
    )
    watchlist_item = models.ForeignKey(
        WatchlistItem, on_delete=models.SET_NULL, null=True, blank=True
    )
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self) -> str:
        return f"{self.user}: {self.message}"

class Portfolio(models.Model):
    """A virtual investment portfolio owned by a user."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="portfolios"
    )
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cash_balance = models.DecimalField(max_digits=20, decimal_places=2, default=100000)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Портфель"
        verbose_name_plural = "Портфели"
        constraints = [
            models.UniqueConstraint(
                fields=("user", "name"), name="unique_portfolio_name"
            )
        ]

    def __str__(self) -> str:
        return f"{self.user}: {self.name}"


class Position(models.Model):
    """Aggregated position of a share inside a portfolio."""

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="positions"
    )
    share = models.ForeignKey(
        "Share", on_delete=models.CASCADE, related_name="positions"
    )
    quantity = models.DecimalField(max_digits=20, decimal_places=6, default=0)
    avg_price = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Позиция"
        verbose_name_plural = "Позиции"
        constraints = [
            models.UniqueConstraint(
                fields=("portfolio", "share"), name="unique_portfolio_position"
            )
        ]

    def __str__(self) -> str:
        return f"{self.portfolio}: {self.share.ticker} x {self.quantity}"

    @property
    def market_value(self):
        price = self.share.last_price if self.share.last_price is not None else self.avg_price
        return self.quantity * price

    @property
    def cost_basis(self):
        return self.quantity * self.avg_price

    @property
    def unrealized_pnl(self):
        return self.market_value - self.cost_basis


class Trade(models.Model):
    """A virtual buy or sell operation."""

    SIDE_BUY = "buy"
    SIDE_SELL = "sell"
    SIDE_CHOICES = ((SIDE_BUY, "Покупка"), (SIDE_SELL, "Продажа"))

    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="trades"
    )
    share = models.ForeignKey("Share", on_delete=models.CASCADE, related_name="trades")
    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    price = models.DecimalField(max_digits=20, decimal_places=9)
    realized_pnl = models.DecimalField(max_digits=20, decimal_places=9, default=0)
    executed_at = models.DateTimeField(default=timezone.now, db_index=True)
    strategy = models.ForeignKey(
        "Strategy", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        ordering = ["-executed_at"]
        verbose_name = "Сделка"
        verbose_name_plural = "Сделки"

    def __str__(self) -> str:
        return f"{self.portfolio}: {self.side} {self.share.ticker} x {self.quantity}"

class Strategy(models.Model):
    """A simple automated trading strategy."""

    CONDITION_PRICE_ABOVE = "price_above"
    CONDITION_PRICE_BELOW = "price_below"
    CONDITION_CHOICES = (
        (CONDITION_PRICE_ABOVE, "Цена выше уровня"),
        (CONDITION_PRICE_BELOW, "Цена ниже уровня"),
    )
    ACTION_BUY = "buy"
    ACTION_SELL = "sell"
    ACTION_CHOICES = ((ACTION_BUY, "Купить"), (ACTION_SELL, "Продать"))

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="strategies"
    )
    portfolio = models.ForeignKey(
        Portfolio, on_delete=models.CASCADE, related_name="strategies"
    )
    share = models.ForeignKey("Share", on_delete=models.CASCADE, related_name="strategies")
    name = models.CharField(max_length=100)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES)
    threshold = models.DecimalField(max_digits=20, decimal_places=9)
    action = models.CharField(max_length=4, choices=ACTION_CHOICES)
    quantity = models.DecimalField(max_digits=20, decimal_places=6)
    is_active = models.BooleanField(default=True)
    triggered = models.BooleanField(default=False)
    last_triggered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Стратегия"
        verbose_name_plural = "Стратегии"

    def __str__(self) -> str:
        return f"{self.name}: {self.share.ticker} {self.condition} {self.threshold}"


class StrategyExecution(models.Model):
    """Log entry for a strategy evaluation/execution."""

    strategy = models.ForeignKey(
        Strategy, on_delete=models.CASCADE, related_name="executions"
    )
    trade = models.ForeignKey(
        Trade, on_delete=models.SET_NULL, null=True, blank=True
    )
    success = models.BooleanField(default=False)
    message = models.CharField(max_length=255, blank=True)
    executed_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-executed_at"]
        verbose_name = "Исполнение стратегии"
        verbose_name_plural = "Исполнения стратегий"

    def __str__(self) -> str:
        return f"{self.strategy}: {self.message}"

