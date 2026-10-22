from django.urls import include, path

app_name = "products"

urlpatterns = [
    path(
        "api/v1/",
        include("products.api.v1.urls"),
    ),
]
