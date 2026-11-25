# Vérifie le filtrage sur les occurrences totales (et non le nombre de segments).
# La clé historique min_docfreq et les autres options restent compatibles.

if (!requireNamespace("quanteda", quietly = TRUE)) {
  stop("Le package quanteda est requis pour ce test.")
}

source(file.path("backend", "r", "pipeline_pretraitement.R"))

textes_test <- c(
  "violence violence violence violence manifestation",
  "justice justice manifestation",
  "justice manifestation",
  "manifestation rare"
)
matrice <- quanteda::dfm(quanteda::tokens(textes_test, remove_punct = TRUE))

# "violence" apparaît quatre fois dans un seul segment.
# "justice" apparaît trois fois dans deux segments.
# "manifestation" apparaît quatre fois dans quatre segments.
filtre_occurrences <- filtrer_formes_par_occurrences(matrice, 3L)
formes_retenues <- sort(quanteda::featnames(filtre_occurrences))
stopifnot(identical(formes_retenues, sort(c("violence", "justice", "manifestation"))))

# Ancien comportement : les deux premières formes étaient exclues.
filtre_documents <- quanteda::dfm_trim(matrice, min_docfreq = 3L)
stopifnot(!("violence" %in% quanteda::featnames(filtre_documents)))
stopifnot(!("justice" %in% quanteda::featnames(filtre_documents)))

# Un seuil plus élevé doit utiliser les mêmes occurrences totales.
filtre_quatre <- filtrer_formes_par_occurrences(matrice, 4L)
stopifnot(identical(sort(quanteda::featnames(filtre_quatre)),
                    sort(c("violence", "manifestation"))))

# Le nombre de segments et les valeurs des formes retenues ne changent pas.
stopifnot(identical(quanteda::ndoc(filtre_occurrences), quanteda::ndoc(matrice)))
stopifnot(identical(
  as.matrix(filtre_occurrences)[, "violence"],
  as.matrix(matrice)[, "violence"]
))

# La fenêtre CHD doit présenter l'explication au-dessus du champ.
html <- paste(readLines(file.path("frontend", "index.html"), warn = FALSE), collapse = "\n")
position_aide <- regexpr("Nombre minimal d'occurrences d'un terme dans le corpus, et non de segments.", html, fixed = TRUE)[[1]]
position_champ <- regexpr('<input id="minFreq" type="number" min="1" value="3" />', html, fixed = TRUE)[[1]]
stopifnot(position_aide > 0L, position_champ > position_aide)
stopifnot(grepl("Valeurs exprimées en occurrences totales dans le corpus.", html, fixed = TRUE))

cat("Test CHD : filtrage par occurrences totales et aide dans le dialogue OK\n")
