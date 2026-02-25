from django.contrib import admin
from .models import Exercise, WorkoutPlan, PlannedExercise, ExerciseLog


@admin.register(Exercise)
class ExerciseAdmin(admin.ModelAdmin):
    list_display = ('name', 'muscle_group', 'created_by')
    list_filter = ('muscle_group',)
    search_fields = ('name',)


@admin.register(WorkoutPlan)
class WorkoutPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'user__username')


@admin.register(PlannedExercise)
class PlannedExerciseAdmin(admin.ModelAdmin):
    list_display = ('exercise', 'plan', 'target_sets', 'target_reps', 'order')
    list_filter = ('plan',)


@admin.register(ExerciseLog)
class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = ('exercise', 'user', 'date', 'weight', 'sets', 'reps', 'one_rm')
    list_filter = ('exercise', 'date')
    search_fields = ('user__username', 'exercise__name')
    readonly_fields = ('one_rm',)
