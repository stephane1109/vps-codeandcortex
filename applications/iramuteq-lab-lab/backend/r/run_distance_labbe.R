#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)
invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"), silent = TRUE)))

script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1]])
runner_dir <- normalizePath(dirname(script_path), winslash = "/", mustWork = TRUE)
repo_root <- normalizePath(file.path(runner_dir, "..", ".."), winslash = "/", mustWork = TRUE)

source(file.path(runner_dir, "pipeline_utilitaires.R"), local = TRUE)

required_packages <- c("jsonlite", "Matrix", "quanteda")
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, quietly = TRUE, logical(1))]
if (length(missing_packages)) {
  stop(paste("Packages R manquants:", paste(missing_packages, collapse = ", ")))
}

source(file.path(repo_root, "iramuteqlite", "nettoyage_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "variables_etoilees.R"), local = TRUE)
source(file.path(runner_dir, "pipeline_corpus.R"), local = TRUE)
source(file.path(runner_dir, "pipeline_pretraitement.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "distance-labbe.R"), local = TRUE)

job_logs <- character(0)
log_info <- function(message, progress = NULL) {
  job_logs <<- c(job_logs, as.character(message))
  invisible(NULL)
}

args <- parse_args(commandArgs(trailingOnly = TRUE))
input_path <- normalizePath(scalar_chr(args$input), winslash = "/", mustWork = TRUE)
config_path <- normalizePath(scalar_chr(args$config), winslash = "/", mustWork = TRUE)
output_dir <- normalizePath(scalar_chr(args[["output-dir"]]), winslash = "/", mustWork = FALSE)
variable <- trimws(scalar_chr(args$variable))
min_effectif <- scalar_int(args[["min-effectif"]], 10L, 1L)

emit <- function(payload) {
  cat(jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null", digits = NA))
}

tryCatch({
  if (!nzchar(variable)) stop("Sélectionnez une variable étoilée comportant au moins deux modalités.")
  config <- jsonlite::fromJSON(config_path, simplifyVector = FALSE)

  # Le seuil propre à Labbé est appliqué après l'agrégation par modalité.
  # Il ne doit pas être confondu avec min_docfreq, qui reste donc à 1 ici.
  config$min_docfreq <- 1L

  corpus <- import_corpus_iramuteq(input_path)
  if (quanteda::ndoc(corpus) < 2L) stop("Le corpus doit contenir au moins deux textes.")

  pipeline <- preparer_pipeline_chd(corpus, config)
  source_data <- list(
    dfm = pipeline$dfm_obj,
    docvars = as.data.frame(quanteda::docvars(pipeline$filtered_corpus), stringsAsFactors = FALSE),
    preprocessing = list(
      source_dictionnaire = pipeline$source_dictionnaire,
      langue = pipeline$langue,
      lemmatisation = scalar_bool(config$lexique_utiliser_lemmes, TRUE),
      stopwords = scalar_bool(config$retirer_stopwords, FALSE),
      ponctuation_supprimee = scalar_bool(config$supprimer_ponctuation, FALSE),
      chiffres_supprimes = scalar_bool(config$supprimer_chiffres, FALSE)
    )
  )

  available <- vapply(variables_labbe_disponibles(source_data), function(item) item$id, character(1))
  if (!variable %in% available) {
    stop("La variable étoilée sélectionnée est absente du corpus ou comporte moins de deux modalités.")
  }

  result <- ecrire_resultats_distance_labbe(source_data, variable, min_effectif, output_dir)
  emit(list(success = TRUE, summary = result$summary, logs = job_logs))
}, error = function(error) {
  emit(list(success = FALSE, message = conditionMessage(error), logs = job_logs))
  quit(save = "no", status = 1L)
})
