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
  "jsonlite",
  "rainette",
  "quanteda",
  "wordcloud",
  "RColorBrewer",
  "dplyr",
  "htmltools",
  "udpipe"
)

install_if_missing <- function(packages) {
  missing <- setdiff(packages, rownames(installed.packages()))
  if (!length(missing)) return(invisible(character(0)))
  install.packages(missing, dependencies = TRUE, lib = .libPaths()[1])
  invisible(setdiff(packages, rownames(installed.packages())))
}

remaining <- install_if_missing(packages_required)

if (length(remaining)) {
  stop(sprintf("Packages R manquants après installation: %s", paste(remaining, collapse = ", ")))
}

cat("Packages R installés dans :", .libPaths()[1], "\n")
