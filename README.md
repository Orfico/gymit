# 🏋️ GymIt

Traccia i tuoi allenamenti, monitora il progresso del massimale teorico nel tempo.

## Stack

- **Django 4.2** — backend e ORM
- **PostgreSQL** (Supabase in produzione) / SQLite in locale
- **Render** — hosting
- **Bootstrap 5** — UI mobile-first
- **Chart.js 4** — grafici di progresso
- **GitHub Actions** — CI/CD

---

## Setup locale

### 1. Clona e crea il virtualenv

```bash
git clone https://github.com/tuoutente/gymit.git
cd gymit
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configura le variabili d'ambiente

```bash
cp .env.example .env
# Modifica .env con il tuo editor
```

### 3. Migra e popola il DB

```bash
python manage.py migrate
python manage.py seed_exercises   # catalogo esercizi predefiniti
python manage.py createsuperuser
```

### 4. Avvia il server

```bash
python manage.py runserver
```

Apri http://localhost:8000

---

## Deploy su Render

1. Crea un nuovo **Web Service** su Render puntando al repository
2. **Build Command**: `pip install -r requirements.txt`
3. **Start Command**: `gunicorn gymit.wsgi`
4. Aggiungi le variabili d'ambiente:
   - `SECRET_KEY` — chiave segreta Django
   - `DEBUG` — `False`
   - `ALLOWED_HOSTS` — il tuo dominio Render
   - `DATABASE_URL` — connection string Supabase PostgreSQL
5. Al primo deploy, nella shell Render esegui `python manage.py seed_exercises`

---

## Struttura del progetto

```
gymit/
├── gymit/           # Configurazione Django
├── gym/             # App principale
│   ├── models.py    # Exercise, WorkoutPlan, PlannedExercise, ExerciseLog
│   ├── views.py     # Tutte le view
│   ├── forms.py     # Form con validazione
│   ├── urls.py      # URL patterns
│   ├── admin.py     # Admin Django
│   ├── templates/   # Template HTML
│   ├── static/      # CSS e JS
│   ├── tests/       # Test suite
│   └── management/  # Comandi custom (seed_exercises)
└── users/           # Autenticazione
```

---

## Formula del massimale teorico (1RM)

L'app usa la **formula di Epley**:

```
1RM = peso × (1 + ripetizioni / 30)
```

Accurata per range 1–15 ripetizioni. Per 1 ripetizione il 1RM coincide con il peso sollevato. Il valore viene calcolato e salvato automaticamente a ogni log, e visualizzato in tempo reale nel form prima del salvataggio.

---

## Test

```bash
python manage.py test gym.tests --verbosity=2
```

---

## Principio chiave — storico immutabile

Ogni sessione di allenamento crea un **nuovo record** `ExerciseLog`. Il carico non viene mai sovrascritto. Il carico "corrente" è l'ultimo log per data. Questo garantisce:

- Storico completo e inviolabile
- Grafici di progresso automatici e affidabili
- Possibilità di calcolare il miglior 1RM di sempre vs. recente
