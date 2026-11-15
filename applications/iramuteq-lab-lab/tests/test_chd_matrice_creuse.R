# Vérifie que l'entrée du moteur CHD reste creuse et que la binarisation
# conserve exactement les valeurs attendues sans changer les options.
if (!requireNamespace("Matrix", quietly = TRUE)) stop("Le package Matrix est requis.")
if (!requireNamespace("quanteda", quietly = TRUE)) stop("Le package quanteda est requis.")

source(file.path("iramuteqlite", "chd_iramuteq.R"))

# Isoler la préparation matricielle du calcul statistique lourd.
.charger_scripts_iramuteq_chd <- function(base_dir = NULL) invisible(NULL)
matrice_observee <- NULL
CHD <- function(data.in, ...) {
  matrice_observee <<- data.in
  stopifnot(inherits(data.in, "dgCMatrix"))
  list(n1 = matrix(1L, nrow = nrow(data.in), ncol = 1L))
}

textes_test <- c(
  "police police violence",
  "violence mairie police",
  "mairie manifestation",
  "manifestation police"
)
dfm_test <- quanteda::dfm(quanteda::tokens(textes_test))
reference <- as.matrix(dfm_test)

resultat_binaire <- calculer_chd_iramuteq(
  dfm_obj = dfm_test,
  k = 3L,
  svd_method = "svdR",
  binariser = TRUE
)
stopifnot(inherits(matrice_observee, "dgCMatrix"))
stopifnot(isTRUE(all.equal(
  unname(as.matrix(matrice_observee)),
  unname(ifelse(reference > 0, 1, 0)),
  check.attributes = FALSE
)))
stopifnot(nrow(resultat_binaire$n1) == nrow(reference))

resultat_comptage <- calculer_chd_iramuteq(
  dfm_obj = dfm_test,
  k = 3L,
  svd_method = "svdR",
  binariser = FALSE
)
stopifnot(inherits(matrice_observee, "dgCMatrix"))
stopifnot(isTRUE(all.equal(
  unname(as.matrix(matrice_observee)),
  unname(reference),
  check.attributes = FALSE
)))
stopifnot(nrow(resultat_comptage$n1) == nrow(reference))

# Vérifier que la boucle CHD ne convertit plus une dgCMatrix en matrice dense.
lignes_moteur <- readLines(file.path("iramuteqlite", "CHD.R"), warn = FALSE)
stopifnot(any(grepl('!inherits(dtable, "Matrix")', lignes_moteur, fixed = TRUE)))

cat("Test de conservation de la matrice creuse CHD : OK\n")
