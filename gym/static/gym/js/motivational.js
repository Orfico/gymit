/**
 * GymIt — Frase motivazionale del giorno (dashboard)
 *
 * Selezione deterministica in base alla data locale: resta identica per
 * tutta la giornata e cambia a mezzanotte, senza bisogno di stato salvato.
 * Lingua scelta da navigator.language/navigator.languages tra quelle
 * disponibili, inglese come fallback.
 */
(function () {
    var PHRASES = {
        it: [
            'Suda oggi. Brilla domani.',
            'Nessuna scusa. Solo ripetizioni.',
            "Il limite è solo un'opinione.",
            'Suda ora, sorridi dopo.',
            'Ogni serie ti rende più forte.',
            "Il dolore è temporaneo. L'orgoglio resta.",
            'Alza il peso, non le scuse.',
            'La vera sfida sei tu contro ieri.',
            'Suda, respira, ripeti.',
            'Costruisci il corpo che ti porti addosso ogni giorno.',
            'Oggi alleni il corpo, domani ringrazia la mente.',
            'Spingi oltre il limite.',
            'La costanza batte il talento.',
            'Fai contare ogni ripetizione.',
            'Suda in palestra, brilla nella vita.',
            'Il comodo non allena nessuno.',
            'Ogni allenamento è un passo avanti.',
            'Il corpo diventa ciò in cui la mente crede.',
            'Fatti valere, un carico alla volta.',
            'Gli obiettivi importanti non aspettano.',
            'La disciplina batte la motivazione.',
            'Allenati per chi diventerai, non per chi eri.',
            'Piccoli progressi, grandi trasformazioni.',
            'Oggi è il giorno per superarsi.',
            'Trasforma la fatica in forza.',
            'Chi si ferma resta indietro, chi spinge cresce.',
            "Il sudore è la firma dell'impegno.",
            'Costruisci muscoli, costruisci carattere.',
            'Non aspettare la motivazione: crea la disciplina.',
            'Ogni serie ti avvicina alla tua versione migliore.',
            'Suda per il traguardo, non per il minuto.',
            'Il ferro non mente mai.',
            'Vinci la giornata, una serie alla volta.',
            'La forza si allena, non si eredita.',
            'Ogni goccia di sudore racconta impegno.',
            'Rialzati più forte di prima.',
            'Nessun traguardo senza sudore.',
            'Fai oggi ciò che domani ringrazierai.',
            'Il progresso non chiede il permesso.',
            "Spingi finché non diventa facile, poi spingi ancora.",
        ],
        en: [
            'Sweat today. Shine tomorrow.',
            'No excuses. Just reps.',
            'The limit is just an opinion.',
            'Sweat now, smile later.',
            'Every set makes you stronger.',
            'Pain is temporary. Pride is forever.',
            'Lift the weight, not the excuses.',
            'The real fight is you versus yesterday.',
            'Sweat. Breathe. Repeat.',
            'Build the body you carry every day.',
            'Train the body, thank the mind tomorrow.',
            'Push past the limit.',
            'Consistency beats talent.',
            'Make every rep count.',
            'Sweat in the gym, shine in life.',
            'Comfort never built strength.',
            'Every workout is a step forward.',
            'The body becomes what the mind believes.',
            'Earn it, one rep at a time.',
            "Big goals don't wait.",
            'Discipline beats motivation.',
            "Train for who you're becoming, not who you were.",
            'Small progress, big transformation.',
            'Today is the day you level up.',
            'Turn fatigue into strength.',
            'Those who stop fall behind, those who push grow.',
            'Sweat is the signature of effort.',
            'Build muscle, build character.',
            "Don't wait for motivation: build discipline.",
            'Every set gets you closer to your best self.',
            'Sweat for the finish line, not the clock.',
            'Iron never lies.',
            'Win the day, one set at a time.',
            'Strength is trained, not inherited.',
            'Every drop of sweat tells a story.',
            'Rise stronger than before.',
            'No finish line without sweat.',
            'Do today what tomorrow will thank you for.',
            "Progress doesn't ask permission.",
            "Push until it's easy, then push again.",
        ],
    };

    function pickLanguage() {
        var langs = (navigator.languages && navigator.languages.length)
            ? navigator.languages
            : [navigator.language || 'en'];
        for (var i = 0; i < langs.length; i++) {
            if (String(langs[i]).toLowerCase().indexOf('it') === 0) return 'it';
        }
        return 'en';
    }

    function localDayNumber() {
        var d = new Date();
        return d.getFullYear() * 372 + (d.getMonth() + 1) * 31 + d.getDate();
    }

    function init() {
        var el = document.getElementById('motivationalQuoteText');
        if (!el) return;
        var list = PHRASES[pickLanguage()] || PHRASES.en;
        el.textContent = list[localDayNumber() % list.length];
    }

    document.addEventListener('DOMContentLoaded', init);
})();
