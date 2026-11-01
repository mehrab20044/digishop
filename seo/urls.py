from django.urls import path

from .views import robots_txt
from .robots_api import RobotsStudioView
from .page_rules_api import PageRulesView
from .page_sitemap import page_rules_sitemap

urlpatterns = [
    path("api/v1/owner/seo/robots-studio/", RobotsStudioView.as_view(), name="seo-robots-studio"),
    path("api/v1/owner/seo/page-rules/", PageRulesView.as_view(), name="seo-page-rules"),
    path("sitemap.xml", page_rules_sitemap, name="store-sitemap"),
    path("robots.txt", robots_txt, name="robots_txt"),
]
