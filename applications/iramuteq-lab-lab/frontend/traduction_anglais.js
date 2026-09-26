const STORAGE_KEY = "iramuteq_lab_interface_language";

const ENGLISH_TRANSLATIONS = Object.freeze({
  "Navigation principale": "Main navigation",
  "Tentative de reproduction de la CHD du (vrai !)": "Attempt to reproduce the CHD of the original",
  "logiciel IRaMuTeQ (IRaMuTeQ - Pierre Ratinaud - LERASS)": "IRaMuTeQ software (IRaMuTeQ - Pierre Ratinaud - LERASS)",
  "Pour d'autres scripts/appli, vous pouvez consulter mon site :": "For other scripts and applications, visit my website:",
  "Version 0_5beta - modifiée 26-09-2026 - (ajout des dictionnaires)": "Version 0_5beta - modified 26-09-2026 - (dictionaries added)",
  "Langue de l'interface": "Interface language",
  "Analyse": "Analysis",
  "Similitudes": "Similarity",
  "Aide": "Help",
  "Importer un fichier texte": "Import a text file",
  "Le corpus doit être au format IRaMuTeQ, avec une première ligne commençant par": "The corpus must use the IRaMuTeQ format, with a first line beginning with",
  "Aucun fichier sélectionné.": "No file selected.",
  "Le téléchargement se fait depuis chaque analyse lancée.": "Downloads are available from each completed analysis.",
  "Mes analyses": "My analyses",
  "Purger mon historique": "Clear my history",
  "Vos analyses apparaîtront ici et resteront disponibles après reconnexion.": "Your analyses will appear here and remain available after you reconnect.",
  "Vos analyses apparaîtront ici et resteront disponibles après reconnexion pendant 30 jours.": "Your analyses will appear here and remain available for 30 days after you reconnect.",
  "Libérer l'accès": "Release access",
  "Analyse du corpus": "Corpus analysis",
  "Synthèse du corpus": "Corpus summary",
  "La synthèse du corpus apparaîtra après l'analyse.": "The corpus summary will appear after the analysis.",
  "Loi de Zipf": "Zipf's law",
  "Étapes de l'analyse": "Analysis steps",
  "Les étapes s'afficheront après le lancement d'une analyse.": "The steps will appear after an analysis is started.",
  "Journal debug": "Debug log",
  "Corpus importé": "Imported corpus",
  "Prévisualisation": "Preview",
  "Importez un fichier texte pour afficher un extrait ici.": "Import a text file to display an excerpt here.",
  "Annotation du corpus": "Corpus annotation",
  "Import de": "Import of",
  ", prévisualisation annotée et gestion du dictionnaire d'expressions de session.": ", annotated preview and session expression-dictionary management.",
  "Aide : le plus simple est de surligner, copier puis coller les expressions à transformer dans le dictionnaire. Par exemple,": "Help: the easiest method is to highlight, copy and paste the expressions to transform into the dictionary. For example,",
  "deviendra": "will become",
  "Vous pouvez enregistrer votre dictionnaire d'expressions, mais vous pouvez également ajuster (supprimer) et enrichir (ajouter) un dictionnaire déjà annoté.": "You can save your expression dictionary, and you can also adjust (delete) and enrich (add to) an existing annotated dictionary.",
  "Vous pouvez réimporter un fichier d'expressions déjà annoté ; il doit impérativement être nommé add_expression_fr.csv.": "You can re-import an existing annotated expression file; it must be named add_expression_fr.csv.",
  "Charger un dictionnaire d'expression": "Load an expression dictionary",
  "Texte à annoter": "Text to annotate",
  "Texte sélectionné (dic_mot)": "Selected text (dic_mot)",
  "Expression source": "Source expression",
  "Normalisation (dic_norm)": "Normalization (dic_norm)",
  "Expression normalisée": "Normalized expression",
  "Type morpho (dic_morpho)": "Morphological type (dic_morpho)",
  "Choisir une catégorie (optionnel)": "Choose a category (optional)",
  "Si vous n'ajoutez pas de catégorie morphosyntaxique, le champ restera vide et l'expression sera interprétée comme « autre forme ».": "If you do not add a morphosyntactic category, the field remains empty and the expression is interpreted as ‘other form’.",
  "Ajouter / mettre à jour": "Add / update",
  "Supprimer une entrée (dic_mot)": "Delete an entry (dic_mot)",
  "Expression à supprimer": "Expression to delete",
  "Supprimer": "Delete",
  "Enregistrer add_expression_fr.csv": "Save add_expression_fr.csv",
  "Résultats CHD": "CHD results",
  "Dendrogramme": "Dendrogram",
  "CHD distance optimisée": "Optimized-distance CHD",
  "Stats CHD": "CHD statistics",
  "Concordancier": "Concordance",
  "Nuage de mots": "Word cloud",
  "Nuages de mots CHD": "CHD word clouds",
  "Paramétrage": "Settings",
  "Paramètres de l'analyse CHD": "CHD analysis settings",
  "Dendrogramme CHD": "CHD dendrogram",
  "Dendrogramme IRaMuTeQ": "IRaMuTeQ dendrogram",
  "Dendrogramme factoextra": "factoextra dendrogram",
  "Chargez un dossier d'exports pour afficher les dendrogrammes CHD.": "Load an export folder to display the CHD dendrograms.",
  "Résultat": "Result",
  "Type de dendrogramme": "Dendrogram type",
  "Selection": "Selection",
  "Meilleur compromis retenu": "Best selected compromise",
  "Croisement des paramètres testés": "Combination of tested parameters",
  "Tableaux statistiques CHD par classe": "CHD statistical tables by class",
  "Analyse factorielle des correspondances": "Correspondence analysis",
  "AFC des classes": "Class AFC",
  "AFC des termes": "Term AFC",
  "Réinitialiser": "Reset",
  "Réinitialiser le zoom": "Reset zoom",
  "Explorer l'AFC": "Explore the AFC",
  "Graphique AFC interactif": "Interactive AFC plot",
  "AFC : termes significatifs les plus extrêmes": "AFC: most extreme significant terms",
  "Mots repères pour nommer les axes AFC": "Reference words for naming AFC axes",
  "Variables étoilées": "Starred variables",
  "Table des mots projetés et coordonnées AFC": "Projected-word table and AFC coordinates",
  "Analyse de similitudes": "Similarity analysis",
  "Paramétrer l'analyse de similitudes": "Configure similarity analysis",
  "Documentation": "Documentation",
  "Aide morpho": "Morphology help",
  "Paramètres CHD": "CHD settings",
  "Paramètres CHD (IRaMuTeQ-lite)": "CHD settings (IRaMuTeQ-lite)",
  "Méthode Iramuteq-lite": "IRaMuTeQ-lite method",
  "Tenir compte de la ponctuation forte (. ! ?) dans le découpage": "Use strong punctuation (. ! ?) for segmentation",
  "Si activé, le découpage recherche la meilleure frontière autour de segment_size avec priorité . ! ?, puis ; :, puis , puis espace ; un retour à la ligne clôture aussi le segment.": "When enabled, segmentation finds the best boundary around segment_size, prioritizing . ! ?, then ; :, then commas and spaces; a line break also ends the segment.",
  "Fréquence minimale des termes (min_docfreq)": "Minimum term frequency (min_docfreq)",
  "Filtrer l'affichage des résultats par p-value (p ≤ max_p)": "Filter displayed results by p-value (p ≤ max_p)",
  "Le graphique AFC des termes affiche toujours uniquement les formes significatives à `p ≤ 0.05`. Ce filtre complémentaire agit sur l'AFC des variables étoilées, le concordancier et les nuages de mots ; dans les stats, les formes significatives apparaissent en vert et les formes au-delà du seuil d'affichage restent affichées en rouge.": "The term AFC plot always displays significant forms only (`p ≤ 0.05`). This additional filter applies to the starred-variable AFC, concordance and word clouds; in the statistics, significant forms appear in green and forms above the display threshold remain visible in red.",
  "Choisir le mode": "Choose mode",
  "Normal": "Standard",
  "En mode Normal, vous choisissez les paramètres de la CHD avant le lancement.": "In Standard mode, you choose the CHD settings before running the analysis.",
  "En mode Normal, vous choisissez tous les paramètres de la CHD avant le lancement.": "In Standard mode, you choose all CHD settings before running the analysis.",
  "Nombre de classes terminales de la phase 1": "Number of terminal classes in phase 1",
  "Ce paramètre correspond à k dans la phase 1 de la CHD, comme dans IRaMuTeQ Lite.": "This setting corresponds to k in phase 1 of the CHD, as in IRaMuTeQ Lite.",
  "Critère de sélection automatique": "Automatic selection criterion",
  "Distance directe des classes AFC": "Direct AFC class distance",
  "Distance directe des classes AFC (ca$row$coord, recommandée)": "Direct AFC class distance (ca$row$coord, recommended)",
  "Critère recommandé : il compare directement les positions réelles de Classe 1, Classe 2, etc. sur les axes 1 et 2 de l'AFC (ca$row$coord), sans moyenne ni médiane de mots.": "Recommended criterion: it directly compares the actual positions of Class 1, Class 2, etc. on AFC axes 1 and 2 (ca$row$coord), without calculating a mean or median of words.",
  "Score S lexical": "Lexical S score",
  "Score S lexical (centres et dispersions des mots significatifs)": "Lexical S score (centres and dispersions of significant words)",
  "Option complémentaire : le score S compare les centres lexicaux construits à partir des mots significatifs et leur dispersion.": "Additional option: the S score compares lexical centres built from significant words and their dispersion.",
  "Paramètres à croiser": "Parameters to combine",
  "Cochez uniquement les paramètres à faire varier. Les paramètres non cochés restent fixes pendant toutes les simulations.": "Select only the parameters to vary. Unselected parameters remain fixed throughout all simulations.",
  "Croiser mincl (manuel)": "Vary mincl (manual)",
  "Croiser la fréquence minimale des termes (min_docfreq)": "Vary minimum term frequency (min_docfreq)",
  "Croiser le nombre de classes terminales de la phase 1": "Vary the number of terminal classes in phase 1",
  "De": "From",
  "à": "to",
  "Lorsque cette option est cochée, les simulations utilisent mincl en mode manuel.": "When selected, simulations use mincl in manual mode.",
  "Ce réglage utilise le même paramètre que « Nombre de classes terminales de la phase 1 » en mode Normal. Il ne fixe pas le nombre final de classes.": "This uses the same setting as ‘Number of terminal classes in phase 1’ in Standard mode. It does not set the final number of classes.",
  "Nombre maximum de formes analysées": "Maximum number of analysed forms",
  "Nombre minimum d'UCE par classe terminale (mincl)": "Minimum number of text segments per terminal class (mincl)",
  "Automatique": "Automatic",
  "Manuel": "Manual",
  "Ce paramètre définit le seuil minimal d'UCE pour conserver une classe terminale.": "This setting defines the minimum number of text segments required to keep a terminal class.",
  "mincl (manuel)": "mincl (manual)",
  "mincl n'est pas le nombre de classes.": "mincl is not the number of classes.",
  "Il fixe le nombre minimal de segments de texte (UCE) qu'une classe terminale doit contenir pour être conservée. Avec": "It sets the minimum number of text segments (UCE) a terminal class must contain to be kept. With",
  "une classe de moins de 5 UCE n'est pas retenue comme classe terminale. Une valeur plus haute réduit les petites classes ; une valeur plus basse les autorise.": "a class containing fewer than 5 UCE is not retained as a terminal class. A higher value reduces small classes; a lower value allows them.",
  ", une classe de moins de 5 UCE n'est pas retenue comme classe terminale. Une valeur plus haute réduit les petites classes ; une valeur plus basse les autorise.": ", a class containing fewer than 5 UCE is not retained as a terminal class. A higher value reduces small classes; a lower value allows them.",
  "Type de classification terminale": "Terminal classification type",
  "Simple": "Single",
  "Double": "Double",
  "Taille de rst1": "rst1 size",
  "Taille de rst2": "rst2 size",
  "Méthode SVD": "SVD method",
  "Calcul des statistiques CHD": "CHD statistics calculation",
  "Mode optimisé (vectorisé, recommandé)": "Optimized mode (vectorized, recommended)",
  "Mode classique (chisq.test par terme)": "Classic mode (chisq.test for each term)",
  "Lexique": "Lexicon",
  "Dictionnaire": "Dictionary",
  "Langue et dictionnaire": "Language and dictionary",
  "Dictionnaires IRaMuTeQ": "IRaMuTeQ dictionaries",
  "Français - dico IRaMuTeQ": "French - IRaMuTeQ dictionary",
  "Anglais - dico IRaMuTeQ": "English - IRaMuTeQ dictionary",
  "Espagnol - dico IRaMuTeQ": "Spanish - IRaMuTeQ dictionary",
  "Italien - dico IRaMuTeQ": "Italian - IRaMuTeQ dictionary",
  "Mode multilingue": "Multilingual mode",
  "Votre langue n’est pas proposée ? - spaCy": "Is your language unavailable? - spaCy",
  "Le choix détermine le lexique, la lemmatisation, les catégories morphosyntaxiques et la langue des stopwords.": "This choice determines the lexicon, lemmatization, morphosyntactic categories and stopword language.",
  "Modèle linguistique spaCy": "spaCy language model",
  "Exemple : en_core_web_sm": "Example: en_core_web_sm",
  "Anglais (installé par défaut)": "English (installed by default)",
  "Allemand": "German",
  "Néerlandais": "Dutch",
  "Portugais": "Portuguese",
  "Catalan": "Catalan",
  "Grec": "Greek",
  "Le modèle anglais": "The English model",
  "est installé par défaut. Les autres modèles doivent être ajoutés au build du serveur. Les modèles multilingues": "is installed by default. Other models must be added to the server build. spaCy multilingual",
  "de spaCy ne fournissent pas le POS et les lemmes nécessaires à la CHD.": "models do not provide the POS tags and lemmas required for CHD.",
  "Lemmatisation via le dictionnaire sélectionné (forme vers lemme)": "Lemmatization using the selected dictionary (form to lemma)",
  "Utiliser le dictionnaire d'expressions (expression vers forme normalisée)": "Use the expression dictionary (expression to normalized form)",
  "Un dictionnaire d'expressions de base est fourni en français et en anglais.": "A basic expression dictionary is provided in French and English.",
  "Ajouter le dictionnaire utilisateur add_expression_fr.csv": "Add the user dictionary add_expression_fr.csv",
  "Fusionne les entrées de l'onglet Annotation avec le dictionnaire d'expressions UNIQUEMENT FRANCAIS.": "Merges entries from the Annotation tab with the expression dictionary for FRENCH ONLY.",
  "Nettoyage": "Preprocessing",
  "Nettoyage caractères (regex)": "Character cleaning (regex)",
  "Les caractères présents dans la liste entre crochets sont conservés (dont _ pour les expressions normalisées) ; tous les autres sont remplacés par des espaces.": "Characters listed inside the brackets are retained (including _ for normalized expressions); all others are replaced with spaces.",
  "Supprimer la ponctuation": "Remove punctuation",
  "Supprime la ponctuation à la tokenisation quanteda (remove_punct), par ex. . , ; : ! ? ' ’ \" - ( ) [ ] …": "Removes punctuation during quanteda tokenization (remove_punct), for example . , ; : ! ? ' ’ \" - ( ) [ ] …",
  "Supprimer les chiffres (0-9)": "Remove digits (0-9)",
  "Traiter les élisions FR (c'est vers est, m'écrire vers écrire)": "Process French elisions (c'est to est, m'écrire to écrire)",
  "Remplacer les tirets (-) par des espaces": "Replace hyphens (-) with spaces",
  "Retirer les stopwords (liste française quanteda)": "Remove stopwords (French quanteda list)",
  "Filtrage morphosyntaxique": "Morphosyntactic filtering",
  "Catégories c_morpho à conserver": "c_morpho categories to keep",
  "Choisir une catégorie": "Choose a category",
  "Choisir une variable": "Choose a variable",
  "Ajouter": "Add",
  "Aucune variable étoilée détectée dans le corpus.": "No starred variable detected in the corpus.",
  "Utilisé si le filtrage morphosyntaxique est actif.": "Used when morphosyntactic filtering is enabled.",
  "Filtrer le terme « être » dans la catégorie VERB": "Filter the term ‘être’ from the VERB category",
  "Conserver les formes non reconnues par le lexique (AUTRE_FORME)": "Keep forms not recognized by the lexicon (AUTRE_FORME)",
  "Paramètres AFC complémentaires": "Additional AFC settings",
  "Réduire les chevauchements des mots (AFC)": "Reduce word overlap (AFC)",
  "Fréquence": "Frequency",
  "Taille des mots (AFC termes)": "Word size (term AFC)",
  "Top N mots par classe (nuages)": "Top N words per class (clouds)",
  "Variables étoilées à projeter (AFC variables)": "Starred variables to project (variable AFC)",
  "Réseau": "Network",
  "Paramètres": "Settings",
  "Méthode de calcul": "Calculation method",
  "Seuil minimal des arêtes": "Minimum edge threshold",
  "Le seuil supprime les arêtes trop faibles.": "The threshold removes edges that are too weak.",
  "Nombre de termes à conserver (plus fréquents)": "Number of terms to keep (most frequent)",
  "Mots les plus fréquents retenus pour l'analyse": "Most frequent words retained for analysis",
  "On conserve les N mots les plus fréquents, puis on calcule les liens selon l'indice choisi.": "The N most frequent words are retained, then links are calculated using the selected index.",
  "La liste est peuplée par fréquence. Cliquez sur la croix d'un mot pour l'exclure de l'analyse.": "The list is populated by frequency. Click a word's cross to exclude it from the analysis.",
  "Limiter au graphe couvrant maximal (arbre de poids max)": "Limit to the maximum spanning tree",
  "Type de layout": "Layout type",
  "Espacement des bulles": "Bubble spacing",
  "Augmente la surface du graphe et l'écartement visuel des nœuds sans modifier les calculs.": "Increases the plot area and visual spacing between nodes without changing the calculations.",
  "Afficher le score de l'indice (arêtes / info-bulles)": "Display index scores (edges/tooltips)",
  "Largeur des arêtes proportionnelle à l'indice": "Edge width proportional to the index",
  "Taille du texte des sommets proportionnelle aux fréquences": "Vertex label size proportional to frequency",
  "Communautés": "Communities",
  "Méthode de communautés": "Community method",
  "Afficher les halos de communautés": "Display community halos",
  "Paramètres de l'analyse de similitudes": "Similarity analysis settings",
  "Fermer": "Close",
  "Lancer la CHD": "Run CHD",
  "Lancer l'analyse": "Run analysis",
  "Traitement": "Processing",
  "Analyse en cours": "Analysis in progress",
  "Initialisation...": "Initializing...",
  "Stopper l'analyse": "Stop analysis",
  "Vérification de l'environnement": "Checking environment",
  "Préparation des dépendances...": "Preparing dependencies...",
  "Démarrage de l'application": "Starting application",
  "Segments de texte dans la classe": "Text segments in the class",
  "Segments de texte dans les classes": "Text segments in the classes",
  "Image précédente": "Previous image",
  "Image suivante": "Next image",
  "Rechercher un terme": "Search for a term",
  "Afficher les classes": "Show classes",
  "Réinitialiser la vue": "Reset view",
  "Segments trouvés": "Segments found",
  "Occurrences d'une forme": "Occurrences of a form",
  "Enregistrer en PNG": "Save as PNG",
  "Construire un sous-corpus": "Build a subcorpus",
  "Sous-navigation CHD": "CHD sub-navigation",
  "Sous-onglets Aide": "Help subtabs",
  "Survolez un terme pour afficher ses informations. Faites glisser le graphique pour le déplacer et utilisez la molette pour zoomer.": "Hover over a term to display its information. Drag the plot to pan and use the mouse wheel to zoom.",
  "Zoomez et déplacez le plan x/y de l’AFC. Les termes s’écartent visuellement avec le zoom. Survolez un terme pour afficher ses coordonnées, son χ² et sa p.value.": "Zoom and pan the AFC x/y plane. Terms spread visually as you zoom. Hover over a term to display its coordinates, χ² and p.value."
});

const FRENCH_BY_ENGLISH = new Map();
Object.entries(ENGLISH_TRANSLATIONS).forEach(([french, english]) => {
  if (!FRENCH_BY_ENGLISH.has(english)) FRENCH_BY_ENGLISH.set(english, french);
});

const DYNAMIC_TRANSLATIONS = [
  ["En mode CHD distance optimisée, l'application simule les combinaisons que vous avez choisies, puis retient celle dont le critère « ", "In Optimized-distance CHD mode, the application simulates the combinations you selected, then retains the one with the highest ‘"],
  [" » est le plus élevé.", "’ criterion."],
  ["Grille prévue : ", "Planned grid: "],
  ["Critère : ", "Criterion: "],
  ["Distance directe des classes AFC", "Direct AFC class distance"],
  ["Score S lexical", "Lexical S score"],
  [" configurations CHD seront comparées.", " CHD configurations will be compared."],
  [" configuration CHD sera comparée.", " CHD configuration will be compared."],
  ["classes terminales phase 1", "phase-1 terminal classes"],
  ["mincl manuel", "manual mincl"],
  [" à ", " to "],
  [" fixe", " fixed"],
  [" CHD sont demandées : le calcul peut être long, surtout pour un corpus volumineux.", " CHD runs are requested: computation may take a long time, especially for a large corpus."],
  ["Retirer ", "Remove "]
];

const originalText = new WeakMap();
const originalAttributes = new WeakMap();
const TRANSLATED_ATTRIBUTES = ["aria-label", "placeholder", "title", "label"];
let currentLanguage = "fr";
let observer = null;

function translateValue(value) {
  const raw = String(value ?? "");
  const trimmed = raw.trim();
  const normalized = trimmed.replace(/\s+/g, " ");
  const translated = ENGLISH_TRANSLATIONS[normalized];
  if (translated) {
    return `${raw.match(/^\s*/)?.[0] || ""}${translated}${raw.match(/\s*$/)?.[0] || ""}`;
  }
  return DYNAMIC_TRANSLATIONS.reduce(
    (result, [french, english]) => result.replaceAll(french, english),
    raw
  );
}

function inferFrenchValue(value) {
  const raw = String(value ?? "");
  const trimmed = raw.trim();
  const french = FRENCH_BY_ENGLISH.get(trimmed);
  if (!french) return raw;
  return `${raw.match(/^\s*/)?.[0] || ""}${french}${raw.match(/\s*$/)?.[0] || ""}`;
}

function shouldIgnoreTextNode(node) {
  return Boolean(node.parentElement?.closest("script, style, code, pre, textarea"));
}

function translateTextNode(node) {
  if (shouldIgnoreTextNode(node)) return;
  if (!originalText.has(node)) {
    const value = node.nodeValue || "";
    originalText.set(node, currentLanguage === "en" ? inferFrenchValue(value) : value);
  }
  const french = originalText.get(node) || "";
  node.nodeValue = currentLanguage === "en" ? translateValue(french) : french;
}

function translateElementAttributes(element) {
  if (!(element instanceof Element)) return;
  let stored = originalAttributes.get(element);
  if (!stored) {
    stored = new Map();
    originalAttributes.set(element, stored);
  }
  TRANSLATED_ATTRIBUTES.forEach((attribute) => {
    if (!element.hasAttribute(attribute)) return;
    if (!stored.has(attribute)) {
      const value = element.getAttribute(attribute) || "";
      stored.set(attribute, currentLanguage === "en" ? inferFrenchValue(value) : value);
    }
    const french = stored.get(attribute) || "";
    element.setAttribute(attribute, currentLanguage === "en" ? translateValue(french) : french);
  });
}

function translateTree(root = document.body) {
  if (!root) return;
  if (root.nodeType === Node.TEXT_NODE) {
    translateTextNode(root);
    return;
  }
  if (root instanceof Element) translateElementAttributes(root);
  const textWalker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let textNode = textWalker.nextNode();
  while (textNode) {
    translateTextNode(textNode);
    textNode = textWalker.nextNode();
  }
  if (root.querySelectorAll) {
    root.querySelectorAll("*").forEach(translateElementAttributes);
  }
}

function observeInterface() {
  if (!observer || !document.body) return;
  observer.observe(document.body, { childList: true, characterData: true, subtree: true });
}

function applyLanguage(language) {
  currentLanguage = language === "en" ? "en" : "fr";
  observer?.disconnect();
  document.documentElement.lang = currentLanguage;
  translateTree(document.body);
  const selector = document.getElementById("interfaceLanguage");
  if (selector instanceof HTMLSelectElement) selector.value = currentLanguage;
  try {
    localStorage.setItem(STORAGE_KEY, currentLanguage);
  } catch {
    // The interface remains usable when browser storage is unavailable.
  }
  observeInterface();
  document.dispatchEvent(new CustomEvent("iramuteq:languagechange", { detail: { language: currentLanguage } }));
}

export function initializeEnglishTranslation({ selectorId = "interfaceLanguage" } = {}) {
  const selector = document.getElementById(selectorId);
  if (!(selector instanceof HTMLSelectElement)) return;

  observer = new MutationObserver((mutations) => {
    observer.disconnect();
    mutations.forEach((mutation) => {
      if (mutation.type === "characterData") {
        originalText.set(mutation.target, mutation.target.nodeValue || "");
      }
      mutation.addedNodes.forEach((node) => translateTree(node));
    });
    if (currentLanguage === "en") translateTree(document.body);
    observeInterface();
  });

  selector.addEventListener("change", () => applyLanguage(selector.value));
  let savedLanguage = "fr";
  try {
    savedLanguage = localStorage.getItem(STORAGE_KEY) === "en" ? "en" : "fr";
  } catch {
    savedLanguage = "fr";
  }
  applyLanguage(savedLanguage);
}
