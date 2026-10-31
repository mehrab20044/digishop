from django.urls import path

from dashboard.api.v1.catalog import (
    AttributeDefinitionsView,
    CategorySchemaView,
    ProductCatalogView,
)
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
from dashboard.api.v1.workspace import (
    CategorySpecificationView,
    CombinationPreviewView,
    WorkspaceBrandView,
    WorkspaceChoicesView,
    WorkspaceProductView,
)
from dashboard.api.v1.write_views import (
    DashboardCreateView,
    DashboardUpdateView,
    OwnerCSRFView,
)
from seo.dashboard_api import SEOAccessView, SEODashboardView

app_name = "owner_dashboard"

urlpatterns = [
    path("workspace/choices/", WorkspaceChoicesView.as_view()),
    path("workspace/products/", WorkspaceProductView.as_view()),
    path("workspace/products/<int:pk>/", WorkspaceProductView.as_view()),
    path("workspace/combinations/preview/", CombinationPreviewView.as_view()),
    path(
        "workspace/categories/<int:pk>/specifications/",
        CategorySpecificationView.as_view(),
    ),
    path("workspace/brands/", WorkspaceBrandView.as_view()),
    path("workspace/brands/<int:pk>/", WorkspaceBrandView.as_view()),
    path(
        "catalog/attributes/<int:pk>/",
        AttributeDefinitionsView.as_view(),
        name="attribute-definition-edit",
    ),
    path(
        "catalog/attributes/",
        AttributeDefinitionsView.as_view(),
        name="attribute-definitions",
    ),
    path(
        "catalog/categories/<int:pk>/",
        CategorySchemaView.as_view(),
        name="category-schema",
    ),
    path(
        "catalog/products/<int:pk>/",
        ProductCatalogView.as_view(),
        name="product-catalog",
    ),
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
