from django.urls import path

from seo.dashboard_api import (
    SEOAccessView,
    SEODashboardView,
)

from .dashboard_api import (
    DashboardDetailView,
    DashboardIndexView,
    DashboardListView,
)
from .dashboard_product_create import ProductCreateView
from .dashboard_write_api import (
    DashboardCreateView,
    DashboardUpdateView,
    OwnerCSRFView,
)
from .dashboard_gallery import ProductGalleryView

app_name = "owner_dashboard"

urlpatterns = [
    path(
        "",
        DashboardIndexView.as_view(),
        name="index",
    ),
    path(
        "csrf/",
        OwnerCSRFView.as_view(),
        name="csrf",
    ),
    path(
        "seo/",
        SEODashboardView.as_view(),
        name="seo",
    ),
    path(
        "seo/access/",
        SEOAccessView.as_view(),
        name="seo-access",
    ),
    path(
        "products/create/",
        ProductCreateView.as_view(),
        name="product-create",
    ),
    path(
        "<slug:resource>/create/",
        DashboardCreateView.as_view(),
        name="create",
    ),
    path(
        "<slug:resource>/<int:pk>/edit/",
        DashboardUpdateView.as_view(),
        name="update",
    ),
    path(
        "<slug:resource>/",
        DashboardListView.as_view(),
        name="list",
    ),
    path(
        "<slug:resource>/<int:pk>/",
        DashboardDetailView.as_view(),
        name="detail",
    ),
        path(
        "products/<int:pk>/gallery/",
        ProductGalleryView.as_view(),
        name="product-gallery",
    ),
]