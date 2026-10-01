#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)
invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"), silent = TRUE)))

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

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("Le package R jsonlite est nécessaire.")
}
source(file.path(repo_root, "iramuteqlite", "analyse-chrono.R"), local = TRUE)

args <- parse_args(commandArgs(trailingOnly = TRUE))
mode <- trimws(as.character(args$mode %||% "describe"))
source_path <- normalizePath(as.character(args$source %||% ""), winslash = "/", mustWork = TRUE)
source_data <- readRDS(source_path)

emit <- function(payload) {
  cat(jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null", digits = NA))
}

tryCatch({
  if (identical(mode, "describe")) {
    emit(c(list(success = TRUE), decrire_analyse_chrono(source_data)))
  } else if (identical(mode, "calculate")) {
    output_dir <- normalizePath(as.character(args[["output-dir"]] %||% ""), winslash = "/", mustWork = FALSE)
    time_variable <- trimws(as.character(args[["time-variable"]] %||% ""))
    comparison_variable <- trimws(as.character(args[["comparison-variable"]] %||% ""))
    if (!nzchar(time_variable)) stop("Sélectionnez une variable temporelle.")
    if (!nzchar(comparison_variable)) stop("Sélectionnez une variable de comparaison.")
    result <- ecrire_resultats_chrono(
      source = source_data,
      time_variable = time_variable,
      comparison_variable = comparison_variable,
      output_dir = output_dir
    )
    emit(list(success = TRUE, summary = result$summary))
  } else {
    stop("Mode d'analyse chronologique non reconnu.")
  }
}, error = function(error) {
  emit(list(success = FALSE, message = conditionMessage(error)))
  quit(save = "no", status = 1L)
})
