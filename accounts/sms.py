import json
import logging
from http.client import HTTPException, HTTPSConnection

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.exceptions import APIException

logger = logging.getLogger(__name__)


class SMSDeliveryError(APIException):
    status_code = 503
    default_detail = (
        "ارسال کد تأیید فعلاً ممکن نیست؛ "
        "کمی بعد دوباره تلاش کنید."
    )
    default_code = "sms_unavailable"


def send_otp(phone, code):
    backend = getattr(
        settings,
        "SMS_BACKEND",
        "console",
    )

    if backend == "console":
        if (
            not settings.DEBUG
            or not settings.OTP_CONSOLE_ENABLED
        ):
            raise ImproperlyConfigured(
                "Console OTP requires DEBUG "
                "and OTP_CONSOLE_ENABLED."
            )

        logger.warning(
            "Development OTP | phone=%s | code=%s",
            phone,
            code,
        )
        return None

    if backend != "smsir":
        raise ImproperlyConfigured(
            "Unsupported SMS_BACKEND."
        )

    api_key = getattr(
        settings,
        "SMSIR_API_KEY",
        "",
    ).strip()

    try:
        template_id = int(
            getattr(settings, "SMSIR_TEMPLATE_ID", "")
        )
    except (TypeError, ValueError):
        template_id = 0

    if not api_key or template_id <= 0:
        logger.error(
            "SMS.ir configuration is incomplete."
        )
        raise SMSDeliveryError()

    body = json.dumps({
        "mobile": phone,
        "templateId": template_id,
        "parameters": [
            {
                "name": "CODE",
                "value": str(code),
            },
        ],
    }).encode("utf-8")

    connection = HTTPSConnection(
        "api.sms.ir",
        timeout=10,
    )

    try:
        connection.request(
            "POST",
            "/v1/send/verify/",
            body=body,
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        response = connection.getresponse()
        raw = response.read(65537)

        if not 200 <= response.status < 300:
            logger.error(
                "SMS.ir HTTP failure: %s",
                response.status,
            )
            raise SMSDeliveryError()

        if len(raw) > 65536:
            logger.error(
                "SMS.ir response exceeded the expected size."
            )
            raise SMSDeliveryError()

        data = json.loads(raw)

    except (OSError, HTTPException, ValueError):
        logger.error(
            "SMS.ir transport or response failure."
        )
        raise SMSDeliveryError() from None

    finally:
        connection.close()

    if (
        not isinstance(data, dict)
        or type(data.get("status")) is not int
        or data["status"] != 1
    ):
        logger.error(
            "SMS.ir rejected the verification request."
        )
        raise SMSDeliveryError()

    return None