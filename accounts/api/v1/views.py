from django.conf import settings
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.permissions import (
    AllowAny,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.settings import api_settings
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.models import Address, Profile
from accounts.profile_services import delete_address
from accounts.services import request_otp, verify_otp
from accounts.throttles import AuthIPThrottle

from .serializers import (
    AddressSerializer,
    CompleteProfileSerializer,
    LogoutSerializer,
    OTPRequestResponseSerializer,
    OTPRequestSerializer,
    OTPVerifyResponseSerializer,
    OTPVerifySerializer,
    ProfileSerializer,
)


class OTPRequestView(generics.GenericAPIView):
    serializer_class = OTPRequestSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthIPThrottle]

    @extend_schema(
        responses={200: OTPRequestResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_otp(serializer.validated_data["phone"])

        return Response({
            "detail": "کد تأیید ارسال شد.",
            "retry_after": settings.OTP_RESEND_SECONDS,
        })


class OTPVerifyView(generics.GenericAPIView):
    serializer_class = OTPVerifySerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthIPThrottle]

    def get_authenticate_header(self, request):
        return "Bearer"

    @extend_schema(
        responses={200: OTPVerifyResponseSerializer},
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = verify_otp(**serializer.validated_data)

        data = {
            "access": result["access"],
            "refresh": result["refresh"],
            "is_new_user": result["is_new_user"],
            "user": ProfileSerializer(
                result["user"],
                context=self.get_serializer_context(),
            ).data,
        }
        return Response(data)


class RefreshView(TokenRefreshView):
    throttle_classes = [AuthIPThrottle]


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "patch",
        "head",
        "options",
    ]

    def get_object(self):
        Profile.objects.get_or_create(
            user=self.request.user,
        )

        return (
            get_user_model()
            .objects.select_related(
                "profile",
                "phone_identity",
            )
            .get(pk=self.request.user.pk)
        )


class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(
                serializer.validated_data["refresh"],
            )
        except TokenError as exc:
            raise serializers.ValidationError({
                "refresh": "توکن نامعتبر یا باطل شده است."
            }) from exc

        token_user_id = token.get(
            api_settings.USER_ID_CLAIM,
        )
        current_user_id = getattr(
            request.user,
            api_settings.USER_ID_FIELD,
        )

        if str(token_user_id) != str(current_user_id):
            raise serializers.ValidationError({
                "refresh": "این توکن متعلق به حساب شما نیست."
            })

        token.blacklist()
        return Response(
            status=status.HTTP_204_NO_CONTENT,
        )


class CompleteProfileView(generics.GenericAPIView):
    serializer_class = CompleteProfileSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ProfileSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save(user=request.user)

        return Response(
            ProfileSerializer(
                user,
                context=self.get_serializer_context(),
            ).data,
        )


class AddressListCreateView(generics.ListCreateAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Address.objects.none()

        return Address.objects.filter(
            user=self.request.user,
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressDetailView(
    generics.RetrieveUpdateDestroyAPIView,
):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = [
        "get",
        "patch",
        "delete",
        "head",
        "options",
    ]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Address.objects.none()

        return Address.objects.filter(
            user=self.request.user,
        )

    def perform_destroy(self, instance):
        delete_address(instance)