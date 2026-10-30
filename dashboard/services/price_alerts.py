from decimal import Decimal

from django.db import transaction

from dashboard.models import AlertNotification, PriceAlert, Share


def process_price_alerts(share: Share, observed_price: Decimal) -> int:
    """Create one notification whenever an observed price crosses a target."""
    notification_count = 0

    with transaction.atomic():
        alerts = (
            PriceAlert.objects.select_for_update()
            .filter(watchlist_item__share=share, is_active=True)
            .select_related("watchlist_item")
        )
        for alert in alerts:
            current_side = observed_price >= alert.target_price
            if (
                alert.last_observed_above is not None
                and alert.last_observed_above != current_side
            ):
                AlertNotification.objects.create(
                    price_alert=alert,
                    observed_price=observed_price,
                )
                notification_count += 1

            if alert.last_observed_above != current_side:
                alert.last_observed_above = current_side
                alert.save(update_fields=("last_observed_above",))

    return notification_count
