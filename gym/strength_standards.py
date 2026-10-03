"""
Strength standards: 1RM atteso per esercizio, sesso, peso corporeo e livello.

I dati stanno in strength_tables.py (tabelle di Strength Level per peso
corporeo, percentili della community: Principiante 5°, Novizio 20°,
Intermedio 50°, Avanzato 80°, Elite 95°). Qui c'è solo il calcolo.

Il peso corporeo cade quasi sempre tra due righe di tabella: il valore si
ricava per interpolazione lineare. Fuori dall'intervallo coperto dalle tabelle
(uomini 50–140 kg, donne 40–120 kg) si usa la riga estrema: estrapolare
darebbe numeri sempre meno attendibili man mano che ci si allontana dai dati.
"""

from .strength_tables import TABLES

# Dal più basso al più alto: l'ordine serve a stabilire il livello raggiunto.
LEVELS = ('beginner', 'novice', 'intermediate', 'advanced', 'elite')

# Nomi mostrati nell'app per scegliere lo standard di un esercizio.
STANDARD_LABELS = {
    'bench_press': 'Panca piana',
    'squat': 'Squat',
    'deadlift': 'Stacco da terra',
    'overhead_press': 'Military press / lento avanti',
    'barbell_row': 'Rematore con bilanciere',
    'incline_bench_press': 'Panca inclinata con bilanciere',
    'front_squat': 'Squat frontale',
    'romanian_deadlift': 'Stacco rumeno',
    'hip_thrust': 'Hip thrust',
    'close_grip_bench_press': 'Panca presa stretta',
    'barbell_curl': 'Curl con bilanciere',
    'sumo_deadlift': 'Stacco sumo',
}

STANDARDS = TABLES

# Coefficiente di riduzione per età (applicato dopo i 40 anni).
# Nota: non viene da Strength Level, che non pubblica correzioni per età.
AGE_FACTORS = [
    (0,  40, 1.00),
    (41, 45, 0.97),
    (46, 50, 0.93),
    (51, 55, 0.87),
    (56, 60, 0.82),
    (61, 65, 0.78),
    (66, 70, 0.73),
    (71, 999, 0.68),
]


def get_age_factor(age):
    """Restituisce il coefficiente di aggiustamento per età."""
    if age is None:
        return 1.0
    for lo, hi, factor in AGE_FACTORS:
        if lo <= age <= hi:
            return factor
    return 1.0


def _interpolate(rows, body_weight, level_index):
    """Valore della colonna `level_index` al peso dato, tra le righe adiacenti."""
    if body_weight <= rows[0][0]:
        return float(rows[0][level_index])
    if body_weight >= rows[-1][0]:
        return float(rows[-1][level_index])
    for lower, upper in zip(rows, rows[1:]):
        if lower[0] <= body_weight <= upper[0]:
            span = upper[0] - lower[0]
            weight_share = (body_weight - lower[0]) / span
            return lower[level_index] + (upper[level_index] - lower[level_index]) * weight_share


def compute_benchmark(standard_key, body_weight, sex, training_level, age=None):
    """
    Calcola il 1RM benchmark atteso in kg.

    Args:
        standard_key: chiave in STANDARDS (es. 'bench_press')
        body_weight: peso corporeo in kg (Decimal o float)
        sex: 'M' o 'F'
        training_level: uno dei livelli (es. 'intermediate')
        age: età in anni (opzionale)

    Returns:
        float con il benchmark in kg, oppure None se i dati sono insufficienti
    """
    if not standard_key or not body_weight or not sex:
        return None
    if training_level not in LEVELS:
        return None

    rows = STANDARDS.get(standard_key, {}).get(sex)
    if not rows:
        return None

    level_index = LEVELS.index(training_level) + 1  # la colonna 0 è il peso
    expected = _interpolate(rows, float(body_weight), level_index) * get_age_factor(age)
    return round(expected, 1)


def get_all_benchmarks(standard_key, body_weight, sex, age=None):
    """
    Restituisce il 1RM atteso in kg per ognuno dei livelli.
    Utile per mostrare all'utente dove si colloca rispetto a tutti.

    Returns:
        dict {livello: kg} oppure None se i dati sono insufficienti
    """
    benchmarks = {
        level: compute_benchmark(standard_key, body_weight, sex, level, age)
        for level in LEVELS
    }
    if any(value is None for value in benchmarks.values()):
        return None
    return benchmarks


def highest_level_reached(standard_key, body_weight, sex, one_rm, age=None):
    """
    Il livello più alto i cui kg sono stati raggiunti da `one_rm`, oppure None
    se non si arriva nemmeno al primo.

    Le soglie passano da compute_benchmark, quindi hanno lo stesso aggiustamento
    per età del target mostrato: altrimenti un utente di 60 anni vedrebbe un
    target ridotto ma un livello calcolato su soglie piene.
    """
    for level in reversed(LEVELS):
        threshold = compute_benchmark(standard_key, body_weight, sex, level, age)
        if threshold is not None and one_rm >= threshold:
            return level
    return None
