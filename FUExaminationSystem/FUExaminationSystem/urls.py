from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

handler400 = 'FUExaminationSystem.views.custom_400'
handler401 = 'FUExaminationSystem.views.custom_401'
handler403 = 'FUExaminationSystem.views.custom_403'
handler404 = 'FUExaminationSystem.views.custom_404'
handler408 = 'FUExaminationSystem.views.custom_408'
handler429 = 'FUExaminationSystem.views.custom_429'
handler500 = 'FUExaminationSystem.views.custom_500'
handler502 = 'FUExaminationSystem.views.custom_502'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', include('users.urls')),
    path('users/', include('users.urls')),
    path('competitions/', include('competitions.urls')),
    path('exam/', include('exams.urls')),
    path('', include('dashboard.urls')),
    path('ide/', include('ide.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

