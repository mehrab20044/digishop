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

admin.site.site_header = "مدیریت دیجی‌شاپ"
admin.site.site_title = "پنل مدیریت دیجی‌شاپ"
admin.site.index_title = "مدیریت فروشگاه"

urlpatterns = [
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
path("api/v1/auth/", include("accounts.api.v1.urls")),]

if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT,
    )


# DigiShop cart routes
urlpatterns += [path("api/v1/cart/", include("cart.urls"))]
