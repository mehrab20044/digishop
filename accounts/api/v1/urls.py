from django.urls import path

from .views import (
    AddressDetailView,
    AddressListCreateView,
    CompleteProfileView,
    LogoutAllView,
    LogoutView,
    ManagementOTPRequestView,
    ManagementOTPVerifyView,
    ManagementRefreshView,
    OTPRequestView,
    OTPVerifyView,
    ProfileView,
    RefreshView,
)

app_name = "accounts"

urlpatterns = [
    path("otp/request/", OTPRequestView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("token/refresh/", RefreshView.as_view(), name="token-refresh"),
    path(
        "management/otp/request/",
        ManagementOTPRequestView.as_view(),
        name="management-otp-request",
    ),
    path(
        "management/otp/verify/",
        ManagementOTPVerifyView.as_view(),
        name="management-otp-verify",
    ),
    path(
        "management/token/refresh/",
        ManagementRefreshView.as_view(),
        name="management-token-refresh",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout-all"),
    path("me/", ProfileView.as_view(), name="profile"),
    path(
        "me/complete/",
        CompleteProfileView.as_view(),
        name="complete-profile",
    ),
    path(
        "addresses/",
        AddressListCreateView.as_view(),
        name="addresses",
    ),
    path(
        "addresses/<int:pk>/",
        AddressDetailView.as_view(),
        name="address-detail",
    ),
]