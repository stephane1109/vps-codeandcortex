options(
  repos = c(
    JUBA = Sys.getenv("RAINETTE_REPO", unset = "https://juba.r-universe.dev"),
    CRAN = Sys.getenv("R_CRAN_MIRROR", unset = "https://cloud.r-project.org")
  )
)

split_lib_paths <- function(value) {
  if (is.null(value) || !length(value)) return(character(0))
  parts <- trimws(unlist(strsplit(as.character(value[[1]]), .Platform$path.sep, fixed = TRUE), use.names = FALSE))
  parts[nzchar(parts)]
}

lib_target <- Sys.getenv("CHDRAINETTE_R_LIBS_USER", unset = "")
if (!nzchar(lib_target)) {
  lib_target <- file.path(path.expand("~"), ".local", "share", "chdrainette", "R", "library")
}
dir.create(lib_target, recursive = TRUE, showWarnings = FALSE)

system_candidates <- unique(c(
  split_lib_paths(Sys.getenv("R_LIBS_SITE", unset = "")),
  "/usr/lib/R/site-library",
  "/usr/lib/R/library",
  "/usr/local/lib/R/site-library",
  "/usr/local/lib/R/library",
  .libPaths()
))
.libPaths(unique(c(lib_target, Filter(dir.exists, system_candidates))))

packages_required <- c(
  "FactoMineR",
  "igraph",
  "jsonlite",
  "dplyr",
  "htmltools",
  "quanteda",
  "rainette",
  "RColorBrewer",
  "remotes",
  "stopwords",
  "stringi",
  "wordcloud"
)

install_if_missing <- function(packages) {
  installed <- rownames(installed.packages())
  missing <- setdiff(packages, installed)
  if (!length(missing)) return(invisible(character(0)))

  standard_packages <- setdiff(missing, "FactoMineR")
  if (length(standard_packages)) {
    install.packages(standard_packages, dependencies = TRUE, lib = .libPaths()[1])
  }

  if ("FactoMineR" %in% missing && !"FactoMineR" %in% rownames(installed.packages())) {
    tryCatch(
      install.packages("FactoMineR", dependencies = TRUE, lib = .libPaths()[1]),
      error = function(error) {
        message("Installation CRAN de FactoMineR impossible : ", conditionMessage(error))
      }
    )
  }

  if (!"FactoMineR" %in% rownames(installed.packages())) {
    if (!"remotes" %in% rownames(installed.packages())) {
      install.packages("remotes", dependencies = TRUE, lib = .libPaths()[1])
    }
    remotes::install_github("husson/FactoMineR", dependencies = NA, upgrade = "never", lib = .libPaths()[1])
  }

  invisible(setdiff(packages, rownames(installed.packages())))
}

remaining <- install_if_missing(packages_required)

if (length(remaining)) {
  stop(sprintf("Packages R manquants après installation: %s", paste(remaining, collapse = ", ")))
}

cat("Packages R installés dans :", .libPaths()[1], "\n")
