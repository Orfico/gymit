"""
Strength standards: multipli del peso corporeo (1RM / BW) per esercizio,
sesso e livello di allenamento.

Fonte: Strength Level (strengthlevel.com), percentili community.
Beginner=5°, Novice=20°, Intermediate=50°, Advanced=80°, Elite=95°.
"""

# Dal più basso al più alto: l'ordine serve a stabilire il livello raggiunto.
LEVELS = ('beginner', 'novice', 'intermediate', 'advanced', 'elite')

# Chiave → {sesso → {livello → multiplo BW}}
STANDARDS = {
    'bench_press': {
        'M': {'beginner': 0.50, 'novice': 0.75, 'intermediate': 1.25, 'advanced': 1.75, 'elite': 2.00},
        'F': {'beginner': 0.25, 'novice': 0.40, 'intermediate': 0.65, 'advanced': 1.00, 'elite': 1.35},
    },
    'squat': {
        'M': {'beginner': 0.75, 'novice': 1.00, 'intermediate': 1.75, 'advanced': 2.25, 'elite': 2.75},
        'F': {'beginner': 0.50, 'novice': 0.65, 'intermediate': 1.00, 'advanced': 1.50, 'elite': 1.90},
    },
    'deadlift': {
        'M': {'beginner': 1.00, 'novice': 1.25, 'intermediate': 2.00, 'advanced': 2.50, 'elite': 3.00},
        'F': {'beginner': 0.50, 'novice': 0.75, 'intermediate': 1.25, 'advanced': 1.75, 'elite': 2.25},
    },
    'overhead_press': {
        'M': {'beginner': 0.35, 'novice': 0.55, 'intermediate': 0.80, 'advanced': 1.10, 'elite': 1.40},
        'F': {'beginner': 0.20, 'novice': 0.30, 'intermediate': 0.50, 'advanced': 0.75, 'elite': 1.00},
    },
    'barbell_row': {
        'M': {'beginner': 0.40, 'novice': 0.55, 'intermediate': 1.00, 'advanced': 1.35, 'elite': 1.65},
        'F': {'beginner': 0.25, 'novice': 0.35, 'intermediate': 0.60, 'advanced': 0.85, 'elite': 1.10},
    },
}

# Coefficiente di riduzione per età (applicato dopo i 40 anni)
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

    exercise_standards = STANDARDS.get(standard_key)
    if not exercise_standards:
        return None

    sex_standards = exercise_standards.get(sex)
    if not sex_standards:
        return None

    multiplier = sex_standards.get(training_level)
    if multiplier is None:
        return None

    expected = float(body_weight) * multiplier * get_age_factor(age)
    return round(expected, 1)


def get_all_benchmarks_for_level(standard_key, sex):
    """
    Restituisce tutti i benchmark (multipli BW) per un esercizio e sesso.
    Utile per mostrare all'utente dove si colloca rispetto a tutti i livelli.

    Returns:
        dict {livello: multiplo} oppure None
    """
    exercise_standards = STANDARDS.get(standard_key)
    if not exercise_standards:
        return None
    return exercise_standards.get(sex)


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
