from django.urls import path

from payments.api.v1.views import (
    FakePaymentDecisionView,
    FakePaymentPageView,
    FakePaymentVerifyView,
    PaymentDetailView,
    PaymentStartView,
)

app_name = "payments"

urlpatterns = [
    path(
        "start/",
        PaymentStartView.as_view(),
        name="start",
    ),
    path(
        "<uuid:pk>/",
        PaymentDetailView.as_view(),
        name="detail",
    ),
    path(
        "fake/<uuid:pk>/",
        FakePaymentPageView.as_view(),
        name="fake-page",
    ),
    path(
        "fake/<uuid:pk>/decision/",
        FakePaymentDecisionView.as_view(),
        name="fake-decision",
    ),
    path(
        "fake/<uuid:pk>/verify/",
        FakePaymentVerifyView.as_view(),
        name="fake-verify",
    ),
]