import io
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Max, Count, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from .forms import (
    WorkoutPlanForm,
    PlannedExerciseForm,
    ExerciseLogForm,
    ExerciseForm,
    PlanFolderForm,
)

from .models import (
    Exercise, WorkoutPlan, PlannedExercise, ExerciseLog,
    MuscleGroup, PlanFolder, WorkoutSession,
)


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

    # Aggrega per gruppo muscolare, escludendo esercizi con <2 log e quelli
    # a corpo libero (niente 1RM da tracciare per loro)
    mg_exercises = defaultdict(list)
    for exercise, logs in exercise_logs.items():
        if len(logs) < 2 or exercise.is_bodyweight:
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

    week_start = date.today() - timedelta(days=date.today().weekday())
    sessions_this_week = all_logs.filter(date__gte=week_start).count()
    active_plans_count = WorkoutPlan.objects.filter(user=request.user, is_active=True).count()

    hour = timezone.localtime().hour
    if hour < 6:
        greeting = 'Buonanotte'
    elif hour < 12:
        greeting = 'Buongiorno'
    elif hour < 18:
        greeting = 'Buon pomeriggio'
    else:
        greeting = 'Buonasera'

    return render(request, 'gym/dashboard.html', {
        'muscle_groups': muscle_groups,
        'sessions_this_week': sessions_this_week,
        'exercises_tracked': len(exercise_logs),
        'active_plans_count': active_plans_count,
        'greeting': greeting,
    })


# ─── Workout Plans ────────────────────────────────────────────────────────────

@login_required
def plan_list(request):
    base_qs = WorkoutPlan.objects.filter(user=request.user).annotate(
        exercise_count=Count('planned_exercises')
    )
    active_qs = base_qs.filter(is_active=True)

    folders = list(
        PlanFolder.objects.filter(user=request.user).prefetch_related(
            Prefetch('plans', queryset=active_qs.order_by('order'))
        )
    )
    unfoldered_plans = active_qs.filter(folder__isnull=True)

    root_nodes = sorted(
        [{'type': 'folder', 'obj': f} for f in folders]
        + [{'type': 'plan', 'obj': p} for p in unfoldered_plans],
        key=lambda n: n['obj'].order
    )

    return render(request, 'gym/plan_list.html', {
        'root_nodes': root_nodes,
        'archived_plans': base_qs.filter(is_active=False),
        'has_active_plans': active_qs.exists(),
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
    today = timezone.localdate()
    return render(request, 'gym/plan_detail.html', {
        'plan': plan,
        'planned': planned,
        # Se la sessione di oggi è già registrata il modale non deve
        # comparire e il bottone mostra lo stato "già registrato".
        'session_logged_today': WorkoutSession.objects.filter(
            user=request.user, date=today, plan_name=plan.name
        ).exists(),
        'today': today,
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
    """
    Riordina il livello radice (cartelle + schede sciolte, interleaved).
    Payload: {"order": [{"type": "plan"|"folder", "id": N}, ...]}
    Una scheda inclusa qui torna sempre "sciolta" (folder=None) — è così
    che si gestisce anche il trascinamento fuori da una cartella.
    Validazione solo di ownership: un payload parziale non è un errore
    (a differenza della vecchia implementazione, che pretendeva un match
    esatto con *tutte* le schede dell'utente comprese le archiviate — bug
    che faceva fallire ogni riordino appena esisteva una scheda archiviata,
    dato che il client invia solo le schede attive mostrate in pagina).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        order = data.get('order', [])
        plan_ids = [entry['id'] for entry in order if entry.get('type') == 'plan']
        folder_ids = [entry['id'] for entry in order if entry.get('type') == 'folder']
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    valid_plan_ids = set(WorkoutPlan.objects.filter(user=request.user).values_list('id', flat=True))
    valid_folder_ids = set(PlanFolder.objects.filter(user=request.user).values_list('id', flat=True))
    if not set(plan_ids) <= valid_plan_ids or not set(folder_ids) <= valid_folder_ids:
        return JsonResponse({'error': 'Invalid IDs'}, status=400)

    for position, entry in enumerate(order):
        if entry.get('type') == 'plan':
            WorkoutPlan.objects.filter(pk=entry['id'], user=request.user).update(order=position, folder=None)
        elif entry.get('type') == 'folder':
            PlanFolder.objects.filter(pk=entry['id'], user=request.user).update(order=position)
    return JsonResponse({'status': 'ok'})


@login_required
def plan_folder_reorder(request, pk):
    """
    Riordina le schede dentro una cartella. Include anche il caso "sposta
    una scheda dentro questa cartella": basta includerne l'id nel payload.
    Payload: {"order": [plan_id, ...]}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    folder = get_object_or_404(PlanFolder, pk=pk, user=request.user)
    try:
        data = json.loads(request.body)
        ordered_ids = data.get('order', [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    valid_ids = set(WorkoutPlan.objects.filter(user=request.user).values_list('id', flat=True))
    if not set(ordered_ids) <= valid_ids:
        return JsonResponse({'error': 'Invalid plan IDs'}, status=400)
    for position, plan_id in enumerate(ordered_ids):
        WorkoutPlan.objects.filter(pk=plan_id, user=request.user).update(order=position, folder=folder)
    return JsonResponse({'status': 'ok'})


@login_required
def plan_folder_create(request):
    if request.method == 'POST':
        form = PlanFolderForm(request.POST)
        if form.is_valid():
            folder = form.save(commit=False)
            folder.user = request.user
            last_order = PlanFolder.objects.filter(user=request.user).aggregate(Max('order'))['order__max']
            folder.order = (last_order or 0) + 1
            folder.save()
            messages.success(request, f'Cartella "{folder.name}" creata.')
        else:
            messages.error(request, 'Nome cartella non valido.')
    return redirect('plan_list')


@login_required
def plan_folder_rename(request, pk):
    folder = get_object_or_404(PlanFolder, pk=pk, user=request.user)
    if request.method == 'POST':
        form = PlanFolderForm(request.POST, instance=folder)
        if form.is_valid():
            form.save()
            messages.success(request, 'Cartella rinominata.')
        else:
            messages.error(request, 'Nome cartella non valido.')
    return redirect('plan_list')


@login_required
def plan_folder_delete(request, pk):
    folder = get_object_or_404(PlanFolder, pk=pk, user=request.user)
    if request.method == 'POST':
        name = folder.name
        folder.delete()  # SET_NULL sulle schede contenute: non vengono eliminate
        messages.success(request, f'Cartella "{name}" eliminata. Le schede al suo interno sono tornate fuori.')
    return redirect('plan_list')


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
        if log.one_rm is not None:
            messages.success(request, f'Log salvato — 1RM teorico: {log.one_rm} kg')
        else:
            messages.success(request, 'Log salvato.')
        from_page = request.POST.get('from')
        plan_pk = request.POST.get('plan')
        if from_page == 'plan' and plan_pk:
            return redirect('plan_detail', pk=plan_pk)
        return redirect('exercise_progress', exercise_id=log.exercise.pk)
    bodyweight_map = json.dumps({ex.pk: ex.is_bodyweight for ex in Exercise.objects.all()})
    return render(request, 'gym/log_form.html', {'form': form, 'bodyweight_map': bodyweight_map})

@login_required
def log_edit(request, pk):
    log = get_object_or_404(ExerciseLog, pk=pk, user=request.user)
    form = ExerciseLogForm(request.POST or None, instance=log, user=request.user)
    if form.is_valid():
        form.save()
        if log.one_rm is not None:
            messages.success(request, f'Log aggiornato — 1RM: {log.one_rm} kg')
        else:
            messages.success(request, 'Log aggiornato.')
        return redirect('exercise_progress', exercise_id=log.exercise.pk)
    bodyweight_map = json.dumps({ex.pk: ex.is_bodyweight for ex in Exercise.objects.all()})
    return render(request, 'gym/log_form.html', {
        'form': form,
        'editing': True,
        'log': log,
        'bodyweight_map': bodyweight_map,
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
    best_reps = all_logs.aggregate(best_reps=Max('reps'))['best_reps']
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
        entry['one_rm'] = round(float(entry['one_rm']), 2) if entry['one_rm'] is not None else None
        entry['weight'] = round(float(entry['weight']), 2) if entry['weight'] is not None else None

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
        'best_reps': best_reps,
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
        best_reps = ExerciseLog.objects.filter(
            user=request.user, exercise=exercise
        ).aggregate(best=Max('reps'))['best']
        last_log = ExerciseLog.objects.filter(
            user=request.user, exercise=exercise
        ).order_by('-date', '-id').first()
        exercises_with_best.append({
            'exercise': exercise,
            'best_one_rm': best,
            'best_reps': best_reps,
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
        .values('id', 'name', 'muscle_group', 'is_bodyweight')
    )
    results = [
        {
            'id': ex['id'],
            'name': ex['name'],
            'muscle_group': dict(
                __import__('gym.models', fromlist=['MuscleGroup']).MuscleGroup.choices
            ).get(ex['muscle_group'], ex['muscle_group']),
            'is_bodyweight': ex['is_bodyweight'],
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
    return render(request, 'gym/exercise_form.html', {'form': form, 'action': 'Crea'})

@login_required
def exercise_edit(request, pk):
    exercise = get_object_or_404(Exercise, pk=pk)
    form = ExerciseForm(request.POST or None, instance=exercise)
    if form.is_valid():
        form.save()
        messages.success(request, f'Esercizio "{exercise.name}" aggiornato.')
        return redirect('exercise_list')
    return render(request, 'gym/exercise_form.html', {'form': form, 'action': 'Modifica', 'exercise': exercise})

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
    writer.writerow(['esercizio', 'gruppo_muscolare', 'serie', 'ripetizioni', 'ordine', 'note', 'corpo_libero'])
    for pe in planned:
        writer.writerow([
            pe.exercise.name,
            pe.exercise.muscle_group,
            pe.target_sets,
            pe.target_reps,
            pe.order,
            pe.notes or '',
            'si' if pe.exercise.is_bodyweight else 'no',
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
            # Colonna opzionale (assente nei CSV esportati prima di questa
            # funzionalità): esercizi senza questa colonna sono considerati
            # "con pesi", coerente col default del modello.
            is_bodyweight = row[6].strip().lower() in ('si', 'sì', 'yes', 'true', '1') if len(row) > 6 else False

            # Crea l'esercizio se non esiste
            exercise, was_created = Exercise.objects.get_or_create(
                name=ex_name,
                defaults={
                    'muscle_group': ex_muscle or MuscleGroup.FULL_BODY,
                    'is_bodyweight': is_bodyweight,
                }
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



# ─── Sessioni di allenamento e calendario ─────────────────────────────────────

# Etichette in italiano — LANGUAGE_CODE è it-it ma il modulo calendar di
# Python usa la locale di sistema, che sul server non è garantita.
MONTH_NAMES_IT = [
    'Gennaio', 'Febbraio', 'Marzo', 'Aprile', 'Maggio', 'Giugno',
    'Luglio', 'Agosto', 'Settembre', 'Ottobre', 'Novembre', 'Dicembre',
]
WEEKDAY_NAMES_IT = ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom']

# Etichette che identificano una riga di intestazione nel CSV importato.
HEADER_LABELS = {'data', 'date', 'giorno', 'data allenamento'}


def _parse_session_date(raw):
    """
    Accetta sia il formato ISO (AAAA-MM-GG) sia quello italiano (GG/MM/AAAA),
    perché i CSV esportati da Excel in locale italiana usano il secondo.
    """
    raw = (raw or '').strip()
    if not raw:
        return None
    parsed = parse_date(raw)
    if parsed:
        return parsed
    for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


# Separatori accettati nei CSV importati: la virgola è lo standard, ma
# Excel in locale italiana esporta col punto e virgola, e capita di ricevere
# file separati da tabulazione o pipe.
CSV_DELIMITERS = [',', ';', '\t', '|']


# Come mostrare i separatori nei messaggi d'errore.
DELIMITER_LABELS = {',': 'virgola', ';': 'punto e virgola', '\t': 'tabulazione', '|': 'barra verticale'}


def _detect_delimiter(content):
    """
    Sceglie il separatore provando davvero a interpretare il file con
    ciascun candidato e premiando quello che produce più righe valide
    (almeno due colonne e una data riconoscibile nella prima).

    Contare le occorrenze non basterebbe: in un file separato da punto e
    virgola un nome scheda come "Push, Pull, Legs" contiene più virgole che
    punti e virgola e farebbe scegliere il separatore sbagliato. csv.Sniffer
    a sua volta è inaffidabile su file di due sole colonne.
    """
    import csv

    best_delimiter, best_score = ',', -1
    for delimiter in CSV_DELIMITERS:
        rows = [
            row for row in csv.reader(io.StringIO(content), delimiter=delimiter)
            if any(cell.strip() for cell in row)
        ]
        # Una riga vale se ha due colonne e una data leggibile: è esattamente
        # lo schema che l'import si aspetta.
        score = sum(
            1 for row in rows
            if len(row) >= 2 and _parse_session_date(row[0]) is not None
        )
        # A parità di righe valide vince il primo candidato (la virgola),
        # che è il formato canonico del template scaricabile.
        if score > best_score:
            best_delimiter, best_score = delimiter, score

    if best_score > 0:
        return best_delimiter

    # Nessun candidato produce righe valide (es. solo intestazione, o date
    # tutte malformate): ripiega su quello che almeno spezza le righe in due
    # colonne, così l'utente riceve errori di data invece di "manca una colonna".
    for delimiter in CSV_DELIMITERS:
        rows = [
            row for row in csv.reader(io.StringIO(content), delimiter=delimiter)
            if any(cell.strip() for cell in row)
        ]
        if rows and all(len(row) >= 2 for row in rows):
            return delimiter

    return ','


@login_required
def session_template_download(request):
    """Scarica un CSV di esempio già nel formato accettato dall'import."""
    import csv

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="gymit_template_allenamenti.csv"'
    response.write('\ufeff')  # BOM per compatibilità Excel

    # Il template usa la virgola: è il separatore più portabile e l'import
    # riconosce comunque gli altri se l'utente risalva il file con Excel.
    writer = csv.writer(response)
    writer.writerow(['data', 'scheda'])

    today = timezone.localdate()
    plan_names = list(
        WorkoutPlan.objects
        .filter(user=request.user)
        .order_by('order')
        .values_list('name', flat=True)[:3]
    ) or ['Push Pull Legs', 'Full Body']

    # Righe di esempio con le schede reali dell'utente, così deve solo
    # correggere le date invece di indovinare i nomi.
    for i, name in enumerate(plan_names):
        writer.writerow([(today - timedelta(days=i * 2 + 2)).isoformat(), name])

    return response


@login_required
def session_create(request):
    """
    Registra una sessione di allenamento (dal modale o dal bottone).

    Idempotente: riconfermare la stessa scheda nello stesso giorno non crea
    duplicati né produce un errore — l'utente ottiene comunque il risultato
    che voleva.
    """
    if request.method != 'POST':
        return redirect('plan_list')

    plan = get_object_or_404(
        WorkoutPlan, pk=request.POST.get('plan_id'), user=request.user
    )

    session_date = timezone.localdate()
    raw_date = request.POST.get('date', '').strip()
    if raw_date:
        parsed = _parse_session_date(raw_date)
        if parsed is None:
            messages.error(request, 'Data non valida.')
            return redirect('plan_detail', pk=plan.pk)
        if parsed > timezone.localdate():
            messages.error(request, 'Non puoi registrare un allenamento nel futuro.')
            return redirect('plan_detail', pk=plan.pk)
        session_date = parsed

    _, created = WorkoutSession.objects.get_or_create(
        user=request.user,
        date=session_date,
        plan_name=plan.name,
        defaults={'plan': plan},
    )

    if created:
        messages.success(request, f'Allenamento registrato: {plan.name}.')
    else:
        messages.info(request, 'Questo allenamento era già registrato per oggi.')

    return redirect('plan_detail', pk=plan.pk)


@login_required
def session_delete(request, pk):
    """Elimina una sessione registrata (dal modale del calendario)."""
    session = get_object_or_404(WorkoutSession, pk=pk, user=request.user)
    if request.method != 'POST':
        return redirect('workout_calendar')

    session_date = session.date
    session.delete()
    messages.success(request, 'Sessione eliminata.')
    return redirect(
        f"{reverse('workout_calendar')}?year={session_date.year}&month={session_date.month}"
    )


@login_required
def workout_calendar(request):
    """
    Calendario mensile delle giornate di allenamento.

    La griglia (settimana lun–dom) è costruita lato server: il template resta
    dichiarativo e il calendario si vede anche senza JavaScript.
    """
    import calendar as pycalendar

    today = timezone.localdate()

    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
    except (TypeError, ValueError):
        year, month = today.year, today.month

    # Fuori range → torna al mese corrente invece di sollevare eccezioni.
    if not (1 <= month <= 12) or not (1900 <= year <= 2200):
        year, month = today.year, today.month

    sessions = (
        WorkoutSession.objects
        .filter(user=request.user, date__year=year, date__month=month)
        .order_by('date', 'id')
    )

    # Mappa giorno → sessioni, per marcare le celle senza query per cella.
    sessions_by_day = defaultdict(list)
    for session in sessions:
        sessions_by_day[session.date.day].append(session)

    cal = pycalendar.Calendar(firstweekday=0)  # 0 = lunedì
    weeks = []
    for week in cal.monthdayscalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                row.append(None)  # cella vuota (mese precedente/successivo)
                continue
            cell_date = date(year, month, day)
            row.append({
                'day': day,
                'date': cell_date,
                'sessions': sessions_by_day.get(day, []),
                'is_today': cell_date == today,
                'is_future': cell_date > today,
            })
        weeks.append(row)

    prev_month_date = date(year, month, 1) - timedelta(days=1)
    last_day = pycalendar.monthrange(year, month)[1]
    next_month_date = date(year, month, last_day) + timedelta(days=1)

    # Giorni distinti allenati, base per tutte le statistiche.
    unique_dates = sorted(
        set(
            WorkoutSession.objects
            .filter(user=request.user)
            .values_list('date', flat=True)
        ),
        reverse=True,
    )

    # Settimana corrente lunedì–domenica, coerente con la griglia del calendario.
    week_start = today - timedelta(days=today.weekday())
    days_this_week = sum(1 for d in unique_dates if week_start <= d <= today)

    # Media settimanale sull'intero storico: giorni allenati diviso le settimane
    # trascorse dal primo allenamento a oggi. La settimana in corso rientra nel
    # conteggio anche se incompleta — è il numero che l'utente si aspetta di
    # veder salire man mano che si allena, non una media solo su settimane chiuse.
    weekly_average = 0
    if unique_dates:
        first_date = unique_dates[-1]
        first_week_start = first_date - timedelta(days=first_date.weekday())
        weeks_elapsed = (week_start - first_week_start).days // 7 + 1
        weekly_average = round(len(unique_dates) / weeks_elapsed, 1)

    return render(request, 'gym/calendar.html', {
        'weeks': weeks,
        'year': year,
        'month': month,
        'month_name': MONTH_NAMES_IT[month - 1],
        'weekday_names': WEEKDAY_NAMES_IT,
        'prev_year': prev_month_date.year,
        'prev_month': prev_month_date.month,
        'next_year': next_month_date.year,
        'next_month': next_month_date.month,
        'today': today,
        'days_trained_this_month': len(sessions_by_day),
        'days_this_week': days_this_week,
        'weekly_average': weekly_average,
        # Non mostrato come statistica: serve solo a decidere lo stato vuoto.
        'total_days_trained': len(unique_dates),
        'is_current_month': (year, month) == (today.year, today.month),
    })


@login_required
def session_day_detail(request, year, month, day):
    """Dettaglio JSON di una giornata — alimenta il modale del calendario."""
    try:
        target = date(year, month, day)
    except ValueError:
        return JsonResponse({'error': 'Data non valida.'}, status=400)

    sessions = WorkoutSession.objects.filter(user=request.user, date=target)
    return JsonResponse({
        'date': target.isoformat(),
        'date_label': f'{day} {MONTH_NAMES_IT[month - 1]} {year}',
        'sessions': [
            {
                'id': s.id,
                'plan_name': s.plan_name,
                'plan_id': s.plan_id,
                'delete_url': reverse('session_delete', args=[s.id]),
                'plan_url': reverse('plan_detail', args=[s.plan_id]) if s.plan_id else None,
            }
            for s in sessions
        ],
    })


@login_required
def session_import(request):
    """
    Importa allenamenti passati da CSV (colonne: data, nome scheda).

    Le schede sconosciute non vengono create: la sessione conserva solo il
    nome, così lo storico è completo senza riempire la lista schede di voci
    fantasma provenienti dal passato.
    """
    import csv
    import io

    if request.method != 'POST':
        return render(request, 'gym/session_import.html')

    csv_file = request.FILES.get('csv_file')
    if not csv_file:
        messages.error(request, 'Nessun file selezionato.')
        return render(request, 'gym/session_import.html')

    if not csv_file.name.lower().endswith('.csv'):
        messages.error(request, 'Il file deve essere in formato CSV.')
        return render(request, 'gym/session_import.html')

    try:
        content = csv_file.read().decode('utf-8-sig')  # utf-8-sig gestisce il BOM
    except UnicodeDecodeError:
        messages.error(request, 'Impossibile leggere il file: salvalo con codifica UTF-8.')
        return render(request, 'gym/session_import.html')

    delimiter = _detect_delimiter(content)
    reader = csv.reader(io.StringIO(content), delimiter=delimiter)
    rows = [row for row in reader if any(cell.strip() for cell in row)]

    if not rows:
        messages.error(request, 'Il file CSV è vuoto.')
        return render(request, 'gym/session_import.html')

    # Intestazione opzionale: la riconosco dall'etichetta, non dal fatto che
    # la prima cella non sia una data — altrimenti una riga con data scritta
    # male verrebbe scartata in silenzio invece di essere segnalata.
    if rows[0] and rows[0][0].strip().lower() in HEADER_LABELS:
        rows = rows[1:]

    if not rows:
        messages.error(request, 'Il file CSV non contiene righe di dati.')
        return render(request, 'gym/session_import.html')

    today = timezone.localdate()
    # Le schede esistenti vengono ricollegate per nome, così il calendario
    # può linkare alla scheda quando questa esiste ancora.
    plans_by_name = {p.name: p for p in WorkoutPlan.objects.filter(user=request.user)}

    to_create = []
    seen = set()
    errors = []
    skipped_future = 0

    for i, row in enumerate(rows, start=1):
        if len(row) < 2:
            errors.append(
                f'Riga {i}: servono due colonne (data e nome scheda) '
                f'separate da {DELIMITER_LABELS.get(delimiter, delimiter)}.'
            )
            continue

        raw_date = row[0].strip()
        plan_name = row[1].strip()

        if not plan_name:
            errors.append(f'Riga {i}: nome scheda mancante.')
            continue
        if len(plan_name) > 100:
            errors.append(f'Riga {i}: nome scheda troppo lungo (max 100 caratteri).')
            continue

        parsed = _parse_session_date(raw_date)
        if parsed is None:
            errors.append(
                f'Riga {i}: data non valida (usa AAAA-MM-GG oppure GG/MM/AAAA).'
            )
            continue
        if parsed > today:
            skipped_future += 1
            continue

        key = (parsed, plan_name)
        if key in seen:
            continue  # duplicato interno al file
        seen.add(key)

        to_create.append(WorkoutSession(
            user=request.user,
            date=parsed,
            plan_name=plan_name,
            plan=plans_by_name.get(plan_name),
        ))

    if not to_create:
        messages.error(request, 'Nessuna riga valida da importare.')
        for err in errors[:5]:
            messages.warning(request, err)
        return render(request, 'gym/session_import.html')

    # Conta quante sessioni esistevano già, per dare un resoconto onesto:
    # ignore_conflicts non dice quali righe sono state effettivamente inserite.
    existing = set(
        WorkoutSession.objects
        .filter(user=request.user, date__in=[s.date for s in to_create])
        .values_list('date', 'plan_name')
    )
    new_count = sum(1 for s in to_create if (s.date, s.plan_name) not in existing)

    WorkoutSession.objects.bulk_create(to_create, ignore_conflicts=True)

    duplicates = len(to_create) - new_count
    msg = f'{new_count} allenamenti importati.'
    if duplicates:
        msg += f' {duplicates} già presenti sono stati ignorati.'
    messages.success(request, msg)

    if skipped_future:
        messages.info(request, f'{skipped_future} righe con data futura ignorate.')
    for err in errors[:5]:
        messages.warning(request, err)
    if len(errors) > 5:
        messages.warning(request, f'... e altri {len(errors) - 5} errori.')

    return redirect('workout_calendar')
