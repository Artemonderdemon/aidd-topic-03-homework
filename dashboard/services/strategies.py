from decimal import Decimal

from django.utils import timezone

from config.settings import logger
from dashboard.models import Strategy, StrategyExecution
from dashboard.services.portfolio import execute_trade


def _condition_met(strategy):
    share = strategy.share
    if share.last_price is None:
        return False
    price = share.last_price
    if strategy.condition == Strategy.CONDITION_PRICE_ABOVE:
        return price >= strategy.threshold
    return price <= strategy.threshold


def evaluate_strategies():
    executed = 0
    for strategy in Strategy.objects.filter(is_active=True).select_related(
        "share", "portfolio", "user"
    ):
        met = _condition_met(strategy)
        if met and not strategy.triggered:
            try:
                trade = execute_trade(
                    portfolio=strategy.portfolio,
                    share=strategy.share,
                    side=strategy.action,
                    quantity=strategy.quantity,
                    price=strategy.share.last_price,
                    strategy=strategy,
                )
                StrategyExecution.objects.create(
                    strategy=strategy,
                    trade=trade,
                    success=True,
                    message=f"Исполнена сделка {strategy.action} {strategy.quantity}",
                )
                executed += 1
            except Exception as exc:  # noqa: BLE001
                StrategyExecution.objects.create(
                    strategy=strategy,
                    success=False,
                    message=str(exc),
                )
            strategy.triggered = True
            strategy.last_triggered_at = timezone.now()
            strategy.save(update_fields=["triggered", "last_triggered_at"])
        elif not met:
            strategy.triggered = False
            strategy.save(update_fields=["triggered"])
    logger.info("Strategy evaluation finished, executed=%s", executed)
    return executed
