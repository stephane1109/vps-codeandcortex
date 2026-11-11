#!/usr/bin/env Rscript
# Exécution indépendante du calcul historique de spécificité par terme.

split_lib_paths <- function(value) {
  if (is.null(value) || !length(value)) return(character(0))
  parts <- trimws(unlist(strsplit(as.character(value[[1]]), .Platform$path.sep, fixed = TRUE), use.names = FALSE))
  parts[nzchar(parts)]
}

lib_target <- Sys.getenv("IRAMUTEQ_R_LIBS_USER", unset = "")
.libPaths(unique(Filter(dir.exists, c(
  if (nzchar(lib_target)) lib_target else character(0),
  split_lib_paths(Sys.getenv("IRAMUTEQ_R_SYSTEM_LIBS", unset = "")),
  "/usr/lib/R/site-library", "/usr/lib/R/library",
  "/usr/local/lib/R/site-library", "/usr/local/lib/R/library", .libPaths()
))))


# La matrice enregistrée dans le RDS est une dgCMatrix (classe S4).
# Charger explicitement Matrix avant readRDS() pour enregistrer les méthodes S4
# de sous-indexation dans ce processus R indépendant.
if (!requireNamespace("Matrix", quietly = TRUE)) {
  stop("Le package R Matrix est nécessaire au calcul des spécificités par variables.")
}
suppressPackageStartupMessages(library(Matrix))

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L) stop("Arguments requis : source.rds, variable, indice, sortie.")
source_path <- normalizePath(args[[1L]], mustWork = TRUE)
variable <- args[[2L]]
indice <- args[[3L]]
repertoire <- args[[4L]]
script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1L]])
racine <- normalizePath(file.path(dirname(script_path), "..", ".."), mustWork = TRUE)
source(file.path(racine, "iramuteqlite", "calcul_specificites.R"), local = TRUE)
source(file.path(racine, "iramuteqlite", "specifilexicalevariables.R"), local = TRUE)
resultat <- ecrire_specificites_lexicales_variables(
  readRDS(source_path), variable, indice, repertoire)
cat(jsonlite::toJSON(resultat$summary, auto_unbox = TRUE, null = "null"))
