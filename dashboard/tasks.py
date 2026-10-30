from config.celery import app
from config.settings import logger

from dashboard.models import PriceHistory, Share
from dashboard.services.alerts import evaluate_watchlist
from dashboard.services.market_data import get_market_data_provider
from dashboard.services.strategies import evaluate_strategies


@app.task(ignore_result=True)
def update_last_price() -> dict[str, int]:
    """Update the last price and trend flag for every share."""
    try:
        provider = get_market_data_provider()
    except Exception:
        logger.exception("Cannot initialize market data provider")
        return {"updated": 0, "failed": 0}

    updated = 0
    failed = 0
    try:
        for share in Share.objects.all().iterator(chunk_size=500):
            try:
                quote = provider.get_last_price(share.figi)
                previous = share.last_price
                share.last_price = quote.price
                share.is_trend_high = (
                    None if previous is None else quote.price >= previous
                )
                share.save(
                    update_fields=["last_price", "is_trend_high", "updated_at"]
                )
                PriceHistory.objects.create(
                    share=share, price=quote.price, recorded_at=quote.time
                )
                updated += 1
                logger.info(
                    "Updated price for share id=%s ticker=%s: %s",
                    share.pk,
                    share.ticker,
                    quote.price,
                )
            except Exception:
                failed += 1
                logger.exception(
                    "Failed to update price for share id=%s ticker=%s",
                    share.pk,
                    share.ticker,
                )
    finally:
        provider.close()

    return {"updated": updated, "failed": failed}


@app.task(ignore_result=True)
def evaluate_watchlists() -> int:
    return evaluate_watchlist()


@app.task(ignore_result=True)
def run_strategies() -> int:
    return evaluate_strategies()
