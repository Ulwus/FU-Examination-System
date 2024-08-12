from django.urls import path
from . import views
from .views import CustomPasswordResetView

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('password_reset/', CustomPasswordResetView.as_view(), name='password_reset'),
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('logout/', views.logout_view, name='logout'),
]
