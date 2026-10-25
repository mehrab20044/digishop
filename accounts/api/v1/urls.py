from django.urls import path

from accounts.api.v1.views import (
    AddressDetailView,
    AddressListCreateView,
    CompleteProfileView,
    LogoutView,
    OTPRequestView,
    OTPVerifyView,
    ProfileView,
    RefreshView,
)

app_name = "accounts"

urlpatterns = [
    path(
        "otp/request/",
        OTPRequestView.as_view(),
        name="otp-request",
    ),
    path(
        "otp/verify/",
        OTPVerifyView.as_view(),
        name="otp-verify",
    ),
    path(
        "token/refresh/",
        RefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path(
        "me/",
        ProfileView.as_view(),
        name="profile",
    ),
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