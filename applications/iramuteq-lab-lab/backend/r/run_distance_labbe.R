#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)
invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"), silent = TRUE)))

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

parse_args <- function(values) {
  result <- list()
  index <- 1L
  while (index <= length(values)) {
    key <- values[[index]]
    if (!startsWith(key, "--") || index == length(values)) stop("Arguments invalides.")
    result[[substring(key, 3L)]] <- values[[index + 1L]]
    index <- index + 2L
  }
  result
}

script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1]])
repo_root <- normalizePath(file.path(dirname(script_path), "..", ".."), winslash = "/", mustWork = TRUE)

if (!requireNamespace("jsonlite", quietly = TRUE) || !requireNamespace("Matrix", quietly = TRUE)) {
  stop("Les packages R jsonlite et Matrix sont nécessaires.")
}
source(file.path(repo_root, "iramuteqlite", "distance-labbe.R"), local = TRUE)

args <- parse_args(commandArgs(trailingOnly = TRUE))
mode <- trimws(as.character(args$mode %||% "describe"))
source_path <- normalizePath(as.character(args$source %||% ""), winslash = "/", mustWork = TRUE)
source_data <- readRDS(source_path)

emit <- function(payload) {
  cat(jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null", digits = NA))
}

tryCatch({
  if (identical(mode, "describe")) {
    emit(c(list(success = TRUE), decrire_distance_labbe(source_data)))
  } else if (identical(mode, "calculate")) {
    output_dir <- normalizePath(as.character(args[["output-dir"]] %||% ""), winslash = "/", mustWork = FALSE)
    variable <- trimws(as.character(args$variable %||% ""))
    min_effectif <- suppressWarnings(as.integer(args[["min-effectif"]] %||% "1"))
    if (!nzchar(variable)) stop("Sélectionnez les textes ou modalités à comparer.")
    if (!is.finite(min_effectif) || min_effectif < 1L) stop("La fréquence minimale doit être un entier supérieur ou égal à 1.")
    result <- ecrire_resultats_distance_labbe(source_data, variable, min_effectif, output_dir)
    emit(list(success = TRUE, summary = result$summary))
  } else {
    stop("Mode de distance intertextuelle non reconnu.")
  }
}, error = function(error) {
  emit(list(success = FALSE, message = conditionMessage(error)))
  quit(save = "no", status = 1L)
})
