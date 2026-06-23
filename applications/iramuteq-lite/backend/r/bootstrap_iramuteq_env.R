#!/usr/bin/env Rscript

invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"), silent = TRUE)))
suppressWarnings(options(stringsAsFactors = FALSE))

parse_args <- function(args) {
  out <- list()
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) stop(paste0("Argument inattendu: ", key))
    if (i == length(args)) stop(paste0("Valeur manquante pour ", key))
    out[[substring(key, 3L)]] <- args[[i + 1L]]
    i <- i + 2L
  }
  out
}

scalar_chr <- function(x, default = "") {
  if (is.null(x) || !length(x) || is.na(x[[1]]) || !nzchar(as.character(x[[1]]))) {
    default
  } else {
    as.character(x[[1]])
  }
}

required_packages <- c(
  "jsonlite", "quanteda", "Matrix", "dplyr", "wordcloud", "RColorBrewer",
  "FactoMineR", "igraph", "proxy", "htmltools", "topicmodels", "irlba", "factoextra"
)

configure_user_library <- function() {
  lib_target <- Sys.getenv("IRAMUTEQ_R_LIBS_USER", unset = "")
  if (!nzchar(lib_target)) {
    lib_target <- file.path(path.expand("~"), ".local", "share", "iramuteq-lite", "R", "library")
  }
  if (!dir.exists(lib_target)) {
    dir.create(lib_target, recursive = TRUE, showWarnings = FALSE)
  }
  if (dir.exists(lib_target)) {
    .libPaths(unique(c(lib_target, .libPaths())))
  }
  normalizePath(.libPaths()[1], winslash = "/", mustWork = FALSE)
}

install_missing_packages <- function(packages, repo, lib) {
  if (!length(packages)) return(character(0))
  tryCatch(
    {
      utils::install.packages(
        packages,
        repos = repo,
        dependencies = TRUE,
        lib = lib
      )
      character(0)
    },
    error = function(e) {
      paste0("install.packages: ", conditionMessage(e))
    }
  )
}

args <- parse_args(commandArgs(trailingOnly = TRUE))
mode <- scalar_chr(args$mode, "install")
if (!mode %in% c("check", "install")) mode <- "install"

cran_repo <- trimws(Sys.getenv("R_CRAN_MIRROR", unset = "https://cloud.r-project.org"))
options(repos = c(CRAN = cran_repo))
lib_path <- configure_user_library()

installed_before <- rownames(installed.packages())
missing_before <- setdiff(required_packages, installed_before)
install_errors <- character(0)

if (identical(mode, "install") && length(missing_before)) {
  install_error <- install_missing_packages(missing_before, repo = cran_repo, lib = lib_path)
  if (length(install_error) && nzchar(install_error[[1]])) {
    install_errors <- c(install_errors, install_error[[1]])
  }
}

installed_after <- rownames(installed.packages())
missing_after <- setdiff(required_packages, installed_after)
installed_now <- setdiff(intersect(required_packages, installed_after), installed_before)

payload <- list(
  success = length(missing_after) == 0,
  mode = mode,
  library = lib_path,
  cran_repo = cran_repo,
  missing_before = unname(missing_before),
  installed_now = unname(installed_now),
  missing_after = unname(missing_after),
  install_errors = unname(install_errors)
)

cat(jsonlite::toJSON(payload, auto_unbox = TRUE, pretty = TRUE, null = "null"))
