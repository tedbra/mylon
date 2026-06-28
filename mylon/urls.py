"""
URL configuration for mylon project.

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
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')), # Hook up accounts auth routes
    path('expenses/', include('expense.urls')),
    path('', include('students.urls')),
    path(
        'serviceworker.js', 
        TemplateView.as_view(template_name="serviceworker.js", content_type='application/javascript'), 
        name='serviceworker'
    ),
    
]

# Append static directory asset routing rules for development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    # If using uploaded profile pictures, append media files directory routing as well:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)