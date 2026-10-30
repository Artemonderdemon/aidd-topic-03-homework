from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AuthenticationViewTests(TestCase):
    def test_registration_normalizes_email_and_logs_user_in(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": " Test.User@example.com ",
                "password1": "Strong!TestPassword438",
                "password2": "Strong!TestPassword438",
            },
        )

        self.assertRedirects(response, reverse("dashboard:index"))
        user = get_user_model().objects.get(email="test.user@example.com")
        self.assertEqual(int(self.client.session["_auth_user_id"]), user.pk)

    def test_registration_shows_password_mismatch_error(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "test@example.com",
                "password1": "Strong!TestPassword438",
                "password2": "Different!Password438",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Введенные пароли не совпадают.")
        self.assertFalse(
            get_user_model().objects.filter(email="test@example.com").exists()
        )

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        get_user_model().objects.create_user(
            username="existing@example.com",
            email="existing@example.com",
            password="Strong!TestPassword438",
        )

        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "EXISTING@example.com",
                "password1": "Strong!TestPassword438",
                "password2": "Strong!TestPassword438",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Данный e-mail уже зарегистрирован")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_invalid_login_form_does_not_raise_key_error(self):
        response = self.client.post(reverse("user:auth"), {"email": "invalid"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid email address")

    def test_logout_route_is_reachable(self):
        response = self.client.get(reverse("user:logout"))

        self.assertRedirects(response, reverse("dashboard:index"))
