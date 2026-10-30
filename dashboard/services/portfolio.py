from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from dashboard.models import Portfolio, Position, Trade


class PortfolioServiceError(ValueError):
    pass


def execute_trade(portfolio, share, side, quantity, price, strategy=None):
    quantity = Decimal(str(quantity))
    price = Decimal(str(price))
    if quantity <= 0:
        raise PortfolioServiceError("Количество должно быть больше нуля")

    with transaction.atomic():
        if side == Trade.SIDE_BUY:
            cost = quantity * price
            if portfolio.cash_balance < cost:
                raise PortfolioServiceError("Недостаточно виртуальных средств")
            position, created = Position.objects.get_or_create(
                portfolio=portfolio,
                share=share,
                defaults={"quantity": 0, "avg_price": price},
            )
            if created:
                position.quantity = quantity
                position.avg_price = price
            else:
                total_qty = position.quantity + quantity
                position.avg_price = (
                    position.quantity * position.avg_price + quantity * price
                ) / total_qty
                position.quantity = total_qty
            position.save()
            portfolio.cash_balance -= cost
            portfolio.save(update_fields=["cash_balance", "updated_at"])
            realized = Decimal("0")
        else:
            position = Position.objects.filter(portfolio=portfolio, share=share).first()
            if position is None or position.quantity < quantity:
                raise PortfolioServiceError("Недостаточно акций для продажи")
            realized = quantity * (price - position.avg_price)
            position.quantity -= quantity
            if position.quantity == 0:
                position.delete()
            else:
                position.save()
            portfolio.cash_balance += quantity * price
            portfolio.save(update_fields=["cash_balance", "updated_at"])

        trade = Trade.objects.create(
            portfolio=portfolio,
            share=share,
            side=side,
            quantity=quantity,
            price=price,
            realized_pnl=realized,
            strategy=strategy,
            executed_at=timezone.now(),
        )
    return trade


def portfolio_summary(portfolio):
    positions = list(portfolio.positions.select_related("share"))
    market_value = sum((p.market_value for p in positions), 0.0)
    cost_basis = sum((p.cost_basis for p in positions), 0.0)
    unrealized = market_value - cost_basis
    realized = sum(float(t.realized_pnl) for t in portfolio.trades.all())
    return {
        "positions": positions,
        "market_value": market_value,
        "cost_basis": cost_basis,
        "unrealized_pnl": unrealized,
        "realized_pnl": realized,
        "total_value": market_value + float(portfolio.cash_balance),
    }
