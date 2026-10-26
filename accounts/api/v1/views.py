from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from accounts.models import Address, OTPChallenge, Profile
from accounts.services.auth_service import (
    logout_all_sessions,
    logout_session,
    refresh_session,
    request_otp,
    verify_otp,
)
from accounts.services.profile_service import delete_address
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


class RefreshSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        max_length=8192,
        trim_whitespace=False,
    )


@method_decorator(never_cache, name="dispatch")
class PublicAuthView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AuthIPThrottle]
    purpose = OTPChallenge.Purpose.CUSTOMER

    def get_authenticate_header(self, request):
        return "Bearer"


class OTPRequestView(PublicAuthView):
    serializer_class = OTPRequestSerializer

    @extend_schema(responses={200: OTPRequestResponseSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        request_otp(
            serializer.validated_data["phone"],
            purpose=self.purpose,
        )

        return Response({
            "detail": "در صورت مجاز بودن درخواست، کد تأیید ارسال می‌شود.",
            "retry_after": settings.OTP_RESEND_SECONDS,
        })


class OTPVerifyView(PublicAuthView):
    serializer_class = OTPVerifySerializer

    @extend_schema(responses={200: OTPVerifyResponseSerializer})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = verify_otp(
            **serializer.validated_data,
            purpose=self.purpose,
        )

        return Response({
            "access": result["access"],
            "refresh": result["refresh"],
            "is_new_user": result["is_new_user"],
            "user": ProfileSerializer(
                result["user"],
                context=self.get_serializer_context(),
            ).data,
        })


class RefreshView(PublicAuthView):
    serializer_class = RefreshSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        return Response(
            refresh_session(
                serializer.validated_data["refresh"],
                purpose=self.purpose,
            ),
        )


class ManagementOTPRequestView(OTPRequestView):
    purpose = OTPChallenge.Purpose.MANAGEMENT


class ManagementOTPVerifyView(OTPVerifyView):
    purpose = OTPChallenge.Purpose.MANAGEMENT


class ManagementRefreshView(RefreshView):
    purpose = OTPChallenge.Purpose.MANAGEMENT


@method_decorator(never_cache, name="dispatch")
class LogoutView(generics.GenericAPIView):
    serializer_class = LogoutSerializer
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        logout_session(
            request.user,
            request.auth,
            serializer.validated_data["refresh"],
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(never_cache, name="dispatch")
class LogoutAllView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = serializers.Serializer

    @extend_schema(responses={204: None})
    def post(self, request, *args, **kwargs):
        logout_all_sessions(request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(never_cache, name="dispatch")
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        Profile.objects.get_or_create(user=self.request.user)

        return (
            get_user_model()
            .objects.select_related("profile")
            .prefetch_related("addresses")
            .get(pk=self.request.user.pk)
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

        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AddressDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Address.objects.none()

        return Address.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        delete_address(instance)