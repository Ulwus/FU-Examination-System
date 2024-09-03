from django.urls import path
from . import views

urlpatterns = [
    path('', views.exam_list, name='exam_list'),
    path('dashboard/', views.student_dashboard, name='student_dashboard'),
    path('exam/<int:pk>/', views.exam_detail, name='exam_detail'),
    path('exam/create/', views.create_exam, name='create_exam'),
    path('exam/<int:pk>/take/', views.take_exam, name='take_exam'),
    path('exam/<int:pk>/result/', views.exam_result, name='exam_result'),
    path('exam/<int:pk>/grade/', views.grade_exam, name='grade_exam'),
    path('exam/<int:pk>/create-questions/', views.create_exam_questions, name='create_exam_questions'),

]       