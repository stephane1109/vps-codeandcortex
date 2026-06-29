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
  "jsonlite", "Matrix", "quanteda", "dplyr", "wordcloud", "RColorBrewer",
  "FactoMineR", "igraph", "proxy", "htmltools", "topicmodels", "irlba", "factoextra"
)

required_min_versions <- c(
  Matrix = "1.5.0"
)

split_lib_paths <- function(value) {
  if (is.null(value) || !length(value)) return(character(0))
  parts <- trimws(unlist(strsplit(as.character(value[[1]]), .Platform$path.sep, fixed = TRUE), use.names = FALSE))
  parts[nzchar(parts)]
}

package_installed_version <- function(pkg) {
  tryCatch(as.character(utils::packageVersion(pkg)), error = function(e) "")
}

package_required_version <- function(pkg) {
  version <- required_min_versions[[pkg]]
  if (is.null(version) || !length(version) || is.na(version[[1]]) || !nzchar(as.character(version[[1]]))) {
    ""
  } else {
    as.character(version[[1]])
  }
}

package_needs_install <- function(pkg) {
  installed_version <- package_installed_version(pkg)
  if (!nzchar(installed_version)) {
    return(TRUE)
  }
  min_version <- package_required_version(pkg)
  if (!nzchar(min_version)) {
    return(FALSE)
  }
  utils::compareVersion(installed_version, min_version) < 0
}

describe_package_requirement <- function(pkg) {
  installed_version <- package_installed_version(pkg)
  min_version <- package_required_version(pkg)
  if (!nzchar(min_version)) {
    return(pkg)
  }
  if (!nzchar(installed_version)) {
    return(sprintf("%s (>= %s requis)", pkg, min_version))
  }
  if (utils::compareVersion(installed_version, min_version) < 0) {
    return(sprintf("%s (%s installe, >= %s requis)", pkg, installed_version, min_version))
  }
  pkg
}

sort_packages_for_install <- function(packages) {
  priority <- c("Matrix")
  unique(c(intersect(priority, packages), setdiff(packages, priority)))
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
  packages <- sort_packages_for_install(packages)
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
  if (!nzchar(Sys.getenv("R_MAKEVARS_USER", unset = "")) && file.exists("/etc/R/Makevars.site")) {
    Sys.setenv(R_MAKEVARS_USER = "/etc/R/Makevars.site")
  }

  install_opts <- c("--no-html", "--no-help", "--no-demo", "--no-docs")
  dependency_scope <- c("Depends", "Imports", "LinkingTo")

  for (pkg in packages) {
    if (!package_needs_install(pkg)) {
      next
    }

    message("Installation / mise a niveau package R requis: ", describe_package_requirement(pkg))

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

installed_versions_before <- setNames(vapply(required_packages, package_installed_version, character(1)), required_packages)
missing_before <- required_packages[vapply(required_packages, package_needs_install, logical(1))]
outdated_before <- missing_before[nzchar(installed_versions_before[missing_before])]
install_errors <- character(0)

if (identical(mode, "install") && length(missing_before)) {
  install_error <- install_missing_packages(missing_before, repo = cran_repo, lib = lib_path)
  if (length(install_error)) {
    install_errors <- c(install_errors, install_error)
  }
}

installed_versions_after <- setNames(vapply(required_packages, package_installed_version, character(1)), required_packages)
missing_after <- required_packages[vapply(required_packages, package_needs_install, logical(1))]
outdated_after <- missing_after[nzchar(installed_versions_after[missing_after])]
installed_now <- required_packages[!nzchar(installed_versions_before[required_packages]) & nzchar(installed_versions_after[required_packages])]
upgraded_now <- required_packages[
  nzchar(installed_versions_before[required_packages]) &
    nzchar(installed_versions_after[required_packages]) &
    installed_versions_before[required_packages] != installed_versions_after[required_packages]
]

if (!length(install_errors) && length(missing_after)) {
  install_errors <- c(
    install_errors,
    paste0(
      "Packages R encore manquants ou obsoletes apres installation: ",
      paste(vapply(missing_after, describe_package_requirement, character(1)), collapse = ", ")
    )
  )
}

payload <- list(
  success = length(missing_after) == 0,
  mode = mode,
  library = lib_path,
  cran_repo = cran_repo,
  missing_before = unname(missing_before),
  outdated_before = unname(outdated_before),
  installed_now = unname(installed_now),
  upgraded_now = unname(upgraded_now),
  missing_after = unname(missing_after),
  outdated_after = unname(outdated_after),
  install_errors = unname(install_errors)
)

cat(jsonlite::toJSON(payload, auto_unbox = TRUE, pretty = TRUE, null = "null"))
cat("\n")

if (!isTRUE(payload$success)) {
  quit(save = "no", status = 1L)
}
