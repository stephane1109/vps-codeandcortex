#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)

suppressPackageStartupMessages({
  library(jsonlite)
  library(rainette)
  library(quanteda)
  library(htmltools)
})

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Usage: Rscript render_explorer.R <plot|docs|code> <analysis_bundle.rds> <params.json> [output.png]")
}

action <- as.character(args[[1]])
bundle_path <- normalizePath(args[[2]], winslash = "/", mustWork = TRUE)
params_path <- normalizePath(args[[3]], winslash = "/", mustWork = TRUE)
bundle <- readRDS(bundle_path)
params <- fromJSON(params_path, simplifyVector = TRUE)

as_bool <- function(value, default = FALSE) {
  if (is.null(value) || is.na(value)) return(default)
  isTRUE(value) || identical(value, 1L) || identical(value, 1) || identical(tolower(as.character(value)), "true")
}

safe_int <- function(value, default, minimum = NA_integer_, maximum = NA_integer_) {
  out <- suppressWarnings(as.integer(value))
  if (is.na(out)) out <- as.integer(default)
  if (!is.na(minimum)) out <- max(out, as.integer(minimum))
  if (!is.na(maximum)) out <- min(out, as.integer(maximum))
  out
}

escape_doc_html <- function(text) {
  gsub("\n", "<br>", htmlEscape(text), fixed = TRUE)
}

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) return(right)
  left
}

highlight_html <- function(text, pattern) {
  if (!nzchar(pattern)) return(text)
  tryCatch(
    gsub(
      pattern,
      "<span class='highlight'>\\0</span>",
      text,
      ignore.case = TRUE,
      perl = TRUE
    ),
    error = function(e) text
  )
}

build_plot_code <- function(current_k, measure, n_terms, same_scales, show_negative, text_size) {
  paste0(
    "rainette_plot(\n",
    "  res,\n",
    "  dtm,\n",
    "  k = ", current_k, ",\n",
    "  n_terms = ", n_terms, ",\n",
    "  free_scales = ", tolower(as.character(!same_scales)), ",\n",
    "  measure = \"", measure, "\",\n",
    "  show_negative = ", tolower(as.character(show_negative)), ",\n",
    "  text_size = ", text_size, "\n",
    ")"
  )
}

plot_res <- bundle$plot_res %||% bundle$res
cutree_res <- bundle$cutree_res %||% bundle$res
plot_dtm <- bundle$plot_dtm %||% bundle$dtm
corpus_src <- bundle$corpus_src
max_k <- safe_int(bundle$max_k, default = 2L, minimum = 2L)
max_k_plot <- safe_int(bundle$max_k_plot, default = max_k, minimum = 2L)
current_bundle_k <- safe_int(bundle$current_k, default = max_k, minimum = 2L)
current_k <- safe_int(params$k, default = max_k, minimum = 2L, maximum = max_k)

if (identical(action, "plot")) {
  if (length(args) < 4) {
    stop("Le mode plot attend un chemin de sortie PNG.")
  }

  output_png <- normalizePath(args[[4]], winslash = "/", mustWork = FALSE)
  output_dir <- dirname(output_png)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  measure <- if (!is.null(params$measure)) as.character(params$measure) else "chi2"
  n_terms <- safe_int(params$n_terms, default = 20L, minimum = 5L, maximum = 50L)
  same_scales <- as_bool(params$same_scales, default = TRUE)
  show_negative <- as_bool(params$show_negative, default = FALSE)
  text_size <- safe_int(params$text_size, default = 12L, minimum = 6L, maximum = 24L)

  res <- plot_res
  dtm <- plot_dtm
  plot_k <- min(current_k, max_k_plot)

  png(output_png, width = 1500, height = 980, res = 150)
  tryCatch(
    rainette::rainette_plot(
      res,
      dtm,
      k = plot_k,
      n_terms = n_terms,
      free_scales = !same_scales,
      measure = measure,
      show_negative = show_negative,
      text_size = text_size
    ),
    error = function(e) {
      plot.new()
      title("Exploration Rainette indisponible")
      text(
        0.5,
        0.6,
        labels = "Impossible de dessiner rainette_plot() pour ces paramètres.",
        cex = 1.1
      )
      text(
        0.5,
        0.45,
        labels = conditionMessage(e),
        cex = 0.9
      )
    }
  )
  dev.off()
  quit(save = "no", status = 0)
}

if (identical(action, "docs")) {
  groups <- if (!is.null(bundle$groups_current) && current_k == current_bundle_k) {
    as.integer(bundle$groups_current)
  } else {
    rainette::cutree(cutree_res, k = current_k)
  }

  if (length(groups) != quanteda::ndoc(corpus_src)) {
    stop("Le bundle Rainette est incohérent : le nombre de groupes ne correspond pas au corpus source.")
  }

  cluster <- safe_int(params$cluster, default = 1L, minimum = 1L, maximum = current_k)
  ndoc <- safe_int(params$ndoc, default = 100L, minimum = 1L)
  max_chars <- safe_int(params$nchar, default = 1000L, minimum = 10L)
  random_sample <- as_bool(params$random_sample, default = FALSE)
  filter_term <- if (!is.null(params$filter_term)) trimws(as.character(params$filter_term)) else ""

  sel <- groups == cluster & !is.na(groups)
  corpus_cluster <- corpus_src[sel]
  corpus_filtered <- corpus_cluster

  if (nzchar(filter_term)) {
    keep <- tryCatch(
      grepl(filter_term, as.character(corpus_cluster), ignore.case = TRUE, perl = TRUE),
      error = function(e) grepl(filter_term, as.character(corpus_cluster), ignore.case = TRUE, fixed = TRUE)
    )
    corpus_filtered <- corpus_cluster[keep]
  }

  size <- min(quanteda::ndoc(corpus_filtered), ndoc)
  if (size > 0) {
    if (random_sample) {
      docs_to_render <- quanteda::corpus_sample(corpus_filtered, size = size)
    } else {
      docs_to_render <- corpus_filtered[seq_len(size)]
    }
    texts <- as.character(docs_to_render)
    texts <- ifelse(
      nchar(texts) <= max_chars,
      texts,
      paste0(substr(texts, 1L, max_chars), "(...)")
    )
    texts <- vapply(texts, escape_doc_html, character(1))
    if (nzchar(filter_term)) {
      texts <- vapply(texts, highlight_html, character(1), pattern = filter_term)
    }
    docs_html <- paste(
      "<div class='doc'>",
      "<div class='docname'>",
      quanteda::docnames(docs_to_render),
      "</div>",
      texts,
      "</div><hr>",
      collapse = "\n"
    )
  } else {
    docs_html <- "<p class='empty-state'>Aucun segment ne correspond à ce filtre.</p>"
  }

  intro_html <- paste0(
    "Affichés : <strong>", min(ndoc, quanteda::ndoc(corpus_filtered)), "</strong>",
    " - Filtrés : <strong>", quanteda::ndoc(corpus_filtered), "</strong>",
    " - Taille du cluster : <strong>", quanteda::ndoc(corpus_cluster), "</strong>."
  )

  payload <- list(
    currentK = current_k,
    selectedCluster = cluster,
    clusterChoices = as.list(seq_len(current_k)),
    introHtml = intro_html,
    documentsHtml = docs_html,
    filteredCount = quanteda::ndoc(corpus_filtered),
    clusterCount = quanteda::ndoc(corpus_cluster)
  )
  cat(toJSON(payload, auto_unbox = TRUE, pretty = TRUE))
  quit(save = "no", status = 0)
}

if (identical(action, "code")) {
  measure <- if (!is.null(params$measure)) as.character(params$measure) else "chi2"
  n_terms <- safe_int(params$n_terms, default = 20L, minimum = 5L, maximum = 50L)
  same_scales <- as_bool(params$same_scales, default = TRUE)
  show_negative <- as_bool(params$show_negative, default = FALSE)
  text_size <- safe_int(params$text_size, default = 12L, minimum = 6L, maximum = 24L)
  plot_k <- min(current_k, max_k_plot)

  payload <- list(
    plotCode = build_plot_code(plot_k, measure, n_terms, same_scales, show_negative, text_size),
    cutreeCode = paste0("cutree_rainette(res, k = ", current_k, ")")
  )
  cat(toJSON(payload, auto_unbox = TRUE, pretty = TRUE))
  quit(save = "no", status = 0)
}

stop(sprintf("Action inconnue : %s", action))
