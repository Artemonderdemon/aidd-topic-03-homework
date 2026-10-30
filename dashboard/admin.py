from django.contrib import admin

from dashboard.models import (
    Notification,
    Portfolio,
    Position,
    PriceHistory,
    Share,
    Strategy,
    StrategyExecution,
    Trade,
    WatchlistItem,
)


@admin.register(Share)
class ShareAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "name",
        "figi",
        "isin",
        "currency",
        "last_price",
        "is_trend_high",
        "updated_at",
    )
    list_filter = ("currency", "is_trend_high")
    search_fields = ("figi", "isin", "name", "ticker")
    readonly_fields = ("created_at", "updated_at")
    fields = (
        "figi",
        "isin",
        "name",
        "ticker",
        "currency",
        "uid",
        "last_price",
        "is_trend_high",
        "created_at",
        "updated_at",
    )
    ordering = ("name",)
    list_per_page = 50
    date_hierarchy = "updated_at"


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    list_display = ("share", "price", "recorded_at")
    list_filter = ("share",)
    search_fields = ("share__ticker", "share__name")
    ordering = ("-recorded_at",)


@admin.register(WatchlistItem)
class WatchlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "target_price", "condition", "is_active", "triggered")
    list_filter = ("condition", "is_active", "triggered")
    search_fields = ("user__username", "share__ticker")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "share", "message", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("user__username", "message")


@admin.register(Portfolio)
class PortfolioAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "cash_balance", "created_at")
    search_fields = ("user__username", "name")


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "share", "quantity", "avg_price", "updated_at")
    search_fields = ("portfolio__name", "share__ticker")


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = ("portfolio", "share", "side", "quantity", "price", "realized_pnl", "executed_at")
    list_filter = ("side",)
    search_fields = ("portfolio__name", "share__ticker")


@admin.register(Strategy)
class StrategyAdmin(admin.ModelAdmin):
    list_display = ("user", "name", "share", "condition", "threshold", "action", "is_active", "triggered")
    list_filter = ("condition", "action", "is_active", "triggered")
    search_fields = ("user__username", "name", "share__ticker")


@admin.register(StrategyExecution)
class StrategyExecutionAdmin(admin.ModelAdmin):
    list_display = ("strategy", "success", "message", "executed_at")
    list_filter = ("success",)
