from django.urls import path
from . import views

urlpatterns = [
    path('', views.CompetitionListView.as_view(), name='competition_list'),
    path('create/', views.CreateCompetitionView.as_view(), name='create_competition'),
    path('join/', views.join_competition, name='join_competition'),
    path('<int:pk>/', views.CompetitionDetailView.as_view(), name='competition_detail'),
    path('<int:competition_id>/download/', views.download_training_dataset, name='download_training_dataset'),
    path('<int:competition_id>/submit/', views.submit_model, name='submit_model'),
]