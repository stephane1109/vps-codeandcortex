options(repos = c(CRAN = Sys.getenv("R_CRAN_MIRROR", unset = "https://cloud.r-project.org")))

split_lib_paths <- function(value) {
  if (is.null(value) || !length(value)) return(character(0))
  parts <- trimws(unlist(strsplit(as.character(value[[1]]), .Platform$path.sep, fixed = TRUE), use.names = FALSE))
  parts[nzchar(parts)]
}

lib_target <- Sys.getenv("IRAMUTEQ_R_LIBS_USER", unset = "")
if (!nzchar(lib_target)) {
  lib_target <- file.path(path.expand("~"), ".local", "share", "iramuteq-lite", "R", "library")
}
dir.create(lib_target, recursive = TRUE, showWarnings = FALSE)
system_candidates <- unique(c(
  split_lib_paths(Sys.getenv("IRAMUTEQ_R_SYSTEM_LIBS", unset = "")),
  split_lib_paths(Sys.getenv("R_LIBS_SITE", unset = "")),
  "/usr/lib/R/site-library",
  "/usr/lib/R/library",
  "/usr/local/lib/R/site-library",
  "/usr/local/lib/R/library",
  .libPaths()
))
.libPaths(unique(c(lib_target, Filter(dir.exists, system_candidates))))

cran_packages <- c(
  "ape",
  "bslib",
  "colorspace",
  "DT",
  "dplyr",
  "factoextra",
  "FactoMineR",
  "htmltools",
  "igraph",
  "intergraph",
  "irlba",
  "jsonlite",
  "markdown",
  "Matrix",
  "plotly",
  "proxy",
  "quanteda",
  "RColorBrewer",
  "remotes",
  "reticulate",
  "rgexf",
  "rgl",
  "shiny",
  "shinyFiles",
  "sna",
  "topicmodels",
  "visNetwork",
  "wordcloud",
  "ggplot2"
)

install_if_missing <- function(packages) {
  missing <- setdiff(packages, rownames(installed.packages()))
  if (!length(missing)) return(invisible(character(0)))
  install.packages(missing, dependencies = TRUE, lib = .libPaths()[1])
  invisible(setdiff(packages, rownames(installed.packages())))
}

remaining <- install_if_missing(cran_packages)

if ("FactoMineR" %in% remaining && "remotes" %in% rownames(installed.packages())) {
  tryCatch(
    remotes::install_github(
      "husson/FactoMineR",
      dependencies = NA,
      upgrade = "never",
      lib = .libPaths()[1]
    ),
    error = function(e) message("Installation GitHub de FactoMineR impossible: ", conditionMessage(e))
  )
}

remaining <- setdiff(cran_packages, rownames(installed.packages()))
if (length(remaining)) {
  stop(sprintf("Packages R manquants après installation: %s", paste(remaining, collapse = ", ")))
}

cat("Packages R installés dans :", .libPaths()[1], "\n")
