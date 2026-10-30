from django.core.management.base import BaseCommand
from django.db import IntegrityError

from config.settings import logger
from dashboard.models import Share
from dashboard.services.market_data import get_market_data_provider


class Command(BaseCommand):
    help = "Import or update the share catalogue from the market data provider"

    def handle(self, *args, **options):
        try:
            provider = get_market_data_provider()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Cannot initialize provider: {exc}"))
            return

        created = 0
        updated = 0
        skipped = 0
        try:
            for instrument in provider.get_shares():
                try:
                    _, was_created = Share.objects.update_or_create(
                        figi=instrument.figi,
                        defaults={
                            "isin": instrument.isin,
                            "name": instrument.name,
                            "ticker": instrument.ticker,
                            "currency": instrument.currency,
                            "uid": instrument.uid,
                        },
                    )
                except IntegrityError as exc:
                    skipped += 1
                    logger.warning(
                        "Skipping share %s (%s): %s",
                        instrument.ticker,
                        instrument.figi,
                        exc,
                    )
                    continue

                if was_created:
                    created += 1
                else:
                    updated += 1
        except Exception as exc:
            self.stderr.write(
                self.style.ERROR(f"Failed to import shares: {exc}")
            )
            return
        finally:
            provider.close()

        self.stdout.write(
            self.style.SUCCESS(
                f"Shares processed: created={created}, updated={updated}, "
                f"skipped={skipped}"
            )
        )
