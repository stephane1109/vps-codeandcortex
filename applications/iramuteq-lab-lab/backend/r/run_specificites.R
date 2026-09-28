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
source(file.path(repo_root, "iramuteqlite", "calcul_specificites.R"), local = TRUE)

args <- parse_args(commandArgs(trailingOnly = TRUE))
mode <- trimws(as.character(args$mode %||% "describe"))
source_path <- normalizePath(as.character(args$source %||% ""), winslash = "/", mustWork = TRUE)
source_data <- readRDS(source_path)

emit <- function(payload) {
  cat(jsonlite::toJSON(payload, auto_unbox = TRUE, null = "null", digits = NA))
}

tryCatch({
  if (identical(mode, "describe")) {
    emit(list(success = TRUE, variables = variables_specificites_disponibles(source_data)))
  } else if (identical(mode, "calculate")) {
    output_dir <- normalizePath(as.character(args[["output-dir"]] %||% ""), winslash = "/", mustWork = FALSE)
    term <- trimws(as.character(args$term %||% ""))
    variable <- trimws(as.character(args$variable %||% ""))
    index <- trimws(as.character(args$index %||% "hypergeo"))
    min_frequency <- suppressWarnings(as.integer(args[["min-frequency"]] %||% 10L))
    if (!nzchar(term)) stop("Le terme sélectionné est vide.")
    if (!nzchar(variable)) stop("Sélectionnez une variable ou les classes CHD.")
    if (!index %in% c("hypergeo", "chi2")) stop("Indice de spécificité non reconnu.")
    if (is.na(min_frequency) || min_frequency < 1L) min_frequency <- 1L
    result <- ecrire_resultats_specificites(
      source = source_data,
      term = term,
      variable = variable,
      index = index,
      min_frequency = min_frequency,
      output_dir = output_dir
    )
    emit(list(success = TRUE, summary = result$summary, result = result$result))
  } else {
    stop("Mode de calcul des spécificités non reconnu.")
  }
}, error = function(error) {
  emit(list(success = FALSE, message = conditionMessage(error)))
  quit(save = "no", status = 1L)
})
