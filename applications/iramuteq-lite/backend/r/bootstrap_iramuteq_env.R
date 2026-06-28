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

split_lib_paths <- function(value) {
  if (is.null(value) || !length(value)) return(character(0))
  parts <- trimws(unlist(strsplit(as.character(value[[1]]), .Platform$path.sep, fixed = TRUE), use.names = FALSE))
  parts[nzchar(parts)]
}

configure_user_library <- function() {
  lib_target <- Sys.getenv("IRAMUTEQ_R_LIBS_USER", unset = "")
  if (!nzchar(lib_target)) {
    lib_target <- file.path(path.expand("~"), ".local", "share", "iramuteq-lite", "R", "library")
  }
  if (!dir.exists(lib_target)) {
    dir.create(lib_target, recursive = TRUE, showWarnings = FALSE)
  }
  system_candidates <- unique(c(
    split_lib_paths(Sys.getenv("IRAMUTEQ_R_SYSTEM_LIBS", unset = "")),
    split_lib_paths(Sys.getenv("R_LIBS_SITE", unset = "")),
    "/usr/lib/R/site-library",
    "/usr/lib/R/library",
    "/usr/local/lib/R/site-library",
    "/usr/local/lib/R/library",
    .libPaths()
  ))
  existing_system_libs <- Filter(dir.exists, system_candidates)
  if (dir.exists(lib_target)) {
    .libPaths(unique(c(lib_target, existing_system_libs)))
  } else {
    .libPaths(unique(existing_system_libs))
  }
  normalizePath(.libPaths()[1], winslash = "/", mustWork = FALSE)
}

install_missing_packages <- function(packages, repo, lib) {
  if (!length(packages)) return(character(0))
  install_errors <- character(0)
  # #### VPS / COOLIFY
  # Certains paquets CRAN (notamment fs, dependance indirecte de FactoMineR/factoextra)
  # echouent sur certains builds Docker si libuv n'est pas detecte correctement.
  # On force ici l'utilisation de la version embarquee de libuv pour rendre
  # le bootstrap plus robuste, meme si libuv1-dev n'est pas visible.
  # #### VPS / COOLIFY
  # `MAKEFLAGS=-j1` limite la compilation a un seul coeur pour reduire les pointes
  # memoire qui peuvent faire echouer les builds Coolify sur des VPS modestes.
  Sys.setenv(USE_BUNDLED_LIBUV = "1", MAKEFLAGS = "-j1")

  install_opts <- c("--no-html", "--no-help", "--no-demo", "--no-docs")
  dependency_scope <- c("Depends", "Imports", "LinkingTo")

  for (pkg in packages) {
    installed_now <- rownames(installed.packages())
    if (pkg %in% installed_now) {
      next
    }

    message("Installation package R requis: ", pkg)

    install_error <- tryCatch(
      {
        utils::install.packages(
          pkg,
          repos = repo,
          # #### IMPORTANT VPS / COOLIFY
          # On installe uniquement les dependances strictement necessaires
          # (Depends / Imports / LinkingTo) pour eviter de tirer des Suggests
          # lourdes ou non indispensables comme certaines briques geospatiales.
          dependencies = dependency_scope,
          lib = lib,
          Ncpus = 1L,
          INSTALL_opts = install_opts
        )
        NULL
      },
      error = function(e) {
        conditionMessage(e)
      }
    )

    if (!is.null(install_error) && nzchar(install_error)) {
      install_errors <- c(install_errors, paste0(pkg, ": ", install_error))
    }
  }

  install_errors
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

if (!length(install_errors) && length(missing_after)) {
  install_errors <- c(
    install_errors,
    paste0(
      "Packages R encore manquants apres installation: ",
      paste(missing_after, collapse = ", ")
    )
  )
}

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
cat("\n")

if (!isTRUE(payload$success)) {
  quit(save = "no", status = 1L)
}
