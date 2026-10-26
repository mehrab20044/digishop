from uuid import UUID

from django.utils import timezone
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .models import AuthSession, OTPChallenge


class SessionJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        try:
            session_id = UUID(str(validated_token["sid"]))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise InvalidToken("شناسه نشست معتبر نیست.") from exc

        purpose = validated_token.get("purpose")

        if purpose not in OTPChallenge.Purpose.values:
            raise InvalidToken("نوع نشست معتبر نیست.")

        valid = AuthSession.objects.filter(
            pk=session_id,
            user_id=user.pk,
            purpose=purpose,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists()

        if not valid:
            raise InvalidToken("نشست منقضی یا لغو شده است.")

        return user