# Test de régression : lecture RDS d'une dgCMatrix dans un processus R distinct.
# Le calcul historique par terme n'est pas modifié par ce test.

arguments <- commandArgs(trailingOnly = FALSE)
chemin_script <- sub("^--file=", "", grep("^--file=", arguments, value = TRUE)[[1L]])
racine <- normalizePath(file.path(dirname(chemin_script), ".."), mustWork = TRUE)
lanceur <- file.path(racine, "backend", "r", "run_specificites_variables.R")

if (!requireNamespace("Matrix", quietly = TRUE)) stop("Le package Matrix est nécessaire.")
if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Le package jsonlite est nécessaire.")

repertoire <- tempfile("test-s4-specificites-")
dir.create(repertoire, recursive = TRUE)
chemin_source <- file.path(repertoire, "source_specificites.rds")
matrice <- Matrix::Matrix(
  c(8, 1, 0,
    5, 2, 0,
    0, 2, 7,
    0, 1, 9),
  nrow = 4L, byrow = TRUE, sparse = TRUE,
  dimnames = list(paste0("segment_", 1:4), c("violence", "manifestation", "tension"))
)
source_test <- list(
  dfm = methods::as(matrice, "dgCMatrix"),
  classes = c(1L, 1L, 2L, 2L),
  docvars = data.frame(
    `*source` = c("original", "original", "ia", "ia"),
    check.names = FALSE,
    stringsAsFactors = FALSE
  )
)
saveRDS(source_test, chemin_source)

pour_chaque_indice <- function(indice) {
  chemin_sortie <- file.path(repertoire, indice)
  dir.create(chemin_sortie)
  rscript <- file.path(R.home("bin"), "Rscript")
  resultat_processus <- suppressWarnings(system2(
    rscript,
    args = c(
      "--vanilla",
      shQuote(lanceur),
      shQuote(chemin_source),
      shQuote("*source"),
      shQuote(indice),
      shQuote(chemin_sortie)
    ),
    stdout = TRUE,
    stderr = TRUE
  ))
  code_retour <- attr(resultat_processus, "status")
  if (is.null(code_retour)) code_retour <- 0L
  if (code_retour != 0L) {
    stop(paste("Échec du processus R :", paste(resultat_processus, collapse = "\n")))
  }

  tableau_path <- file.path(chemin_sortie, "specificites_formes_variables.csv")
  resume_path <- file.path(chemin_sortie, "resume_specificites_variables.json")
  stopifnot(file.exists(tableau_path), file.exists(resume_path))
  tableau <- utils::read.csv(tableau_path, stringsAsFactors = FALSE)
  resume <- jsonlite::fromJSON(resume_path)
  stopifnot(nrow(tableau) == 6L, resume$n_modalities == 2L, resume$index == indice)
  stopifnot(setequal(unique(tableau$modalite), c("original", "ia")))
  stopifnot(
    tableau$score_specificite[tableau$forme == "violence" & tableau$modalite == "original"] > 0,
    tableau$score_specificite[tableau$forme == "violence" & tableau$modalite == "ia"] < 0
  )
}

pour_chaque_indice("hypergeo")
pour_chaque_indice("chi2")
unlink(repertoire, recursive = TRUE, force = TRUE)
cat("test_runner_specificites_variables: OK\n")
