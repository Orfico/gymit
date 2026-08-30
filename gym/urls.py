from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # Schede
    path('plans/', views.plan_list, name='plan_list'),
    path('plans/create/', views.plan_create, name='plan_create'),
    path('plans/reorder/', views.plan_list_reorder, name='plan_list_reorder'),

    # Cartelle
    path('plans/folders/create/', views.plan_folder_create, name='plan_folder_create'),
    path('plans/folders/<int:pk>/rename/', views.plan_folder_rename, name='plan_folder_rename'),
    path('plans/folders/<int:pk>/delete/', views.plan_folder_delete, name='plan_folder_delete'),
    path('plans/folders/<int:pk>/reorder/', views.plan_folder_reorder, name='plan_folder_reorder'),

    path('plans/<int:pk>/', views.plan_detail, name='plan_detail'),
    path('plans/<int:pk>/edit/', views.plan_edit, name='plan_edit'),
    path('plans/<int:pk>/delete/', views.plan_delete, name='plan_delete'),
    path('plans/<int:pk>/reorder/', views.plan_reorder, name='plan_reorder'),

    # Esercizi in scheda
    path('plans/<int:plan_pk>/add-exercise/', views.planned_exercise_add, name='planned_exercise_add'),
    path('planned/<int:pk>/edit/', views.planned_exercise_edit, name='planned_exercise_edit'),
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
    path('exercises/<int:pk>/edit/', views.exercise_edit, name='exercise_edit'),
    path('exercises/<int:pk>/delete/', views.exercise_delete, name='exercise_delete'),
    path('exercises/<int:pk>/video/', views.exercise_video_set, name='exercise_video_set'),
    path('exercises/<int:pk>/video/remove/', views.exercise_video_remove, name='exercise_video_remove'),

    # Preferenze utente
    path('preferences/video-admin/', views.toggle_video_admin, name='toggle_video_admin'),

    # Modifica log allenamento
    path('log/<int:pk>/edit/', views.log_edit, name='log_edit'),

    # Esportazione/Importazione schede
    path('plans/<int:pk>/export/', views.plan_export, name='plan_export'),
    path('plans/import/', views.plan_import, name='plan_import'),

    # Sessioni di allenamento e calendario
    path('sessions/create/', views.session_create, name='session_create'),
    path('sessions/<int:pk>/delete/', views.session_delete, name='session_delete'),
    path('sessions/import/', views.session_import, name='session_import'),
    path('sessions/template/', views.session_template_download, name='session_template_download'),
    path('calendar/', views.workout_calendar, name='workout_calendar'),
    path('calendar/<int:year>/<int:month>/<int:day>/', views.session_day_detail, name='session_day_detail'),

    # PWA Service Worker (deve stare alla root per avere scope /)
    path('sw.js', views.service_worker, name='service_worker'),
]
