from decimal import Decimal
from django.contrib.auth import get_user_model
User = get_user_model()
from io import StringIO
from unittest.mock import patch

import httpx
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from dashboard.forms import ShareModelForm
from dashboard.models import (
    Notification,
    Portfolio,
    Position,
    PriceHistory,
    Strategy,
    Trade,
    WatchlistItem,
)
from dashboard.services.alerts import evaluate_watchlist
from dashboard.services.portfolio import execute_trade
from dashboard.services.strategies import evaluate_strategies
from dashboard.models import Share
from dashboard.services.graph import get_graph
from dashboard.services.market_data import (
    Candle,
    DemoMarketDataProvider,
    Instrument,
    MarketDataError,
    Quote,
    TinkoffRestProvider,
)
from dashboard.tasks import update_last_price


def make_share(**overrides) -> Share:
    data = {
        "figi": "BBG000000001",
        "isin": "RU0000000001",
        "name": "Сбербанк",
        "ticker": "SBER",
        "currency": "rub",
        "uid": "uid-sber",
        "last_price": Decimal("250.50"),
        "is_trend_high": True,
    }
    data.update(overrides)
    return Share.objects.create(**data)


class ShareModelTests(TestCase):
    def test_str_and_unique_constraints(self):
        share = make_share()
        self.assertEqual(str(share), "SBER — Сбербанк")
        with self.assertRaises(Exception):
            make_share(name="Другой", ticker="OTHER", uid="other-uid")


class ShareFormTests(TestCase):
    def test_price_and_trend_are_not_user_editable(self):
        form = ShareModelForm()
        self.assertNotIn("last_price", form.fields)
        self.assertNotIn("is_trend_high", form.fields)
        self.assertIn("uid", form.fields)

    def test_ticker_is_normalized(self):
        form = ShareModelForm(
            data={
                "figi": "BBG1",
                "isin": "RU1",
                "name": "Test",
                "ticker": " test ",
                "currency": " RUB ",
                "uid": "uid-1",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["ticker"], "TEST")
        self.assertEqual(form.cleaned_data["currency"], "rub")


class DashboardViewTests(TestCase):
    def setUp(self):
        self.share = make_share()

    def test_list_is_public(self):
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SBER")

    def test_detail_is_public(self):
        with patch("dashboard.views.get_graph", return_value="<div>plot</div>"):
            response = self.client.get(
                reverse("dashboard:detail", kwargs={"pk": self.share.pk})
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Сбербанк")
        self.assertContains(response, "plot")

    def test_detail_missing_returns_404(self):
        response = self.client.get(
            reverse("dashboard:detail", kwargs={"pk": 99999})
        )
        self.assertEqual(response.status_code, 404)

    def test_detail_handles_market_data_error(self):
        with patch(
            "dashboard.views.get_graph",
            side_effect=MarketDataError("provider failed"),
        ):
            response = self.client.get(
                reverse("dashboard:detail", kwargs={"pk": self.share.pk})
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "График временно недоступен")

    def test_create_requires_login(self):
        response = self.client.get(reverse("dashboard:create"))
        self.assertRedirects(
            response,
            f"{reverse('user:auth')}?next={reverse('dashboard:create')}",
        )

    def test_create_update_delete_as_authenticated_user(self):
        self.client.force_login(
            self._create_user(email="user@example.com", password="Str0ng!Pass2026")
        )

        response = self.client.post(
            reverse("dashboard:create"),
            {
                "figi": "BBG2",
                "isin": "RU2",
                "name": "Новая акция",
                "ticker": "NEW",
                "currency": "rub",
                "uid": "uid-new",
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        created = Share.objects.get(ticker="NEW")

        response = self.client.post(
            reverse("dashboard:update", kwargs={"pk": created.pk}),
            {
                "figi": "BBG2",
                "isin": "RU2",
                "name": "Обновлённая акция",
                "ticker": "NEW",
                "currency": "rub",
                "uid": "uid-new",
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        created.refresh_from_db()
        self.assertEqual(created.name, "Обновлённая акция")

        response = self.client.post(
            reverse("dashboard:delete", kwargs={"pk": created.pk})
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertFalse(Share.objects.filter(pk=created.pk).exists())

    def test_health(self):
        response = self.client.get(reverse("dashboard:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @staticmethod
    def _create_user(email, password):
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username=email, email=email, password=password
        )


class ShareApiTests(APITestCase):
    def setUp(self):
        self.share = make_share()
        self.user = self._create_user()

    @staticmethod
    def _create_user():
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(
            username="api@example.com",
            email="api@example.com",
            password="Str0ng!Pass2026",
        )

    def test_anonymous_can_read(self):
        response = self.client.get("/api/v1/shares/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_anonymous_cannot_write(self):
        response = self.client.post(
            "/api/v1/shares/",
            {
                "figi": "BBG3",
                "isin": "RU3",
                "name": "Test",
                "ticker": "TST",
                "currency": "rub",
                "uid": "uid-test",
            },
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_authenticated_crud_including_uid(self):
        self.client.force_authenticate(self.user)
        payload = {
            "figi": "BBG3",
            "isin": "RU3",
            "name": "Test",
            "ticker": "TST",
            "currency": "rub",
            "uid": "uid-test",
            "last_price": "999.99",
        }
        response = self.client.post("/api/v1/shares/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["uid"], "uid-test")
        self.assertIsNone(response.data["last_price"])
        share_id = response.data["id"]

        response = self.client.patch(
            f"/api/v1/shares/{share_id}/",
            {"name": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated")

        response = self.client.delete(f"/api/v1/shares/{share_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_detail_missing_returns_404(self):
        response = self.client.get("/api/v1/shares/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_search_ordering_and_pagination(self):
        make_share(
            figi="BBG000000002",
            isin="RU0000000002",
            name="Газпром",
            ticker="GAZP",
            uid="uid-gazp",
        )
        response = self.client.get("/api/v1/shares/?ticker=GAZP")
        self.assertEqual(response.data["count"], 1)

        response = self.client.get("/api/v1/shares/?search=SBE")
        self.assertEqual(response.data["count"], 1)

        response = self.client.get("/api/v1/shares/?ordering=-ticker")
        self.assertEqual(response.data["results"][0]["ticker"], "SBER")

        response = self.client.get("/api/v1/shares/?limit=1")
        self.assertEqual(len(response.data["results"]), 1)
        self.assertIsNotNone(response.data["next"])


class FakeProvider:
    def __init__(self, price=Decimal("150.00"), fail_for=None):
        self.price = price
        self.fail_for = fail_for
        self.closed = False

    def get_last_price(self, figi):
        if self.fail_for and figi == self.fail_for:
            raise MarketDataError("boom")
        return Quote(price=self.price, time=timezone.now())

    def get_daily_candles(self, figi, days=180):
        return [
            Candle(
                time=timezone.now(),
                close=Decimal("100.00"),
            ),
            Candle(
                time=timezone.now(),
                close=Decimal("101.00"),
            ),
        ]

    def get_shares(self):
        return [
            Instrument(
                figi="BBG1",
                isin="RU1",
                name="Test",
                ticker="TST",
                currency="rub",
                uid="uid-1",
            )
        ]

    def close(self):
        self.closed = True


class UpdatePriceTaskTests(TestCase):
    def setUp(self):
        self.share = make_share(last_price=Decimal("100.00"), is_trend_high=False)
        self.provider = FakeProvider()

    def test_updates_price_trend_and_timestamp(self):
        old_updated_at = self.share.updated_at
        with patch(
            "dashboard.tasks.get_market_data_provider",
            return_value=self.provider,
        ):
            result = update_last_price.run()

        self.share.refresh_from_db()
        self.assertEqual(result, {"updated": 1, "failed": 0})
        self.assertEqual(self.share.last_price, Decimal("150.000000000"))
        self.assertTrue(self.share.is_trend_high)
        self.assertGreater(self.share.updated_at, old_updated_at)
        self.assertTrue(self.provider.closed)

    def test_first_price_has_unknown_trend(self):
        self.share.last_price = None
        self.share.save(update_fields=["last_price"])
        with patch(
            "dashboard.tasks.get_market_data_provider",
            return_value=self.provider,
        ):
            update_last_price.run()

        self.share.refresh_from_db()
        self.assertIsNone(self.share.is_trend_high)

    def test_failure_does_not_stop_other_shares(self):
        make_share(
            figi="BBG2",
            isin="RU2",
            name="Second",
            ticker="SEC",
            uid="uid-2",
            last_price=Decimal("10.00"),
        )
        provider = FakeProvider(fail_for=self.share.figi)
        with patch(
            "dashboard.tasks.get_market_data_provider",
            return_value=provider,
        ):
            result = update_last_price.run()

        self.assertEqual(result, {"updated": 1, "failed": 1})


class AddSharesCommandTests(TestCase):
    def test_import_creates_and_updates_without_duplicates(self):
        provider = FakeProvider()
        with patch(
            "dashboard.management.commands.add_shares.get_market_data_provider",
            return_value=provider,
        ):
            stdout = StringIO()
            call_command("add_shares", stdout=stdout)

        self.assertEqual(Share.objects.count(), 1)
        self.assertIn("created=1", stdout.getvalue())

        provider.get_shares = lambda: [
            Instrument(
                figi="BBG1",
                isin="RU1",
                name="Updated",
                ticker="TST",
                currency="rub",
                uid="uid-1",
            )
        ]
        with patch(
            "dashboard.management.commands.add_shares.get_market_data_provider",
            return_value=provider,
        ):
            stdout = StringIO()
            call_command("add_shares", stdout=stdout)

        self.assertEqual(Share.objects.count(), 1)
        self.assertEqual(Share.objects.get().name, "Updated")
        self.assertIn("updated=1", stdout.getvalue())


class MarketDataProviderTests(SimpleTestCase):
    def test_demo_provider(self):
        provider = DemoMarketDataProvider()
        shares = provider.get_shares()
        self.assertEqual(len(shares), 5)
        quote = provider.get_last_price(shares[0].figi)
        self.assertIsInstance(quote.price, Decimal)
        self.assertEqual(len(provider.get_daily_candles(shares[0].figi)), 180)

    def test_tinkoff_rest_provider_parses_responses(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/Shares"):
                return httpx.Response(
                    200,
                    json={
                        "instruments": [
                            {
                                "figi": "BBG1",
                                "isin": "RU1",
                                "name": "Test",
                                "ticker": "TST",
                                "currency": "rub",
                                "uid": "uid-1",
                            }
                        ]
                    },
                )
            if request.url.path.endswith("/GetLastPrices"):
                return httpx.Response(
                    200,
                    json={
                        "lastPrices": [
                            {
                                "figi": "BBG1",
                                "price": {"units": "100", "nano": 500000000},
                                "time": "2026-10-24T10:00:00Z",
                            }
                        ]
                    },
                )
            if request.url.path.endswith("/GetCandles"):
                return httpx.Response(
                    200,
                    json={
                        "candles": [
                            {
                                "time": "2026-10-24T00:00:00Z",
                                "close": {"units": "101", "nano": 250000000},
                            }
                        ]
                    },
                )
            return httpx.Response(404)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        provider = TinkoffRestProvider(
            token="token",
            base_url="https://example.test/rest",
            client=client,
        )
        self.assertEqual(provider.get_shares()[0].ticker, "TST")
        self.assertEqual(provider.get_last_price("BBG1").price, Decimal("100.5"))
        self.assertEqual(
            provider.get_daily_candles("BBG1")[0].close, Decimal("101.25")
        )
        provider.close()

    def test_tinkoff_rest_provider_reports_http_error(self):
        client = httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(500, text="error")
            )
        )
        provider = TinkoffRestProvider(
            token="token",
            base_url="https://example.test/rest",
            client=client,
        )
        with self.assertRaises(MarketDataError):
            provider.get_shares()
        provider.close()


class GraphTests(SimpleTestCase):
    def test_graph_html_contains_plotly(self):
        share = Share(
            figi="BBG1",
            isin="RU1",
            name="Test",
            ticker="TST",
            currency="rub",
            uid="uid-1",
        )
        html = get_graph(share, provider=FakeProvider())
        self.assertIn("plotly", html.lower())
        self.assertIn("TST", html)


class NewFeatureModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="tester@example.com",
            email="tester@example.com",
            password="Str0ng!Pass2026",
        )
        self.share = make_share()

    def test_price_history_created(self):
        PriceHistory.objects.create(share=self.share, price=Decimal("10.5"))
        self.assertEqual(self.share.price_history.count(), 1)

    def test_watchlist_trigger_creates_notification(self):
        item = WatchlistItem.objects.create(
            user=self.user,
            share=self.share,
            target_price=Decimal("100.00"),
            condition=WatchlistItem.CONDITION_ABOVE,
        )
        self.share.last_price = Decimal("150.00")
        self.share.save(update_fields=["last_price"])
        created = evaluate_watchlist(self.user)
        self.assertEqual(created, 1)
        self.assertTrue(Notification.objects.filter(user=self.user).exists())
        item.refresh_from_db()
        self.assertTrue(item.triggered)

    def test_portfolio_trade_buy_and_sell(self):
        portfolio = Portfolio.objects.create(user=self.user, name="Main")
        buy = execute_trade(
            portfolio=portfolio,
            share=self.share,
            side=Trade.SIDE_BUY,
            quantity=Decimal("2"),
            price=Decimal("100"),
        )
        self.assertEqual(buy.side, Trade.SIDE_BUY)
        position = Position.objects.get(portfolio=portfolio, share=self.share)
        self.assertEqual(position.quantity, Decimal("2"))
        sell = execute_trade(
            portfolio=portfolio,
            share=self.share,
            side=Trade.SIDE_SELL,
            quantity=Decimal("1"),
            price=Decimal("120"),
        )
        self.assertEqual(sell.realized_pnl, Decimal("20"))
        position.refresh_from_db()
        self.assertEqual(position.quantity, Decimal("1"))

    def test_strategy_creates_trade(self):
        portfolio = Portfolio.objects.create(user=self.user, name="Main")
        Strategy.objects.create(
            user=self.user,
            portfolio=portfolio,
            share=self.share,
            name="Buy high",
            condition=Strategy.CONDITION_PRICE_ABOVE,
            threshold=Decimal("10"),
            action=Strategy.ACTION_BUY,
            quantity=Decimal("1"),
        )
        self.share.last_price = Decimal("150")
        self.share.save(update_fields=["last_price"])
        executed = evaluate_strategies()
        self.assertEqual(executed, 1)
        self.assertEqual(Trade.objects.filter(portfolio=portfolio).count(), 1)


