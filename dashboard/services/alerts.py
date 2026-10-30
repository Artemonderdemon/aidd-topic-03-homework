from django.utils import timezone

from config.settings import logger
from dashboard.models import Notification, WatchlistItem


def evaluate_watchlist(user=None):
    queryset = WatchlistItem.objects.filter(is_active=True)
    if user is not None:
        queryset = queryset.filter(user=user)

    created = 0
    for item in queryset.select_related("share", "user"):
        share = item.share
        if share.last_price is None:
            continue
        price = share.last_price
        condition_met = (
            item.condition == WatchlistItem.CONDITION_ABOVE
            and price >= item.target_price
        ) or (
            item.condition == WatchlistItem.CONDITION_BELOW
            and price <= item.target_price
        )
        if condition_met and not item.triggered:
            message = (
                f"{share.ticker}: цена {price} достигла уровня {item.target_price}"
            )
            Notification.objects.create(
                user=item.user, share=share, watchlist_item=item, message=message
            )
            item.triggered = True
            item.triggered_at = timezone.now()
            item.save(update_fields=["triggered", "triggered_at"])
            created += 1
        elif not condition_met:
            item.triggered = False
            item.triggered_at = None
            item.save(update_fields=["triggered", "triggered_at"])
    logger.info("Watchlist evaluation finished, notifications=%s", created)
    return created
