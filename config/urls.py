"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
)

from cms.api.v1.footer_views import FooterOwnerView, footer_styles, public_footer
from cms.views import (
    banner_feed,
    page_document,
    page_links,
    page_sitemap,
    page_styles,
    page_view,
    public_theme,
    theme_styles,
)
from dashboard.api.v1.customer_operations import CustomerOperationsView
from products.category_url_views import (
    category_page,
    category_resolve,
    category_sitemap,
)

admin.site.site_header = "مدیریت دیجی‌شاپ"
admin.site.site_title = "پنل مدیریت دیجی‌شاپ"
admin.site.index_title = "مدیریت فروشگاه"


urlpatterns = [
    path("api/v1/customer/", include("accounts.api.v1.customer_hub_urls")),
    path("api/v1/content/footer/", public_footer),
    path("pages-assets/store-footer.css", footer_styles),
    path("api/v1/owner/footer-settings/", FooterOwnerView.as_view()),
    path("api/v1/owner/customer-operations/", CustomerOperationsView.as_view()),
    path("api/v1/content/banners/", banner_feed),
    path("api/v1/content/theme/", public_theme),
    path("api/v1/content/page/<str:slug>/", page_document),
    path("pages-assets/theme.css", theme_styles),
    path("api/v1/owner/pages/", include("cms.api.v1.urls")),
    path("api/v1/content/pages/", page_links, name="cms-links"),
    path("pages-assets/page-content.css", page_styles, name="cms-styles"),
    path("pages-sitemap.xml", page_sitemap, name="cms-sitemap"),
    path("pages/<str:slug>", page_view, name="cms-page"),
    path("pages/<str:slug>/", page_view),
    path("products/category/<path:path>", category_page, name="category-page"),
    path(
        "products/api/v1/category-resolve/", category_resolve, name="category-resolve"
    ),
    path("category-sitemap.xml", category_sitemap, name="category-sitemap"),
    path("admin/", admin.site.urls),
    path("products/", include("products.urls")),
    path(
        "api/v1/owner/",
        include("dashboard.api.v1.urls"),
    ),
    path("api/v1/orders/", include("orders.api.v1.urls")),
    path("api/v1/payments/", include("payments.api.v1.urls")),
    path("", include("seo.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/v1/auth/", include("accounts.api.v1.urls")),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )


# DigiShop cart routes
urlpatterns += [path("api/v1/cart/", include("cart.urls"))]
