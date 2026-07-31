"""
URL configuration for land_escrow project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
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
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from core import admin_urls
from land_escrow.health_views import health_check

from core import api_views

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url=settings.STATIC_URL + 'images/favicon.ico', permanent=True)),
    path('health/', health_check, name='health-check'),
    path('browse', RedirectView.as_view(url='/parcels/', permanent=False)),
    path('browse/', RedirectView.as_view(url='/parcels/', permanent=False)),
    path('marketplace', RedirectView.as_view(url='/parcels/', permanent=False, query_string=True)),
    path('marketplace/', RedirectView.as_view(url='/parcels/', permanent=False, query_string=True)),
    path('admin/', admin.site.urls),
    path('admin/', include(admin_urls)),
    path('api/v1/auth/', include('core.auth_urls')),
    path('api/auth/me/', api_views.auth_me_api, name='auth_me_api'),
    path('api/onboarding/select-role/', api_views.onboarding_select_role_api, name='onboarding_select_role_api'),
    path('accounts/', include('allauth.urls')),
    path('api/v1/', include('core.urls')),
    path('api/v1/admin/control-plane/', include('admin_control_plane.urls')),
    path('', include('server.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
