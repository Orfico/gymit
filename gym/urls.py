from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Schede
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/create/', views.plan_create, name='plan_create'),
    path('plans/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:pk>/edit/', views.plan_edit, name='plan_edit'),
    path('plans/<int:pk>/delete/', views.plan_delete, name='plan_delete'),
    path('plans/<int:pk>/reorder/', views.plan_reorder, name='plan_reorder'),

    # Esercizi in scheda
    path('plans/<int:plan_pk>/add-exercise/', views.planned_exercise_add, name='planned_exercise_add'),
    path('planned/<int:pk>/remove/', views.planned_exercise_remove, name='planned_exercise_remove'),

    # Log allenamenti
    path('log/add/', views.log_create, name='log_create'),
    path('log/<int:pk>/delete/', views.log_delete, name='log_delete'),

    # Progresso
    path('progress/', views.progress_overview, name='progress_overview'),
    path('progress/<int:exercise_id>/', views.exercise_progress, name='exercise_progress'),

    # Autocomplete
    path('exercises/autocomplete/', views.exercise_autocomplete, name='exercise_autocomplete'),

    # Catalogo esercizi
    path('exercises/', views.exercise_list, name='exercise_list'),
    path('exercises/create/', views.exercise_create, name='exercise_create'),
]
