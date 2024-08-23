from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', include('users.urls')),
    path('users/', include('users.urls')),
    path('', include('exams.urls')),
    path('ide/', include('ide.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
