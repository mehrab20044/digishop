from django.urls import path

from .customer_hub import (
    HubOrdersView,
    HubSummaryView,
    ReturnsView,
    SavedProductsView,
    SavedStateView,
)

app_name = "customer_hub"
urlpatterns = [
    path("saved/<int:pk>/", SavedStateView.as_view(), name="saved-state"),
    path("summary/", HubSummaryView.as_view(), name="summary"),
    path("orders/", HubOrdersView.as_view(), name="orders"),
    path("orders/<uuid:pk>/", HubOrdersView.as_view(), name="order"),
    path("saved/", SavedProductsView.as_view(), name="saved"),
    path("returns/", ReturnsView.as_view(), name="returns"),
]
