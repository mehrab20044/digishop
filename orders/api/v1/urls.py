from django.urls import path

from orders.api.v1.views import (
    OrderCancelView,
    OrderDetailView,
    OrderListCreateView,
    OrderPreviewView,
)

app_name = "orders"

urlpatterns = [
    path(
        "",
        OrderListCreateView.as_view(),
        name="list-create",
    ),
    path(
        "<uuid:pk>/",
        OrderDetailView.as_view(),
        name="detail",
    ),
    path(
        "<uuid:pk>/cancel/",
        OrderCancelView.as_view(),
        name="cancel",
    ),
    path(
    "preview/",
    OrderPreviewView.as_view(),
    name="preview",
),
]