/**
 * GymIt — Video tutorial degli esercizi
 *
 * Caricamento in due tempi, per non contattare Google finché non è l'utente a
 * chiederlo:
 *   1. a pagina chiusa nel DOM non c'è né l'iframe né la copertina, solo gli
 *      indirizzi in attributi `data-` (una stringa non fa richieste);
 *   2. alla prima apertura di "Vedi video" si inserisce la copertina;
 *   3. al clic sulla copertina la si sostituisce con il player.
 *
 * L'indirizzo dell'embed arriva già pronto dal server, costruito dal solo id
 * del video: qui non si compone nulla a partire da input dell'utente.
 */
function initExerciseVideo() {
    var stage = document.querySelector('[data-video-stage]');
    if (!stage) return;

    var details = stage.closest('details');
    var posterLoaded = false;

    function showPlayer() {
        var iframe = document.createElement('iframe');
        iframe.src = stage.dataset.embedUrl;
        iframe.title = stage.dataset.videoTitle;
        iframe.loading = 'lazy';
        iframe.allow = 'accelerometer; encrypted-media; gyroscope; picture-in-picture';
        iframe.allowFullscreen = true;
        iframe.referrerPolicy = 'strict-origin-when-cross-origin';
        iframe.setAttribute('frameborder', '0');
        stage.replaceChildren(iframe);
    }

    function buildPoster() {
        var button = document.createElement('button');
        button.type = 'button';
        button.className = 'exercise-video-poster';
        // textContent implicito: niente HTML costruito a mano attorno al titolo.
        button.setAttribute('aria-label', 'Riproduci ' + stage.dataset.videoTitle);

        var image = document.createElement('img');
        image.src = stage.dataset.thumbUrl;   // prima e unica richiesta a Google
        image.alt = '';
        image.loading = 'lazy';
        image.decoding = 'async';

        var play = document.createElement('span');
        play.className = 'exercise-video-play';
        play.setAttribute('aria-hidden', 'true');
        play.innerHTML = '<i class="bi bi-play-fill"></i>';

        button.appendChild(image);
        button.appendChild(play);
        button.addEventListener('click', showPlayer);
        stage.replaceChildren(button);
    }

    if (details) {
        details.addEventListener('toggle', function () {
            if (details.open && !posterLoaded) {
                posterLoaded = true;
                buildPoster();
            }
        });
    } else {
        buildPoster();
    }
}
