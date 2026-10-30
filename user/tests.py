from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from user.forms import AuthForm, RegistrationForm

User = get_user_model()


class RegistrationFormTests(TestCase):
    def test_valid_registration_creates_user(self):
        form = RegistrationForm(
            data={
                "email": "New.User@Example.com ",
                "password1": "Str0ng!Pass2026",
                "password2": "Str0ng!Pass2026",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, "new.user@example.com")
        self.assertEqual(user.email, "new.user@example.com")
        self.assertTrue(user.check_password("Str0ng!Pass2026"))

    def test_duplicate_email_is_rejected_case_insensitively(self):
        User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="Str0ng!Pass2026",
        )
        form = RegistrationForm(
            data={
                "email": "USER@example.com",
                "password1": "Another!Pass2026",
                "password2": "Another!Pass2026",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_password_mismatch_is_reported(self):
        form = RegistrationForm(
            data={
                "email": "user@example.com",
                "password1": "Str0ng!Pass2026",
                "password2": "Different!Pass2026",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password2", form.errors)

    def test_weak_password_is_rejected(self):
        form = RegistrationForm(
            data={
                "email": "user@example.com",
                "password1": "123",
                "password2": "123",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("password1", form.errors)


class AuthFormTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="Str0ng!Pass2026",
        )

    def test_authentication_is_case_insensitive_for_email(self):
        form = AuthForm(
            data={"email": "USER@example.com", "password": "Str0ng!Pass2026"}
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.user, self.user)

    def test_invalid_credentials_are_rejected(self):
        form = AuthForm(
            data={"email": "user@example.com", "password": "wrong-password"}
        )
        self.assertFalse(form.is_valid())
        self.assertIsNone(form.user)


class AuthViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="Str0ng!Pass2026",
        )

    def test_login_page_renders(self):
        response = self.client.get(reverse("user:auth"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Войдите в профиль")

    def test_login_success_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "user@example.com", "password": "Str0ng!Pass2026"},
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertEqual(
            self.client.session["_auth_user_id"], str(self.user.pk)
        )

    def test_login_failure_shows_error(self):
        response = self.client.post(
            reverse("user:auth"),
            {"email": "user@example.com", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Неверный логин или пароль")

    def test_login_respects_safe_next_parameter(self):
        next_url = reverse("dashboard:create")
        response = self.client.post(
            f"{reverse('user:auth')}?next={next_url}",
            {
                "email": "user@example.com",
                "password": "Str0ng!Pass2026",
                "next": next_url,
            },
        )
        self.assertRedirects(response, next_url)

    def test_login_ignores_external_next_parameter(self):
        response = self.client.post(
            reverse("user:auth"),
            {
                "email": "user@example.com",
                "password": "Str0ng!Pass2026",
                "next": "https://evil.example.com/",
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))


class RegistrationViewTests(TestCase):
    def test_registration_page_renders(self):
        response = self.client.get(reverse("user:registration"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Регистрация в системе")

    def test_registration_creates_user_and_logs_in(self):
        response = self.client.post(
            reverse("user:registration"),
            {
                "email": "new@example.com",
                "password1": "Str0ng!Pass2026",
                "password2": "Str0ng!Pass2026",
            },
        )
        self.assertRedirects(response, reverse("dashboard:index"))
        user = User.objects.get(email="new@example.com")
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="user@example.com",
            email="user@example.com",
            password="Str0ng!Pass2026",
        )

    def test_logout_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("user:logout"))
        self.assertEqual(response.status_code, 405)

    def test_logout_via_post(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("user:logout"))
        self.assertRedirects(response, reverse("dashboard:index"))
        self.assertNotIn("_auth_user_id", self.client.session)
