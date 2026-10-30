from decimal import Decimal

from config.settings import TINKOFF_TOKEN, logger


def get_last_data(share):
    try:
        from tinkoff.invest import Client
    except ImportError as error:
        raise RuntimeError(
            "Market data updates require the optional Tinkoff Invest SDK."
        ) from error

    with Client(TINKOFF_TOKEN) as client:
        resp = client.market_data.get_last_prices(figi=[share.figi])
        if not resp.last_prices:
            raise ValueError(f"Tinkoff returned no last price for share {share.id}")
        price = resp.last_prices[0]
        logger.info(f"Get last data for share with id {share.id}")
        return Decimal(price.price.units) + Decimal(price.price.nano) / Decimal(
            "1000000000"
        )
