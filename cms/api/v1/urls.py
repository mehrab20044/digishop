from django.urls import path

from cms.api.v1.banner_views import BannerVideoUploadView, BannerView
from cms.api.v1.theme_views import ThemeView
from cms.api.v1.views import (
    PageDetailView,
    PageHideView,
    PageImageUploadView,
    PageListCreateView,
    PagePublishView,
)

app_name = "cms_owner"
urlpatterns = [
    path("banners/videos/", BannerVideoUploadView.as_view(), name="banner-video-upload"),
    path("banners/", BannerView.as_view(), name="banners"),
    path("theme/", ThemeView.as_view(), name="theme"),
    path("", PageListCreateView.as_view(), name="list-create"),
    path("images/", PageImageUploadView.as_view(), name="image-upload"),
    path("<int:pk>/", PageDetailView.as_view(), name="detail"),
    path("<int:pk>/publish/", PagePublishView.as_view(), name="publish"),
    path("<int:pk>/hide/", PageHideView.as_view(), name="hide"),
]
