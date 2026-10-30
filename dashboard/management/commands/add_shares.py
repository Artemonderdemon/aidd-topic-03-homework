from django.core.management.base import BaseCommand

from config.settings import TINKOFF_TOKEN
from dashboard.models import Share


class Command(BaseCommand):
    help = "Add shares to DB"

    def handle(self, *args, **options):
        try:
            from tinkoff.invest import Client
        except ImportError as error:
            raise RuntimeError(
                "Importing shares requires the optional Tinkoff Invest SDK."
            ) from error

        with Client(TINKOFF_TOKEN) as client:
            shares = client.instruments.shares()
            for share in shares.instruments:
                Share.objects.get_or_create(
                    figi=share.figi,
                    name=share.name,
                    isin=share.isin,
                    ticker=share.ticker,
                    currency=share.currency,
                    uid=share.uid,
                )

