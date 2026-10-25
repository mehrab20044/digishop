import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def send_otp(phone, code):
    if not settings.DEBUG or not settings.OTP_CONSOLE_ENABLED:
        raise ImproperlyConfigured(
            "SMS provider is not configured. "
            "Console OTP requires DEBUG and OTP_CONSOLE_ENABLED."
        )

    logger.warning("Development OTP | phone=%s | code=%s", phone, code)