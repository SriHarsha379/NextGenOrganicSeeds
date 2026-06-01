import base64
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from orders.models import Order


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_order(**kwargs):
    """Create a minimal Order for testing."""
    defaults = dict(
        full_name="Test User",
        email="test@example.com",
        phone="9999999999",
        address="123 Main St, Bengaluru",
        cart_items=[{"id": 1, "name": "Tomato Seeds", "price": 50, "quantity": 2}],
        total_quantity=2,
        total_amount=Decimal("180.00"),
        postal_charge=Decimal("80.00"),
        payment_status="Pending",
        phonepe_order_id="HF100",
    )
    defaults.update(kwargs)
    return Order.objects.create(**defaults)


def _mock_status(success=True, state="COMPLETED", payment_id="TXN123", error=None):
    return {"success": success, "state": state, "payment_id": payment_id, "error": error}


# ─────────────────────────────────────────────────────────────────────────────
# 1. Webhook — authentication
# ─────────────────────────────────────────────────────────────────────────────

class WebhookAuthTests(TestCase):
    """_verify_webhook_request: Basic-Auth logic."""

    def _post(self, body, headers=None):
        c = Client()
        kwargs = {"content_type": "application/json"}
        if headers:
            kwargs["HTTP_AUTHORIZATION"] = headers
        return c.post("/phonepe/webhook/", data=json.dumps(body), **kwargs)

    @patch("cart.views.settings")
    def test_no_credentials_configured_passes(self, mock_settings):
        """When no PHONEPE_WEBHOOK_USER set, webhook is permissive."""
        mock_settings.PHONEPE_WEBHOOK_USER = ""
        mock_settings.PHONEPE_WEBHOOK_PASSWORD = ""
        mock_settings.DEFAULT_FROM_EMAIL = "from@test.com"
        mock_settings.ADMIN_NOTIFICATION_EMAIL = "admin@test.com"

        _make_order(phonepe_order_id="HF001")

        payload = {"event": "checkout.order.failed", "payload": {"merchantOrderId": "HF001"}}
        with patch("cart.views._check_phonepe_payment_status"):
            resp = self._post(payload)
        # Should reach the handler (not 401)
        self.assertNotEqual(resp.status_code, 401)

    @patch("cart.views.settings")
    def test_wrong_credentials_rejected(self, mock_settings):
        mock_settings.PHONEPE_WEBHOOK_USER = "admin"
        mock_settings.PHONEPE_WEBHOOK_PASSWORD = "secret"

        token = base64.b64encode(b"admin:wrongpassword").decode()
        resp = self._post({"event": "checkout.order.completed"}, headers=f"Basic {token}")
        self.assertEqual(resp.status_code, 401)

    @patch("cart.views.settings")
    def test_correct_credentials_accepted(self, mock_settings):
        mock_settings.PHONEPE_WEBHOOK_USER = "admin"
        mock_settings.PHONEPE_WEBHOOK_PASSWORD = "secret"
        mock_settings.DEFAULT_FROM_EMAIL = "from@test.com"
        mock_settings.ADMIN_NOTIFICATION_EMAIL = "admin@test.com"

        _make_order(phonepe_order_id="HF002")
        token = base64.b64encode(b"admin:secret").decode()
        payload = {"event": "checkout.order.failed", "payload": {"merchantOrderId": "HF002"}}
        with patch("cart.views._check_phonepe_payment_status"):
            resp = self._post(payload, headers=f"Basic {token}")
        self.assertNotEqual(resp.status_code, 401)

    @patch("cart.views.settings")
    def test_missing_auth_header_rejected(self, mock_settings):
        mock_settings.PHONEPE_WEBHOOK_USER = "admin"
        mock_settings.PHONEPE_WEBHOOK_PASSWORD = "secret"

        resp = self._post({"event": "checkout.order.completed"})
        self.assertEqual(resp.status_code, 401)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Webhook — payload parsing
# ─────────────────────────────────────────────────────────────────────────────

class WebhookPayloadParsingTests(TestCase):

    def _post_no_auth(self, body):
        with patch("cart.views._verify_webhook_request", return_value=True):
            return Client().post(
                "/phonepe/webhook/",
                data=json.dumps(body),
                content_type="application/json",
            )

    def test_invalid_json_returns_400(self):
        with patch("cart.views._verify_webhook_request", return_value=True):
            resp = Client().post("/phonepe/webhook/", data="not-json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_unknown_event_ignored_200(self):
        resp = self._post_no_auth({"event": "some.unknown.event", "payload": {}})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Ignored", resp.json()["message"])

    def test_missing_merchant_order_id_returns_400(self):
        resp = self._post_no_auth({"event": "checkout.order.completed", "payload": {}})
        self.assertEqual(resp.status_code, 400)

    def test_get_method_not_allowed(self):
        with patch("cart.views._verify_webhook_request", return_value=True):
            resp = Client().get("/phonepe/webhook/")
        self.assertEqual(resp.status_code, 405)

    def test_nested_payload_string_parsed(self):
        """payload field may itself be a JSON-encoded string."""
        inner = json.dumps({"merchantOrderId": "HF999"})
        resp = self._post_no_auth({"event": "checkout.order.cancelled", "payload": inner})
        # Order doesn't exist yet — should 404 (not 400 / 500)
        self.assertEqual(resp.status_code, 404)

    def test_flat_body_merchant_order_id(self):
        """merchantOrderId may be at the top level of the body."""
        resp = self._post_no_auth({
            "event": "checkout.order.cancelled",
            "merchantOrderId": "HF888",
        })
        self.assertEqual(resp.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Webhook — Completed event → order → Paid
# ─────────────────────────────────────────────────────────────────────────────

class WebhookCompletedTests(TestCase):

    def setUp(self):
        self.order = _make_order(phonepe_order_id="HF200")

    def _post_completed(self, merchant_id="HF200", payment_details=None):
        payload = {
            "event": "checkout.order.completed",
            "payload": {
                "merchantOrderId": merchant_id,
                "paymentDetails": payment_details or [{"transactionId": "TXN_ABC"}],
            },
        }
        with patch("cart.views._verify_webhook_request", return_value=True):
            return Client().post(
                "/phonepe/webhook/",
                data=json.dumps(payload),
                content_type="application/json",
            )

    @patch("cart.views._check_phonepe_payment_status")
    @patch("cart.views._send_order_status_emails")
    def test_order_marked_paid(self, mock_email, mock_status):
        """Core test: completed webhook changes order status to Paid."""
        mock_status.return_value = _mock_status(success=True, payment_id="TXN_ABC")

        resp = self._post_completed()

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "Paid")
        self.assertEqual(self.order.payment_id, "TXN_ABC")

    @patch("cart.views._check_phonepe_payment_status")
    @patch("cart.views._send_order_status_emails")
    def test_confirmation_email_sent_on_paid(self, mock_email, mock_status):
        """Email helper must be called exactly once when status changes to Paid."""
        mock_status.return_value = _mock_status(success=True, payment_id="TXN_ABC")

        self._post_completed()

        mock_email.assert_called_once_with(self.order, "Paid")

    @patch("cart.views._check_phonepe_payment_status")
    def test_email_content_on_paid(self, mock_status):
        """Using Django's test email backend, verify email body text."""
        mock_status.return_value = _mock_status(success=True, payment_id="TXN_REAL")

        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            DEFAULT_FROM_EMAIL="Hasa Farm <orders@hasafarm.com>",
            ADMIN_NOTIFICATION_EMAIL="admin@hasafarm.com",
            PHONEPE_WEBHOOK_USER="",
            PHONEPE_WEBHOOK_PASSWORD="",
        ):
            with patch("cart.views._verify_webhook_request", return_value=True):
                resp = Client().post(
                    "/phonepe/webhook/",
                    data=json.dumps({
                        "event": "checkout.order.completed",
                        "payload": {"merchantOrderId": "HF200"},
                    }),
                    content_type="application/json",
                )

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)  # customer + admin

        customer_email = mail.outbox[0]
        self.assertIn("test@example.com", customer_email.to)
        self.assertIn("Order Confirmed", customer_email.subject)
        self.assertIn("TXN_REAL", customer_email.body)

        admin_email = mail.outbox[1]
        self.assertIn("admin@hasafarm.com", admin_email.to)

    @patch("cart.views._check_phonepe_payment_status")
    @patch("cart.views._send_order_status_emails")
    def test_idempotent_duplicate_webhook_no_second_email(self, mock_email, mock_status):
        """Second identical webhook must not change status or send another email."""
        mock_status.return_value = _mock_status(success=True, payment_id="TXN_ABC")

        self._post_completed()
        mock_email.reset_mock()
        resp = self._post_completed()  # send again

        self.assertEqual(resp.status_code, 200)
        self.assertIn("No change needed", resp.json()["message"])
        mock_email.assert_not_called()

    @patch("cart.views._check_phonepe_payment_status")
    @patch("cart.views._send_order_status_emails")
    def test_timing_race_status_api_lag_still_marks_paid(self, mock_email, mock_status):
        """Bug 1 fix: even if status API returns state!=COMPLETED, webhook is trusted."""
        mock_status.return_value = _mock_status(success=False, state="PENDING", payment_id=None)

        resp = self._post_completed()

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "Paid")

    @patch("cart.views._check_phonepe_payment_status")
    def test_status_api_exception_returns_500(self, mock_status):
        """Bug 1 fix: API call failure → 500 so PhonePe retries."""
        mock_status.return_value = _mock_status(success=False, error="Connection refused")

        resp = self._post_completed()

        self.assertEqual(resp.status_code, 500)
        # Order must NOT be changed
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "Pending")

    @patch("cart.views._check_phonepe_payment_status")
    @patch("cart.views._send_order_status_emails")
    def test_payment_id_from_webhook_payload_used_when_api_returns_none(self, mock_email, mock_status):
        """Falls back to paymentDetails[].transactionId in webhook body."""
        mock_status.return_value = _mock_status(success=True, payment_id=None)

        resp = self._post_completed(payment_details=[{"transactionId": "FALLBACK_TXN"}])

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_id, "FALLBACK_TXN")

    def test_order_not_found_returns_404(self):
        with patch("cart.views._verify_webhook_request", return_value=True):
            with patch("cart.views._check_phonepe_payment_status", return_value=_mock_status()):
                resp = Client().post(
                    "/phonepe/webhook/",
                    data=json.dumps({"event": "checkout.order.completed",
                                     "payload": {"merchantOrderId": "HF_NONEXISTENT"}}),
                    content_type="application/json",
                )
        self.assertEqual(resp.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Webhook — Failed / Cancelled events
# ─────────────────────────────────────────────────────────────────────────────

class WebhookFailedCancelledTests(TestCase):

    def setUp(self):
        self.order = _make_order(phonepe_order_id="HF300")

    def _post_event(self, event):
        with patch("cart.views._verify_webhook_request", return_value=True):
            return Client().post(
                "/phonepe/webhook/",
                data=json.dumps({"event": event, "payload": {"merchantOrderId": "HF300"}}),
                content_type="application/json",
            )

    @patch("cart.views._send_order_status_emails")
    def test_failed_event_marks_order_failed(self, mock_email):
        resp = self._post_event("checkout.order.failed")
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "Failed")
        mock_email.assert_called_once_with(self.order, "Failed")

    @patch("cart.views._send_order_status_emails")
    def test_cancelled_event_marks_order_cancelled(self, mock_email):
        resp = self._post_event("checkout.order.cancelled")
        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "Cancelled")
        mock_email.assert_called_once_with(self.order, "Cancelled")


# ─────────────────────────────────────────────────────────────────────────────
# 5. order_success — authorization & status update
# ─────────────────────────────────────────────────────────────────────────────

class OrderSuccessTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.order = _make_order(phonepe_order_id="HF400", payment_status="Pending")

    def _url(self, pid="HF400"):
        return reverse("order_success", args=[pid])

    def test_guest_order_accessible_without_session(self):
        """Bug 2 fix: guest orders (user=None) do not require session auth."""
        with patch("cart.views._check_phonepe_payment_status",
                   return_value=_mock_status(success=False, state="PENDING")):
            resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

    def test_guest_order_still_pending_shows_pending_flag(self):
        with patch("cart.views._check_phonepe_payment_status",
                   return_value=_mock_status(success=False, state="PENDING")):
            resp = self.client.get(self._url())
        self.assertContains(resp, "", status_code=200)
        self.assertTrue(resp.context["pending"])

    @patch("cart.views._check_phonepe_payment_status")
    @patch("cart.views._send_order_status_emails")
    def test_guest_order_marked_paid_on_success_page(self, mock_email, mock_status):
        """order_success updates DB when PhonePe confirms COMPLETED."""
        mock_status.return_value = _mock_status(success=True, payment_id="TXN_SS")

        resp = self.client.get(self._url())

        self.assertEqual(resp.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, "Paid")
        mock_email.assert_called_once()

    def test_registered_user_order_requires_ownership(self):
        """Registered-user orders with a different logged-in user → 403."""
        owner = User.objects.create_user("owner", password="pass")
        other = User.objects.create_user("other", password="pass")
        self.order.user = owner
        self.order.save(update_fields=["user"])

        self.client.force_login(other)
        with patch("cart.views._check_phonepe_payment_status",
                   return_value=_mock_status(success=False)):
            resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 403)

    def test_registered_user_owner_can_access(self):
        owner = User.objects.create_user("owner2", password="pass")
        self.order.user = owner
        self.order.save(update_fields=["user"])

        self.client.force_login(owner)
        with patch("cart.views._check_phonepe_payment_status",
                   return_value=_mock_status(success=False, state="PENDING")):
            resp = self.client.get(self._url())
        self.assertEqual(resp.status_code, 200)

    def test_nonexistent_order_returns_404(self):
        resp = self.client.get(self._url("HF_MISSING"))
        self.assertEqual(resp.status_code, 404)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Order model — partial save does not recompute total_quantity
# ─────────────────────────────────────────────────────────────────────────────

class OrderModelTests(TestCase):

    def test_full_save_recomputes_total_quantity(self):
        order = _make_order(phonepe_order_id="HF500", total_quantity=0)
        order.cart_items = [
            {"id": 1, "name": "A", "price": 10, "quantity": 3},
            {"id": 2, "name": "B", "price": 20, "quantity": 2},
        ]
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.total_quantity, 5)

    def test_partial_save_does_not_recompute_total_quantity(self):
        # Create order — full save computes total_quantity from cart_items (2 items)
        order = _make_order(phonepe_order_id="HF501")
        order.refresh_from_db()
        saved_quantity = order.total_quantity  # 2, from the cart_items fixture

        # Now change cart_items in-memory to empty, but only partial-save payment fields
        order.cart_items = []
        order.payment_status = "Paid"
        order.save(update_fields=["payment_status", "payment_id"])
        order.refresh_from_db()
        # total_quantity in DB must still be saved_quantity — not recomputed from empty cart_items
        self.assertEqual(order.total_quantity, saved_quantity)
        self.assertEqual(order.payment_status, "Paid")


# ─────────────────────────────────────────────────────────────────────────────
# 7. Email content
# ─────────────────────────────────────────────────────────────────────────────

class EmailContentTests(TestCase):
    """Verify that _send_order_status_emails dispatches correct email text."""

    def _run(self, status):
        from cart.views import _send_order_status_emails
        order = _make_order(phonepe_order_id=f"HF6{status[:2]}", payment_status=status)
        order.payment_id = "TXN_MAIL"
        with self.settings(
            EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
            DEFAULT_FROM_EMAIL="Hasa Farm <orders@hasafarm.com>",
            ADMIN_NOTIFICATION_EMAIL="admin@hasafarm.com",
        ):
            _send_order_status_emails(order, status)
        return mail.outbox

    def test_paid_customer_email_contains_order_details(self):
        outbox = self._run("Paid")
        self.assertEqual(len(outbox), 2)
        customer_mail = outbox[0]
        body = customer_mail.body
        self.assertIn("Order Confirmed", customer_mail.subject)
        self.assertIn("TXN_MAIL", body)
        self.assertIn("Tomato Seeds", body)
        # Customer email must also carry an HTML alternative
        self.assertTrue(customer_mail.alternatives)
        self.assertIn("text/html", customer_mail.alternatives[0][1])
        self.assertIn("Order #", customer_mail.alternatives[0][0])

    def test_cancelled_customer_email(self):
        outbox = self._run("Cancelled")
        self.assertIn("Cancelled", outbox[0].subject)
        self.assertTrue(outbox[0].alternatives)
        self.assertIn("text/html", outbox[0].alternatives[0][1])

    def test_failed_customer_email(self):
        outbox = self._run("Failed")
        self.assertIn("Failed", outbox[0].subject)
        self.assertTrue(outbox[0].alternatives)
        self.assertIn("text/html", outbox[0].alternatives[0][1])

    def test_admin_always_notified(self):
        outbox = self._run("Paid")
        admin_mail = outbox[1]
        self.assertIn("admin@hasafarm.com", admin_mail.to)
        self.assertIn("Paid", admin_mail.subject)
        self.assertTrue(admin_mail.alternatives)
        self.assertIn("text/html", admin_mail.alternatives[0][1])
        self.assertIn("Order #", admin_mail.alternatives[0][0])
