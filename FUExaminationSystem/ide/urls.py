from django.urls import path
from . import views

urlpatterns = [
    path('run/', views.run_code, name='run_code'),

]