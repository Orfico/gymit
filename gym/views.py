import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Max, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse

from .forms import (
    WorkoutPlanForm,
    PlannedExerciseForm,
    ExerciseLogForm,
    ExerciseForm,
)
from .models import Exercise, WorkoutPlan, PlannedExercise, ExerciseLog


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Home: ultimi log e scheda attiva."""
    recent_logs = (
        ExerciseLog.objects
        .filter(user=request.user)
        .select_related('exercise')[:10]
    )
    active_plan = (
        WorkoutPlan.objects
        .filter(user=request.user, is_active=True)
        .prefetch_related('planned_exercises__exercise')
        .first()
    )
    # Numero esercizi loggati oggi
    logged_today = ExerciseLog.objects.filter(
        user=request.user, date=date.today()
    ).count()

    return render(request, 'gym/dashboard.html', {
        'recent_logs': recent_logs,
        'active_plan': active_plan,
        'logged_today': logged_today,
    })


# ─── Workout Plans ────────────────────────────────────────────────────────────

@login_required
def plan_list(request):
    plans = WorkoutPlan.objects.filter(user=request.user).annotate(
        exercise_count=Count('planned_exercises')
    )
    return render(request, 'gym/plan_list.html', {'plans': plans})


@login_required
def plan_create(request):
    form = WorkoutPlanForm(request.POST or None)
    if form.is_valid():
        plan = form.save(commit=False)
        plan.user = request.user
        plan.save()
        messages.success(request, f'Scheda "{plan.name}" creata con successo.')
        return redirect('plan_detail', pk=plan.pk)
    return render(request, 'gym/plan_form.html', {'form': form, 'action': 'Crea'})


@login_required
def plan_detail(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk, user=request.user)
    planned = plan.planned_exercises.select_related('exercise').all()
    return render(request, 'gym/plan_detail.html', {
        'plan': plan,
        'planned': planned,
    })


@login_required
def plan_edit(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk, user=request.user)
    form = WorkoutPlanForm(request.POST or None, instance=plan)
    if form.is_valid():
        form.save()
        messages.success(request, 'Scheda aggiornata.')
        return redirect('plan_detail', pk=plan.pk)
    return render(request, 'gym/plan_form.html', {'form': form, 'action': 'Modifica', 'plan': plan})


@login_required
def plan_delete(request, pk):
    plan = get_object_or_404(WorkoutPlan, pk=pk, user=request.user)
    if request.method == 'POST':
        plan.delete()
        messages.success(request, f'Scheda "{plan.name}" eliminata.')
        return redirect('plan_list')
    return render(request, 'gym/plan_confirm_delete.html', {'plan': plan})


# ─── Planned Exercises ────────────────────────────────────────────────────────

@login_required
@login_required
def planned_exercise_add(request, plan_pk):
    plan = get_object_or_404(WorkoutPlan, pk=plan_pk, user=request.user)
    form = PlannedExerciseForm(request.POST or None)
    if form.is_valid():
        pe = form.save(commit=False)
        pe.plan = plan
        from django.db.models import Max
        last_order = plan.planned_exercises.aggregate(Max('order'))['order__max']
        pe.order = (last_order or 0) + 1
        pe.save()
        messages.success(request, f'"{pe.exercise.name}" aggiunto alla scheda.')
        return redirect('plan_detail', pk=plan.pk)
    return render(request, 'gym/planned_exercise_form.html', {
        'form': form, 'plan': plan, 'action': 'Aggiungi'
    })


@login_required
def plan_reorder(request, pk):
    """
    Riceve via POST JSON con la nuova sequenza di ID PlannedExercise
    e aggiorna il campo order di ciascuno.
    Chiamato in AJAX dal drag & drop nel frontend.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    plan = get_object_or_404(WorkoutPlan, pk=pk, user=request.user)
    try:
        data = json.loads(request.body)
        ordered_ids = data.get('order', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    valid_ids = set(plan.planned_exercises.values_list('id', flat=True))
    if set(ordered_ids) != valid_ids:
        return JsonResponse({'error': 'Invalid exercise IDs'}, status=400)
    for position, pe_id in enumerate(ordered_ids):
        PlannedExercise.objects.filter(pk=pe_id, plan=plan).update(order=position)
    return JsonResponse({'status': 'ok'})
@login_required
def planned_exercise_remove(request, pk):
    pe = get_object_or_404(PlannedExercise, pk=pk, plan__user=request.user)
    plan_pk = pe.plan.pk
    if request.method == 'POST':
        pe.delete()
        messages.success(request, 'Esercizio rimosso dalla scheda.')
    return redirect('plan_detail', pk=plan_pk)


# ─── Exercise Logs ────────────────────────────────────────────────────────────

@login_required
def log_create(request):
    """
    Registra una nuova sessione. Ogni submit crea un nuovo ExerciseLog —
    mai sovrascrive. Il 1RM viene calcolato automaticamente nel model.save().
    """
    # Precompila l'esercizio se passato come query param (da dashboard)
    initial = {}
    exercise_id = request.GET.get('exercise')
    if exercise_id:
        initial['exercise'] = exercise_id
    initial['date'] = date.today()

    form = ExerciseLogForm(request.POST or None, user=request.user, initial=initial)
    if form.is_valid():
        log = form.save(commit=False)
        log.user = request.user
        log.save()
        messages.success(
            request,
            f'Log salvato — 1RM teorico: {log.one_rm} kg'
        )
        return redirect('exercise_progress', exercise_id=log.exercise.pk)
    return render(request, 'gym/log_form.html', {'form': form})


@login_required
def log_delete(request, pk):
    log = get_object_or_404(ExerciseLog, pk=pk, user=request.user)
    exercise_id = log.exercise.pk
    if request.method == 'POST':
        log.delete()
        messages.success(request, 'Log eliminato.')
    return redirect('exercise_progress', exercise_id=exercise_id)


# ─── Progress ─────────────────────────────────────────────────────────────────

@login_required
def exercise_progress(request, exercise_id):
    """
    Visualizza lo storico del 1RM per un esercizio con filtro temporale.
    Il best 1RM è sempre calcolato sull'intero storico (all-time).
    Default: ultimi 365 giorni.
    """
    from datetime import timedelta

    exercise = get_object_or_404(Exercise, pk=exercise_id)

    # Tutti i log — usati per best all-time e conteggio totale
    all_logs = (
        ExerciseLog.objects
        .filter(user=request.user, exercise=exercise)
        .order_by('date', 'id')
    )

    if not all_logs.exists():
        messages.info(request, f'Nessun log trovato per "{exercise.name}".')

    best = all_logs.aggregate(best_one_rm=Max('one_rm'))['best_one_rm']
    total_log_count = all_logs.count()

    # ── Filtro temporale ──────────────────────────────────────────
    PERIODS = {'3m': 90, '6m': 180, '1y': 365, 'all': None}
    period = request.GET.get('period', '1y')
    if period not in PERIODS:
        period = '1y'

    days = PERIODS[period]
    if days is not None:
        cutoff = date.today() - timedelta(days=days)
        logs = all_logs.filter(date__gte=cutoff)
    else:
        logs = all_logs

    # Dati per Chart.js
    chart_data = list(logs.values('date', 'one_rm', 'weight', 'reps', 'sets'))
    for entry in chart_data:
        entry['date'] = entry['date'].strftime('%d/%m/%Y')
        entry['one_rm'] = round(float(entry['one_rm']), 2)
        entry['weight'] = round(float(entry['weight']), 2)

    PERIOD_LABELS = {
        '3m':  '3 mesi',
        '6m':  '6 mesi',
        '1y':  '1 anno',
        'all': 'Tutto',
    }
    return render(request, 'gym/progress.html', {
        'exercise': exercise,
        'logs': logs.order_by('-date', '-id'),
        'best_one_rm': best,
        'chart_data': json.dumps(chart_data),
        'log_count': logs.count(),
        'total_log_count': total_log_count,
        'period': period,
        'period_label': PERIOD_LABELS[period],
        'periods': list(PERIOD_LABELS.items()),
    })



@login_required
def progress_overview(request):
    """
    Panoramica di tutti gli esercizi loggati dall'utente,
    con il miglior 1RM per ciascuno.
    """
    exercise_ids = (
    ExerciseLog.objects
    .filter(user=request.user)
    .order_by('exercise_id')   # annulla l'ordinamento default prima del distinct
    .values_list('exercise_id', flat=True)
    .distinct()
)
    exercises_with_best = []
    for ex_id in exercise_ids:
        exercise = Exercise.objects.get(pk=ex_id)
        best = ExerciseLog.objects.filter(
            user=request.user, exercise=exercise
        ).aggregate(best=Max('one_rm'))['best']
        last_log = ExerciseLog.objects.filter(
            user=request.user, exercise=exercise
        ).order_by('-date', '-id').first()
        exercises_with_best.append({
            'exercise': exercise,
            'best_one_rm': best,
            'last_log': last_log,
        })

    exercises_with_best.sort(key=lambda x: x['exercise'].muscle_group)

    return render(request, 'gym/progress_overview.html', {
        'exercises': exercises_with_best,
    })


# ─── Exercises ────────────────────────────────────────────────────────────────

@login_required
def exercise_list(request):
    muscle_filter = request.GET.get('muscle', '')
    exercises = Exercise.objects.all()
    if muscle_filter:
        exercises = exercises.filter(muscle_group=muscle_filter)

    from .models import MuscleGroup
    return render(request, 'gym/exercise_list.html', {
        'exercises': exercises,
        'muscle_groups': MuscleGroup.choices,
        'selected_muscle': muscle_filter,
    })


@login_required
def exercise_autocomplete(request):
    """
    Endpoint JSON per l'autocompletamento degli esercizi.
    Cerca per sottostringa (icontains) su nome e gruppo muscolare.
    Restituisce max 10 risultati.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'results': []})

    exercises = (
        Exercise.objects
        .filter(name__icontains=query)
        .order_by('muscle_group', 'name')[:10]
        .values('id', 'name', 'muscle_group')
    )
    results = [
        {
            'id': ex['id'],
            'name': ex['name'],
            'muscle_group': dict(
                __import__('gym.models', fromlist=['MuscleGroup']).MuscleGroup.choices
            ).get(ex['muscle_group'], ex['muscle_group']),
        }
        for ex in exercises
    ]
    return JsonResponse({'results': results})


@login_required
def exercise_create(request):
    form = ExerciseForm(request.POST or None)
    if form.is_valid():
        exercise = form.save(commit=False)
        exercise.created_by = request.user
        exercise.save()
        messages.success(request, f'Esercizio "{exercise.name}" aggiunto.')
        return redirect('exercise_list')
    return render(request, 'gym/exercise_form.html', {'form': form})

# ─── PWA ──────────────────────────────────────────────────────────────────────

def service_worker(request):
    """
    Serve il service worker dalla root (/sw.js) in modo che possa
    controllare l'intero sito. Un SW servito da /static/ non può
    avere scope /, quindi serve questa view dedicata.
    """
    import os
    from django.http import HttpResponse
    from django.contrib.staticfiles import finders
    sw_path = finders.find('gym/sw.js')
    if sw_path and os.path.exists(sw_path):
        with open(sw_path, 'r') as f:
            content = f.read()
    else:
        content = ''
    response = HttpResponse(content, content_type='application/javascript')
    response['Service-Worker-Allowed'] = '/'
    response['Cache-Control'] = 'no-cache'
    return response

