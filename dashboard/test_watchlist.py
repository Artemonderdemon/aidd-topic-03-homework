from decimal import Decimal

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from dashboard.models import (
    AlertNotification,
    PriceAlert,
    Share,
    WatchlistItem,
)
from dashboard.services.price_alerts import process_price_alerts
from dashboard.tasks import update_last_price


class WatchlistTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            username="watcher", password="Strong!TestPassword438"
        )
        self.other_user = user_model.objects.create_user(
            username="other-watcher", password="Strong!TestPassword438"
        )
        self.share = Share.objects.create(
            figi="FIGI-WATCH",
            isin="TEST00000002",
            name="Watch Test",
            ticker="WATCH",
            currency="usd",
            uid="uid-watch",
            last_price=99,
        )
        self.item = WatchlistItem.objects.create(user=self.user, share=self.share)

    def test_watchlist_requires_login_and_is_private(self):
        response = self.client.get(reverse("dashboard:watchlist"))
        self.assertRedirects(response, reverse("dashboard:index"))

        self.client.force_login(self.other_user)
        response = self.client.get(reverse("dashboard:watchlist"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Watch Test")

    def test_watchlist_and_alert_forms_render(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard:watchlist"))
        self.assertContains(response, "Мой мониторинг акций")
        response = self.client.get(reverse("dashboard:watchlist-add"))
        self.assertContains(response, "Добавить акцию в мониторинг")
        response = self.client.get(reverse("dashboard:alert-add", args=[self.item.pk]))
        self.assertContains(response, "Целевая цена для WATCH")
        response = self.client.get(reverse("dashboard:notifications"))
        self.assertContains(response, "Уведомления о целевых ценах")

    def test_user_can_add_and_remove_share_from_watchlist(self):
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("dashboard:watchlist-add"), {"share": self.share.pk}
        )
        self.assertRedirects(response, reverse("dashboard:watchlist"))
        item = WatchlistItem.objects.get(user=self.other_user, share=self.share)

        response = self.client.post(
            reverse("dashboard:watchlist-remove", args=[item.pk])
        )
        self.assertRedirects(response, reverse("dashboard:watchlist"))
        self.assertFalse(
            WatchlistItem.objects.filter(user=self.other_user, share=self.share).exists()
        )

    def test_user_cannot_add_same_share_twice(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("dashboard:watchlist-add"), {"share": self.share.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(WatchlistItem.objects.filter(user=self.user).count(), 1)

    def test_target_alert_creates_in_app_notification_on_each_crossing(self):
        alert = PriceAlert.objects.create(
            watchlist_item=self.item, target_price=Decimal("100.00")
        )

        self.assertEqual(
            process_price_alerts(self.share, Decimal("99.00")),
            0,
        )
        self.assertEqual(process_price_alerts(self.share, Decimal("99.00")), 0)
        self.assertEqual(
            process_price_alerts(self.share, Decimal("101.00")),
            1,
        )
        self.assertEqual(process_price_alerts(self.share, Decimal("102.00")), 0)
        self.assertEqual(
            process_price_alerts(self.share, Decimal("99.00")),
            1,
        )
        self.assertEqual(alert.notifications.count(), 2)

    def test_alert_can_only_be_created_for_owned_watchlist_item(self):
        self.client.force_login(self.other_user)
        response = self.client.get(
            reverse("dashboard:alert-add", args=[self.item.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_notification_read_and_delete_are_scoped_to_owner(self):
        alert = PriceAlert.objects.create(
            watchlist_item=self.item, target_price=Decimal("100.00")
        )
        notification = AlertNotification.objects.create(
            price_alert=alert, observed_price=Decimal("101.00")
        )

        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("dashboard:notification-read", args=[notification.pk])
        )
        self.assertEqual(response.status_code, 404)
        response = self.client.post(
            reverse("dashboard:alert-remove", args=[alert.pk])
        )
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("dashboard:notification-read", args=[notification.pk])
        )
        self.assertRedirects(response, reverse("dashboard:notifications"))
        notification.refresh_from_db()
        self.assertIsNotNone(notification.read_at)

    def test_duplicate_target_is_rejected_by_form(self):
        PriceAlert.objects.create(
            watchlist_item=self.item, target_price=Decimal("100.00")
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("dashboard:alert-add", args=[self.item.pk]),
            {"target_price": "100"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Для этой целевой цены оповещение уже создано")
        self.assertEqual(self.item.price_alerts.count(), 1)

    def test_price_update_task_creates_crossing_notification(self):
        alert = PriceAlert.objects.create(
            watchlist_item=self.item,
            target_price=Decimal("100.00"),
            last_observed_above=True,
        )

        with patch(
            "dashboard.tasks.get_last_data", return_value=Decimal("99.00")
        ):
            update_last_price.run()

        self.assertEqual(alert.notifications.count(), 1)
        alert.refresh_from_db()
        self.assertFalse(alert.last_observed_above)
