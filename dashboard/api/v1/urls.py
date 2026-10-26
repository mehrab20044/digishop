from django.urls import path

from seo.dashboard_api import SEOAccessView, SEODashboardView

from dashboard.api.v1.gallery import ProductGalleryView
from dashboard.api.v1.product_create import ProductCreateView
from dashboard.api.v1.staff import (
    StaffListCreateView,
    StaffUpdateView,
)
from dashboard.api.v1.views import (
    DashboardDetailView,
    DashboardIndexView,
    DashboardListView,
)
from dashboard.api.v1.write_views import (
    DashboardCreateView,
    DashboardUpdateView,
    OwnerCSRFView,
)

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

    # Specific routes must precede generic resource routes.
    path(
        "staff/",
        StaffListCreateView.as_view(),
        name="staff-list-create",
    ),
    path(
        "staff/<int:pk>/",
        StaffUpdateView.as_view(),
        name="staff-update",
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
        "products/<int:pk>/gallery/",
        ProductGalleryView.as_view(),
        name="product-gallery",
    ),

    # Generic routes come last.
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
]