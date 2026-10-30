"""Market data providers.

The public Tinkoff Invest REST API is used when a token is configured.
Without a token the application falls back to deterministic demo data so the
UI, background task and tests can run in a clean environment.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from typing import Iterable, Protocol

import httpx
from django.conf import settings
from django.utils import timezone as django_timezone

from config.settings import logger


class MarketDataError(RuntimeError):
    """Raised when market data cannot be obtained."""


@dataclass(frozen=True)
class Instrument:
    figi: str
    isin: str
    name: str
    ticker: str
    currency: str
    uid: str


@dataclass(frozen=True)
class Quote:
    price: Decimal
    time: datetime


@dataclass(frozen=True)
class Candle:
    time: datetime
    close: Decimal


class MarketDataProvider(Protocol):
    def get_shares(self) -> list[Instrument]: ...

    def get_last_price(self, figi: str) -> Quote: ...

    def get_daily_candles(self, figi: str, days: int = 180) -> list[Candle]: ...

    def close(self) -> None: ...


class DemoMarketDataProvider:
    """Deterministic data for local development and automated tests."""

    _SHARES = (
        Instrument(
            figi="BBG004730N88",
            isin="RU0009029540",
            name="Сбербанк",
            ticker="SBER",
            currency="rub",
            uid="demo-sber-uid",
        ),
        Instrument(
            figi="BBG004730RP0",
            isin="RU0007661625",
            name="Газпром",
            ticker="GAZP",
            currency="rub",
            uid="demo-gazp-uid",
        ),
        Instrument(
            figi="BBG004731032",
            isin="RU0009024277",
            name="Лукойл",
            ticker="LKOH",
            currency="rub",
            uid="demo-lkoh-uid",
        ),
        Instrument(
            figi="BBG006L8G4H1",
            isin="RU000A107662",
            name="Яндекс",
            ticker="YDEX",
            currency="rub",
            uid="demo-ydex-uid",
        ),
        Instrument(
            figi="BBG004730ZJ9",
            isin="RU0009033591",
            name="Т-Технологии",
            ticker="T",
            currency="rub",
            uid="demo-t-uid",
        ),
    )

    _BASE_PRICES = {
        "SBER": Decimal("250.00"),
        "GAZP": Decimal("135.50"),
        "LKOH": Decimal("7200.00"),
        "YDEX": Decimal("4300.00"),
        "T": Decimal("2800.00"),
    }

    def _instrument(self, figi: str) -> Instrument:
        for instrument in self._SHARES:
            if instrument.figi == figi:
                return instrument
        raise MarketDataError(f"Demo instrument with figi={figi!r} not found")

    def get_shares(self) -> list[Instrument]:
        return list(self._SHARES)

    def get_last_price(self, figi: str) -> Quote:
        instrument = self._instrument(figi)
        base = self._BASE_PRICES[instrument.ticker]
        phase = int(time.time() // 60) % 360
        delta = Decimal(str(round(math.sin(phase / 12.0) * 2.5, 2)))
        return Quote(price=max(base + delta, Decimal("0.01")), time=django_timezone.now())

    def get_daily_candles(self, figi: str, days: int = 180) -> list[Candle]:
        instrument = self._instrument(figi)
        base = self._BASE_PRICES[instrument.ticker]
        today = date.today()
        candles: list[Candle] = []
        for index in range(days):
            candle_date = today - timedelta(days=days - 1 - index)
            drift = Decimal(str(round(math.sin(index / 9.0) * 4.0, 2)))
            candles.append(
                Candle(
                    time=datetime.combine(
                        candle_date, dt_time.min, tzinfo=timezone.utc
                    ),
                    close=max(base + drift, Decimal("0.01")),
                )
            )
        return candles

    def close(self) -> None:
        return None


class TinkoffRestProvider:
    """Minimal client for the public Tinkoff Invest REST API."""

    def __init__(
        self,
        token: str,
        base_url: str,
        timeout: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        if not token:
            raise MarketDataError(
                "TINKOFF_TOKEN is required for the Tinkoff market data provider"
            )
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(
            timeout=httpx.Timeout(timeout),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )

    def close(self) -> None:
        self._client.close()

    def _post(self, service: str, method: str, payload: dict) -> dict:
        url = f"{self._base_url}/{service}/{method}"
        try:
            response = self._client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise MarketDataError(
                f"Tinkoff API returned {exc.response.status_code}: {detail}"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Tinkoff API request failed: {exc}") from exc

        if not isinstance(data, dict):
            raise MarketDataError("Tinkoff API returned an unexpected response")
        return data

    @staticmethod
    def _money_to_decimal(value: dict | None) -> Decimal:
        if not value:
            raise MarketDataError("Tinkoff API response does not contain a price")
        units = value.get("units", 0)
        nano = value.get("nano", 0)
        return Decimal(str(units)) + Decimal(str(nano)) / Decimal("1000000000")

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime:
        if not value:
            return django_timezone.now()
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    def get_shares(self) -> list[Instrument]:
        data = self._post(
            "InstrumentsService",
            "Shares",
            {"instrumentStatus": "INSTRUMENT_STATUS_BASE"},
        )
        instruments: list[Instrument] = []
        for item in data.get("instruments", []):
            figi = item.get("figi")
            ticker = item.get("ticker")
            name = item.get("name")
            uid = item.get("uid")
            if not all((figi, ticker, name, uid)):
                continue
            instruments.append(
                Instrument(
                    figi=figi,
                    isin=item.get("isin", ""),
                    name=name,
                    ticker=ticker,
                    currency=str(item.get("currency", "rub")).lower(),
                    uid=uid,
                )
            )
        return instruments

    def get_last_price(self, figi: str) -> Quote:
        data = self._post(
            "MarketDataService",
            "GetLastPrices",
            {"figi": [figi]},
        )
        prices = data.get("lastPrices", [])
        if not prices:
            raise MarketDataError(f"No last price returned for figi={figi!r}")
        item = prices[0]
        return Quote(
            price=self._money_to_decimal(item.get("price")),
            time=self._parse_datetime(item.get("time")),
        )

    def get_daily_candles(self, figi: str, days: int = 180) -> list[Candle]:
        now = django_timezone.now()
        start = now - timedelta(days=days)
        data = self._post(
            "MarketDataService",
            "GetCandles",
            {
                "figi": figi,
                "from": start.isoformat().replace("+00:00", "Z"),
                "to": now.isoformat().replace("+00:00", "Z"),
                "interval": "CANDLE_INTERVAL_DAY",
            },
        )
        candles: list[Candle] = []
        for item in data.get("candles", []):
            try:
                candles.append(
                    Candle(
                        time=self._parse_datetime(item.get("time")),
                        close=self._money_to_decimal(item.get("close")),
                    )
                )
            except (MarketDataError, TypeError, ValueError):
                logger.warning("Skipping malformed candle for figi=%s", figi)
        return candles


def get_market_data_provider() -> MarketDataProvider:
    """Return the configured provider.

    ``auto`` uses Tinkoff when a token is present and demo data otherwise.
    """
    provider = getattr(settings, "MARKET_DATA_PROVIDER", "auto").lower()

    if provider == "demo":
        return DemoMarketDataProvider()

    if provider == "tinkoff":
        return TinkoffRestProvider(
            token=settings.TINKOFF_TOKEN,
            base_url=settings.TINKOFF_API_URL,
            timeout=settings.TINKOFF_API_TIMEOUT,
        )

    if provider == "auto":
        if settings.TINKOFF_TOKEN:
            return TinkoffRestProvider(
                token=settings.TINKOFF_TOKEN,
                base_url=settings.TINKOFF_API_URL,
                timeout=settings.TINKOFF_API_TIMEOUT,
            )
        return DemoMarketDataProvider()

    raise MarketDataError(
        f"Unknown MARKET_DATA_PROVIDER={provider!r}; expected auto, tinkoff or demo"
    )


def get_last_data(
    share, provider: MarketDataProvider | None = None
) -> Quote:
    """Backward-compatible helper used by callers that only need one quote."""
    owns_provider = provider is None
    provider = provider or get_market_data_provider()
    try:
        return provider.get_last_price(share.figi)
    finally:
        if owns_provider:
            provider.close()


def iter_instruments(
    provider: MarketDataProvider | None = None,
) -> Iterable[Instrument]:
    owns_provider = provider is None
    provider = provider or get_market_data_provider()
    try:
        yield from provider.get_shares()
    finally:
        if owns_provider:
            provider.close()
