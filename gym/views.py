import json
from datetime import date

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Max, Count
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse

from .forms import (
    WorkoutPlanForm,
    PlannedExerciseForm,
    ExerciseLogForm,
    ExerciseForm,
)

from .models import Exercise, WorkoutPlan, PlannedExercise, ExerciseLog, MuscleGroup


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def dashboard(request):
    """Dashboard aggregata per gruppo muscolare con sparkline 1RM."""
    import json
    from collections import defaultdict
    from .models import MuscleGroup

    # Tutti i log dell'utente in ordine cronologico per esercizio.
    # order_by esplicito: il default del modello è per data desc e
    # creerebbe liste invertite nel defaultdict.
    all_logs = (
        ExerciseLog.objects
        .filter(user=request.user)
        .select_related('exercise')
        .order_by('exercise_id', 'date', 'id')
    )

    # Raggruppa log per esercizio (mantiene l'ordine cronologico)
    exercise_logs = defaultdict(list)
    for log in all_logs:
        exercise_logs[log.exercise].append(log)

    # Aggrega per gruppo muscolare, escludendo esercizi con <2 log
    mg_exercises = defaultdict(list)
    for exercise, logs in exercise_logs.items():
        if len(logs) < 2:
            continue
        first_1rm = float(logs[0].one_rm)
        last_1rm = float(logs[-1].one_rm)
        variation_pct = round(
            ((last_1rm - first_1rm) / first_1rm * 100) if first_1rm else 0.0, 1
        )
        chart_data = json.dumps([
            {'date': log.date.strftime('%d/%m'), 'one_rm': float(log.one_rm)}
            for log in logs
        ])
        mg_exercises[exercise.muscle_group].append({
            'exercise': exercise,
            'last_one_rm': last_1rm,
            'variation_pct': variation_pct,
            'chart_data': chart_data,
            'log_count': len(logs),
        })

    mg_display = dict(MuscleGroup.choices)
    muscle_groups = []
    for mg_key, exercises in mg_exercises.items():
        exercises.sort(key=lambda x: x['last_one_rm'], reverse=True)
        avg_variation = round(
            sum(e['variation_pct'] for e in exercises) / len(exercises), 1
        )
        muscle_groups.append({
            'name': mg_display.get(mg_key, mg_key),
            'key': mg_key,
            'avg_variation': avg_variation,
            'exercises': exercises,
            'total_logs': sum(e['log_count'] for e in exercises),
        })

    muscle_groups.sort(key=lambda x: x['total_logs'], reverse=True)

    return render(request, 'gym/dashboard.html', {
        'muscle_groups': muscle_groups,
    })


# ─── Workout Plans ────────────────────────────────────────────────────────────

@login_required
def plan_list(request):
    base_qs = WorkoutPlan.objects.filter(user=request.user).annotate(
        exercise_count=Count('planned_exercises')
    )
    return render(request, 'gym/plan_list.html', {
        'active_plans': base_qs.filter(is_active=True),
        'archived_plans': base_qs.filter(is_active=False),
    })


@login_required
def plan_create(request):
    form = WorkoutPlanForm(request.POST or None)
    if form.is_valid():
        plan = form.save(commit=False)
        plan.user = request.user
        from django.db.models import Max
        last_order = WorkoutPlan.objects.filter(user=request.user).aggregate(Max('order'))['order__max']
        plan.order = (last_order or 0) + 1
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

@login_required
def plan_list_reorder(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        ordered_ids = data.get('order', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    valid_ids = set(WorkoutPlan.objects.filter(user=request.user).values_list('id', flat=True))
    if set(ordered_ids) != valid_ids:
        return JsonResponse({'error': 'Invalid plan IDs'}, status=400)
    for position, plan_id in enumerate(ordered_ids):
        WorkoutPlan.objects.filter(pk=plan_id, user=request.user).update(order=position)
    return JsonResponse({'status': 'ok'})


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
    plan_id = request.GET.get('plan')
    if exercise_id:
        initial['exercise'] = exercise_id
    initial['date'] = date.today()

    # Pre-compila serie/ripetizioni dai target della scheda
    if exercise_id and plan_id and request.GET.get('from') == 'plan':
        try:
            pe = PlannedExercise.objects.get(
                plan_id=plan_id, exercise_id=exercise_id, plan__user=request.user
            )
            initial['sets'] = pe.target_sets
            initial['reps'] = pe.target_reps
        except PlannedExercise.DoesNotExist:
            pass

    form = ExerciseLogForm(request.POST or None, user=request.user, initial=initial)
    if form.is_valid():
        log = form.save(commit=False)
        log.user = request.user
        log.save()
        messages.success(
            request,
            f'Log salvato — 1RM teorico: {log.one_rm} kg'
        )
        from_page = request.POST.get('from')
        plan_pk = request.POST.get('plan')
        if from_page == 'plan' and plan_pk:
            return redirect('plan_detail', pk=plan_pk)
        return redirect('exercise_progress', exercise_id=log.exercise.pk)
    return render(request, 'gym/log_form.html', {'form': form})

@login_required
def log_edit(request, pk):
    log = get_object_or_404(ExerciseLog, pk=pk, user=request.user)
    form = ExerciseLogForm(request.POST or None, instance=log, user=request.user)
    if form.is_valid():
        form.save()
        messages.success(request, f'Log aggiornato — 1RM: {log.one_rm} kg')
        return redirect('exercise_progress', exercise_id=log.exercise.pk)
    return render(request, 'gym/log_form.html', {
        'form': form,
        'editing': True,
        'log': log,
    })


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
    Default: tutto lo storico.
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
    period = request.GET.get('period', 'all')
    if period not in PERIODS:
        period = 'all'

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

@login_required
def exercise_delete(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    if request.method == 'POST':
        name = exercise.name
        exercise.delete()  # CASCADE elimina anche tutti gli ExerciseLog associati
        messages.success(request, f'"{name}" e tutti i log associati sono stati eliminati.')
    return redirect('exercise_list')


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
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

# ─── Import/Export Schede ─────────────────────────────────────────────────

@login_required
def plan_export(request, pk):
    """Esporta una scheda come CSV."""
    import csv
    plan = get_object_or_404(WorkoutPlan, pk=pk, user=request.user)
    planned = plan.planned_exercises.select_related('exercise').order_by('order')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="gymit_{plan.name}.csv"'
    response.write('\ufeff')  # BOM per compatibilità Excel

    writer = csv.writer(response)
    writer.writerow(['piano', plan.name, plan.description or ''])
    writer.writerow(['esercizio', 'gruppo_muscolare', 'serie', 'ripetizioni', 'ordine', 'note'])
    for pe in planned:
        writer.writerow([
            pe.exercise.name,
            pe.exercise.muscle_group,
            pe.target_sets,
            pe.target_reps,
            pe.order,
            pe.notes or '',
        ])
    return response


@login_required
def plan_import(request):
    """Importa una scheda da CSV."""
    import csv
    import io

    if request.method != 'POST':
        return render(request, 'gym/plan_import.html')

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, 'Nessun file selezionato.')
        return render(request, 'gym/plan_import.html')

    if not csv_file.name.endswith('.csv'):
        messages.error(request, 'Il file deve essere in formato CSV.')
        return render(request, 'gym/plan_import.html')

    try:
        content = csv_file.read().decode('utf-8-sig')  # utf-8-sig gestisce il BOM
        reader = csv.reader(io.StringIO(content))
        rows = list(reader)

        if len(rows) < 2:
            messages.error(request, 'Il file CSV è vuoto o non valido.')
            return render(request, 'gym/plan_import.html')

        # Prima riga: piano, nome, descrizione
        first_row = rows[0]
        if len(first_row) < 2 or first_row[0] != 'piano':
            messages.error(request, 'Formato CSV non valido. Usa un file esportato da GymIt.')
            return render(request, 'gym/plan_import.html')

        plan_name = first_row[1].strip()
        plan_description = first_row[2].strip() if len(first_row) > 2 else ''

        # Seconda riga: intestazioni — salta
        # Righe successive: esercizi
        exercise_rows = rows[2:]
        if not exercise_rows:
            messages.error(request, 'La scheda non contiene esercizi.')
            return render(request, 'gym/plan_import.html')

        # Crea la scheda
        from django.db.models import Max as DMax
        last_order = WorkoutPlan.objects.filter(user=request.user).aggregate(DMax('order'))['order__max']
        plan = WorkoutPlan.objects.create(
            user=request.user,
            name=plan_name,
            description=plan_description,
            order=(last_order or 0) + 1,
        )

        created_exercises = []
        for i, row in enumerate(exercise_rows, start=1):
            if len(row) < 4:
                plan.delete()
                messages.error(request, f'Riga {i+2} non valida: dati insufficienti.')
                return render(request, 'gym/plan_import.html')

            ex_name = row[0].strip()
            ex_muscle = row[1].strip()
            try:
                target_sets = int(row[2])
                target_reps = int(row[3])
            except ValueError:
                plan.delete()
                messages.error(request, f'Riga {i+2}: serie e ripetizioni devono essere numeri interi.')
                return render(request, 'gym/plan_import.html')

            order = int(row[4]) if len(row) > 4 and row[4].strip().isdigit() else i
            notes = row[5].strip() if len(row) > 5 else ''

            # Crea l'esercizio se non esiste
            exercise, was_created = Exercise.objects.get_or_create(
                name=ex_name,
                defaults={'muscle_group': ex_muscle or MuscleGroup.FULL_BODY}
            )
            if was_created:
                created_exercises.append(ex_name)

            PlannedExercise.objects.create(
                plan=plan,
                exercise=exercise,
                target_sets=target_sets,
                target_reps=target_reps,
                order=order,
                notes=notes,
            )

        msg = f'Scheda "{plan_name}" importata con successo.'
        if created_exercises:
            msg += f' Esercizi creati automaticamente: {", ".join(created_exercises)}.'
        messages.success(request, msg)
        return redirect('plan_detail', pk=plan.pk)

    except Exception as e:
        messages.error(request, f'Errore durante l\'importazione: {str(e)}')
        return render(request, 'gym/plan_import.html')

