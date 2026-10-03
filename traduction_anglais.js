(function () {
    "use strict";

    const translations = Object.freeze({
        "Serveur VPS": "VPS server",
        "Appli stats Code & Cortex": "Code & Cortex Stats Apps",
        "Applications d’analyse textuelle, statistique hébergées sur le serveur Code & Cortex. Vous pouvez me contacter via la messagerie de mon blog, le serveur n'a pas de mail, ou via le support (Google Group). N'hésitez pas à faire remonter vos problèmes et/ou demandes d'amélioration.": "Textual and statistical analysis applications hosted on the Code & Cortex server. You can contact me through my blog messaging system or the support group (Google Group), as the server has no email service. Please report any problems or requests for improvements.",
        "Langue": "Language",
        "Aide d'utilisation": "User guide",
        "Sessions actives": "Active sessions",
        "File d’attente": "Queue",
        "File d'attente": "Queue",
        "Serveur de calcul": "Computing server",
        "Synchronisation en attente": "Waiting for synchronization",
        "Comprendre la file d'attente et la charge serveur": "Understanding the queue and server load",
        "Pensez à cliquer sur \"Libérer l'accès\" (bouton à gauche) à la fin de l'utilisation de l'application. C'est aussi simple que de penser à fermer sa porte d'entrée quand on quitte son appartement ! Ensuite vous pourrez fermer le navigateur de l'application. Merci !": "Remember to click \"Release access\" (button on the left) when you have finished using an application. It is as simple as closing your front door when leaving home. You can then close the application tab. Thank you!",
        "Extraire": "Extract",
        "Calculer": "Analyse",
        "Multimodale": "Multimodal",
        "Libre": "Available",
        "En construction": "Under construction",
        "Application en préparation": "Application in development",
        "Scraper Reddit": "Reddit scraper",
        "Scraper Wikipedia": "Wikipedia scraper",
        "Extraction Multimédia": "Multimedia extraction",
        "Pour extraire des fichiers images, mp4, mp3 depuis une vidéo YouTube.": "Extract image, MP4 and MP3 files from a YouTube video.",
        "Extraction et génération stopmotion.": "Stop-motion extraction and generation.",
        "Détection IA": "AI detection",
        "Repérer des indices de vidéo générée par IA à partir de mesures temporelles.": "Detect signs of AI-generated video using temporal measurements.",
        "Extraction commentaires YouTube": "YouTube comment extraction",
        "Extraire les commentaires YouTube avec clé API Google obligatoire.": "Extract YouTube comments using a required Google API key.",
        "Scraper les posts Reddit.": "Scrape Reddit posts.",
        "Réseau de vidéo YouTube": "YouTube video network",
        "Scraper les informations d’une chaîne YouTube.": "Scrape information from a YouTube channel.",
        "Conversion de fichier mp3 en texte avec Whisper.": "Convert MP3 files to text with Whisper.",
        "Convertir un ou plusieurs PDF en texte nettoyé compatible avec IRaMuTeQ.": "Convert one or more PDF files into cleaned text compatible with IRaMuTeQ.",
        "Conversion d’exports Europresse vers un corpus compatible avec IRaMuTeQ.": "Convert Europresse exports into an IRaMuTeQ-compatible corpus.",
        "Cooccurrences mot pivot": "Pivot-word co-occurrences",
        "Analyse de cooccurrences centrée sur un mot pivot.": "Co-occurrence analysis centred on a pivot word.",
        "Classification descendante hiérarchique Rainette.": "Rainette descending hierarchical classification.",
        "Comparer deux textes à partir de la divergence de Jensen-Shannon.": "Compare two texts using Jensen-Shannon divergence.",
        "Pour tester les discours algorithmiques des IA génératives.": "Test the algorithmic discourse of generative AI systems.",
        "Petit mais costaud !!! Basé sur le moteur IRAMUTEQ : CHD, AFC, LDA...": "Small but powerful! Based on the IRAMUTEQ engine: CHD, CA, LDA and more.",
        "Version de base d’IRaMuTeQ Lite avec des développements expérimentaux en cours.": "Base IRaMuTeQ Lite version with ongoing experimental developments.",
        "Analyse Discriminante Linéaire (LDA)": "Linear Discriminant Analysis (LDA)",
        "Test de modélisation thématique LDA.": "LDA topic-modelling test.",
        "Vecteur émotionnel": "Emotional vector",
        "Analyse émotionnelle multimodale.": "Multimodal emotion analysis.",
        "Rendre audible l'inaudible": "Making the inaudible audible",
        "Analyse audio, détection d'anomalies d'amplitude et transcription Whisper.": "Audio analysis, amplitude anomaly detection and Whisper transcription.",
        "Analyse du débit de parole": "Speech-rate analysis",
        "Mesure du rythme de parole.": "Speech-rate measurement.",
        "Analyses multimodales": "Multimodal analyses",
        "Analyse multimodale de la temporalité à partir de texte, audio et images.": "Multimodal analysis of temporality using text, audio and images.",
        "Analyse MM": "MM analysis",
        "Préparation vidéo, extraction, transcription, anomalies et analyses multimodales.": "Video preparation, extraction, transcription, anomaly detection and multimodal analysis.",
        "Version 0_3 - modifiée 31-07-2026 - Stéphane Meurisse": "Version 0_3 - updated 31-07-2026 - Stéphane Meurisse",
        "Synchronisation": "Synchronization",
        "Mise à jour": "Updating",
        "Saturé": "At capacity",
        "Occupé": "Busy",
        "En attente": "Queued",
        "Serveur occupé": "Server busy",
        "En cours": "In progress",
        "Ouverture": "Opening",
        "Ouverture en cours...": "Opening...",
        "Synchronisation indisponible": "Synchronization unavailable",
        "Acces libere": "Access released",
        "Accès libéré": "Access released",
        "Disponible": "Available",
        "API dashboard indisponible pour le moment.": "The dashboard API is currently unavailable.",
        "Synchronisation Redis temporairement indisponible : la page conserve le dernier etat connu et met a jour la pastille d'une application que vous venez d'ouvrir.": "Redis synchronization is temporarily unavailable. The page keeps the latest known state and updates the indicator for an application you have just opened.",
        "API dashboard trop lente : verifie Redis et la boucle de synchronisation du dashboard.": "The dashboard API is too slow. Check Redis and the dashboard synchronization loop.",
        "API dashboard indisponible : verifie le service racine du depot, l'endpoint `/api/tickets/dashboard` et la variable REDIS_URL du dashboard.": "The dashboard API is unavailable. Check the repository root service, the `/api/tickets/dashboard` endpoint and the dashboard REDIS_URL variable."
    });

    const ariaTranslations = Object.freeze({
        "État du serveur": "Server status",
        "Informations du tableau de bord": "Dashboard information",
        "Applications disponibles": "Available applications",
        "Applications pour extraire des donnees": "Data extraction applications",
        "Applications pour calculer et comparer": "Analysis and comparison applications",
        "Applications multimodales": "Multimodal applications",
        "Langue de l'interface": "Interface language"
    });

    const staticSelector = [
        ".sur-titre", "h1", ".description", ".lien-aide", ".selecteur-langue > span",
        ".etat-serveur .label", ".etat-serveur .valeur", ".aide-rapide-titre", ".aide-regle", ".famille-titre",
        ".titre-application", ".description-application",
        ".carte-application:not([data-app-id]) .statut",
        ".carte-application:not([data-app-id]) .meta-application", ".version-home"
    ].join(",");

    const originalTexts = new WeakMap();
    const originalAria = new WeakMap();
    let language = "fr";

    function normalize(value) {
        return String(value || "").replace(/\s+/g, " ").trim();
    }

    function translate(value) {
        const source = normalize(value);
        if (language !== "en" || !source) return source;
        if (translations[source]) return translations[source];
        const quota = source.match(/^(\d+)\s*\/\s*(\d+)\s+actif\s*·\s*(\d+)\s+attente$/i);
        if (quota) return `${quota[1]} / ${quota[2]} active · ${quota[3]} queued`;
        const activity = source.match(/^(\d+)\s+actif\s*·\s*(\d+)\s+attente$/i);
        if (activity) return `${activity[1]} active · ${activity[2]} queued`;
        return source;
    }

    function applyStaticTranslations() {
        document.querySelectorAll(staticSelector).forEach((element) => {
            if (!originalTexts.has(element)) originalTexts.set(element, normalize(element.textContent));
            const source = originalTexts.get(element);
            element.textContent = language === "en" ? (translations[source] || source) : source;
        });
        document.querySelectorAll("[aria-label]").forEach((element) => {
            if (!originalAria.has(element)) originalAria.set(element, element.getAttribute("aria-label") || "");
            const source = originalAria.get(element);
            element.setAttribute("aria-label", language === "en" ? (ariaTranslations[source] || source) : source);
        });
        const title = language === "en" ? "Code & Cortex Stats Apps" : "Appli stats Code & Cortex";
        document.title = title;
        document.querySelector('meta[property="og:title"]')?.setAttribute("content", title);
        document.querySelector('meta[name="twitter:title"]')?.setAttribute("content", title);
    }

    function setLanguage(nextLanguage) {
        language = nextLanguage === "en" ? "en" : "fr";
        document.documentElement.lang = language;
        const selector = document.getElementById("home-language");
        if (selector) selector.value = language;
        applyStaticTranslations();
        window.dispatchEvent(new CustomEvent("home-language-change", { detail: { language } }));
    }

    window.homeI18n = Object.freeze({
        getLanguage: () => language,
        setLanguage,
        translate
    });

    const selector = document.getElementById("home-language");
    selector?.addEventListener("change", () => setLanguage(selector.value));
    setLanguage("fr");
})();
