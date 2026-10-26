import json
from unittest.mock import patch

from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase, override_settings

from accounts.sms import SMSDeliveryError, send_otp


@override_settings(
    SMS_BACKEND="smsir",
    SMSIR_API_KEY="test-only-api-key",
    SMSIR_TEMPLATE_ID="123456",
)
class SMSIRTests(SimpleTestCase):
    def test_success_uses_template_code_and_timeout(self):
        with patch("accounts.sms.HTTPSConnection") as factory:
            connection = factory.return_value
            response = connection.getresponse.return_value
            response.status = 200
            response.read.return_value = b'{"status": 1}'

            send_otp("09123456789", "001234")

            factory.assert_called_once_with(
                "api.sms.ir",
                timeout=10,
            )

            call = connection.request.call_args

            self.assertEqual(
                call.args,
                ("POST", "/v1/send/verify/"),
            )

            data = json.loads(call.kwargs["body"])

            self.assertEqual(
                data["mobile"],
                "09123456789",
            )
            self.assertEqual(data["templateId"], 123456)
            self.assertEqual(
                data["parameters"],
                [{"name": "CODE", "value": "001234"}],
            )
            self.assertEqual(
                call.kwargs["headers"]["X-API-KEY"],
                "test-only-api-key",
            )

            connection.close.assert_called_once()

    def test_timeout_is_not_retried_or_logged_with_secrets(self):
        with patch("accounts.sms.HTTPSConnection") as factory:
            connection = factory.return_value
            connection.request.side_effect = TimeoutError(
                "test-only-api-key 001234"
            )

            with self.assertLogs(
                "accounts.sms",
                level="ERROR",
            ) as logs:
                with self.assertRaises(SMSDeliveryError):
                    send_otp("09123456789", "001234")

            connection.request.assert_called_once()
            connection.close.assert_called_once()

            output = " ".join(logs.output)
            self.assertNotIn("test-only-api-key", output)
            self.assertNotIn("001234", output)

    def test_http_failure_rejection_and_invalid_json(self):
        cases = [
            (401, b'{"status": 10}'),
            (302, b""),
            (200, b'{"status": 0}'),
            (200, b'{"status": true}'),
            (200, b"[]"),
            (200, b"not-json"),
        ]

        for status, body in cases:
            with self.subTest(status=status, body=body):
                with patch(
                    "accounts.sms.HTTPSConnection"
                ) as factory:
                    response = (
                        factory.return_value
                        .getresponse.return_value
                    )
                    response.status = status
                    response.read.return_value = body

                    with self.assertLogs(
                        "accounts.sms",
                        level="ERROR",
                    ):
                        with self.assertRaises(SMSDeliveryError):
                            send_otp("09123456789", "001234")

    @override_settings(SMSIR_API_KEY="")
    def test_missing_key_does_not_connect(self):
        with patch("accounts.sms.HTTPSConnection") as factory:
            with self.assertLogs(
                "accounts.sms",
                level="ERROR",
            ):
                with self.assertRaises(SMSDeliveryError):
                    send_otp("09123456789", "001234")

            factory.assert_not_called()

    @override_settings(
        SMS_BACKEND="console",
        DEBUG=False,
        OTP_CONSOLE_ENABLED=True,
    )
    def test_console_is_blocked_outside_development(self):
        with self.assertRaises(ImproperlyConfigured):
            send_otp("09123456789", "001234")

    @override_settings(
        SMS_BACKEND="console",
        DEBUG=True,
        OTP_CONSOLE_ENABLED=True,
    )
    def test_console_requires_explicit_development_mode(self):
        with patch("accounts.sms.HTTPSConnection") as factory:
            with self.assertLogs(
                "accounts.sms",
                level="WARNING",
            ):
                send_otp("09123456789", "001234")

            factory.assert_not_called()