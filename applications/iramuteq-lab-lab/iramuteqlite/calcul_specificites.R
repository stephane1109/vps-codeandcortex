# Calcul des specificites lexicales par modalite, selon la methode de Lafon.

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0L) y else x
}

normaliser_modalite_specificites <- function(x) {
  value <- trimws(as.character(x))
  value[is.na(value) | !nzchar(value)] <- NA_character_
  value
}

variables_specificites_disponibles <- function(source) {
  variables <- list(list(
    id = "__classes_chd__",
    label = "Classes CHD",
    modalities = sort(unique(normaliser_modalite_specificites(source$classes)), na.last = NA)
  ))

  docvars <- source$docvars
  if (is.null(docvars) || !is.data.frame(docvars)) return(variables)

  reserved <- c("Classes", "doc_id", "segment_source", "rst_source")
  candidates <- setdiff(names(docvars), reserved)
  candidates <- candidates[startsWith(candidates, "*")]
  for (variable in candidates) {
    modalities <- sort(unique(normaliser_modalite_specificites(docvars[[variable]])), na.last = NA)
    if (length(modalities) < 2L) next
    variables[[length(variables) + 1L]] <- list(
      id = variable,
      label = sub("^\\*", "", variable),
      modalities = modalities
    )
  }
  variables
}

exporter_source_specificites <- function(dfm_obj, corpus_obj, classes, output_dir, config = list()) {
  internal_dir <- file.path(output_dir, ".internal")
  dir.create(internal_dir, recursive = TRUE, showWarnings = FALSE)
  source_path <- file.path(internal_dir, "source_specificites.rds")

  matrix_docs_termes <- methods::as(dfm_obj, "dgCMatrix")
  docvars <- as.data.frame(quanteda::docvars(corpus_obj), stringsAsFactors = FALSE)
  source <- list(
    version = 2L,
    created_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
    dfm = matrix_docs_termes,
    docvars = docvars,
    classes = as.integer(classes),
    segment_ids = as.character(quanteda::docnames(corpus_obj)),
    segments = unname(enc2utf8(as.character(corpus_obj))),
    preprocessing = list(
      lexique = config$lexique_fichier %||% config$lexique_langue %||% NA_character_,
      lemmes = config$lexique_utiliser_lemmes %||% NA,
      min_docfreq = config$min_docfreq %||% NA_integer_,
      filtrage_morpho = config$filtrage_morpho %||% NA
    )
  )
  saveRDS(source, source_path, compress = "gzip")

  options_path <- file.path(output_dir, "variables_specificites.json")
  jsonlite::write_json(
    list(
      available = TRUE,
      variables = variables_specificites_disponibles(source),
      note = "Les calculs utilisent la matrice lexicale déjà traitée par cette CHD."
    ),
    options_path,
    auto_unbox = TRUE,
    pretty = TRUE,
    null = "null"
  )
  list(source = source_path, options = options_path)
}

table_lexicale_par_modalite <- function(source, variable) {
  groups <- if (identical(variable, "__classes_chd__")) {
    paste0("Classe ", source$classes)
  } else {
    if (is.null(source$docvars) || !variable %in% names(source$docvars)) {
      stop("La variable étoilée demandée n'est pas disponible dans cette analyse.")
    }
    normaliser_modalite_specificites(source$docvars[[variable]])
  }

  keep <- !is.na(groups) & nzchar(groups)
  if (sum(keep) < 2L) stop("Pas assez de segments renseignés pour cette variable.")
  groups <- factor(groups[keep], levels = sort(unique(groups[keep])))
  if (nlevels(groups) < 2L) stop("La variable doit comporter au moins deux modalités.")

  dfm <- source$dfm[keep, , drop = FALSE]
  indicator <- Matrix::sparseMatrix(
    i = seq_along(groups),
    j = as.integer(groups),
    x = 1,
    dims = c(length(groups), nlevels(groups)),
    dimnames = list(NULL, levels(groups))
  )
  table <- Matrix::t(dfm) %*% indicator
  rownames(table) <- colnames(dfm)
  colnames(table) <- levels(groups)
  methods::as(table, "dgCMatrix")
}

resoudre_totaux_reference_specificites <- function(counts, reference_col_totals = NULL) {
  observed_col_totals <- colSums(counts)
  reference <- suppressWarnings(as.numeric(reference_col_totals))
  valid_reference <- length(reference) == ncol(counts) &&
    all(is.finite(reference)) &&
    all(reference >= observed_col_totals)
  if (!valid_reference) reference <- observed_col_totals
  names(reference) <- colnames(counts)
  reference
}

calculer_scores_hypergeometriques <- function(table, reference_col_totals = NULL) {
  counts <- as.matrix(table)
  row_totals <- rowSums(counts)
  col_totals <- resoudre_totaux_reference_specificites(counts, reference_col_totals)
  corpus_total <- sum(col_totals)
  scores <- matrix(0, nrow(counts), ncol(counts), dimnames = dimnames(counts))
  log_p <- matrix(0, nrow(counts), ncol(counts), dimnames = dimnames(counts))

  for (j in seq_len(ncol(counts))) {
    observed <- counts[, j]
    expected <- row_totals * col_totals[[j]] / corpus_total
    under <- observed < expected
    current_log_p <- numeric(length(observed))
    if (any(under)) {
      current_log_p[under] <- stats::phyper(
        observed[under], row_totals[under], corpus_total - row_totals[under],
        col_totals[[j]], lower.tail = TRUE, log.p = TRUE
      )
    }
    if (any(!under)) {
      current_log_p[!under] <- stats::phyper(
        observed[!under] - 1, row_totals[!under], corpus_total - row_totals[!under],
        col_totals[[j]], lower.tail = FALSE, log.p = TRUE
      )
    }
    score_abs <- abs(current_log_p / log(10))
    scores[, j] <- ifelse(under, -score_abs, score_abs)
    log_p[, j] <- current_log_p
  }
  list(scores = scores, log_p = log_p)
}

calculer_scores_chi2_specificites <- function(table, reference_col_totals = NULL) {
  counts <- as.matrix(table)
  row_totals <- rowSums(counts)
  col_totals <- resoudre_totaux_reference_specificites(counts, reference_col_totals)
  corpus_total <- sum(col_totals)
  scores <- matrix(0, nrow(counts), ncol(counts), dimnames = dimnames(counts))
  log_p <- matrix(0, nrow(counts), ncol(counts), dimnames = dimnames(counts))

  for (j in seq_len(ncol(counts))) {
    a <- counts[, j]
    b <- row_totals - a
    c <- col_totals[[j]] - a
    d <- corpus_total - a - b - c
    denominator <- (a + b) * (c + d) * (a + c) * (b + d)
    chi2 <- ifelse(denominator > 0, corpus_total * (a * d - b * c)^2 / denominator, 0)
    expected <- row_totals * col_totals[[j]] / corpus_total
    scores[, j] <- ifelse(a < expected, -chi2, chi2)
    log_p[, j] <- stats::pchisq(chi2, df = 1, lower.tail = FALSE, log.p = TRUE)
  }
  list(scores = scores, log_p = log_p)
}

formater_p_scientifique_specificites <- function(log_p) {
  vapply(log_p, function(value) {
    if (!is.finite(value)) return("< 1e-300")
    exponent <- value / log(10)
    if (exponent < -300) return(paste0("< 1e", floor(exponent)))
    format(exp(value), scientific = TRUE, digits = 4)
  }, character(1))
}

safe_specificites_slug <- function(value) {
  slug <- iconv(as.character(value), to = "ASCII//TRANSLIT", sub = "")
  slug <- tolower(gsub("[^A-Za-z0-9_-]+", "-", slug))
  slug <- gsub("-+", "-", slug)
  slug <- gsub("^-|-$", "", slug)
  if (!nzchar(slug)) "specificites" else slug
}

ecrire_csv_utf8_specificites <- function(data, path, row.names = FALSE) {
  normalized <- as.data.frame(data, stringsAsFactors = FALSE)
  character_columns <- vapply(normalized, is.character, logical(1))
  normalized[character_columns] <- lapply(normalized[character_columns], enc2utf8)
  connection <- file(path, open = "wt", encoding = "UTF-8")
  on.exit(close(connection), add = TRUE)
  utils::write.csv(normalized, connection, row.names = row.names, fileEncoding = "")
}

ecrire_resultats_specificites <- function(source, term, variable, index, output_dir) {
  table_complete <- table_lexicale_par_modalite(source, variable)
  if (!term %in% rownames(table_complete)) {
    stop(paste0("La forme « ", term, " » n'est pas disponible dans la matrice lexicale de cette CHD."))
  }
  reference_col_totals <- Matrix::colSums(table_complete)
  table <- table_complete[term, , drop = FALSE]

  calculated <- if (identical(index, "chi2")) {
    calculer_scores_chi2_specificites(table, reference_col_totals = reference_col_totals)
  } else {
    calculer_scores_hypergeometriques(table, reference_col_totals = reference_col_totals)
  }
  counts <- as.matrix(table)
  scores <- calculated$scores
  log_p <- calculated$log_p
  row_totals <- rowSums(counts)
  col_totals <- as.numeric(reference_col_totals)
  names(col_totals) <- colnames(counts)
  corpus_total <- sum(col_totals)
  term_index <- 1L
  observed <- counts[term_index, ]
  expected <- row_totals[[term_index]] * col_totals / corpus_total
  selected_scores <- scores[term_index, ]
  selected_log_p <- log_p[term_index, ]

  result <- data.frame(
    terme = term,
    modalite = colnames(counts),
    occurrences_modalite = as.integer(observed),
    occurrences_attendues = round(expected, 4),
    occurrences_totales_terme = as.integer(row_totals[[term_index]]),
    score_specificite = round(as.numeric(selected_scores), 4),
    p_value = formater_p_scientifique_specificites(selected_log_p),
    interpretation = ifelse(selected_scores > 0, "surreprésenté", ifelse(selected_scores < 0, "sous-représenté", "attendu")),
    stringsAsFactors = FALSE
  )

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  ecrire_csv_utf8_specificites(result, file.path(output_dir, "specificites_terme_modalites.csv"))

  png_path <- file.path(output_dir, "graphique_specificites.png")
  grDevices::png(png_path, width = 1600, height = max(900, 170 + 110 * nrow(result)), res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  margins <- max(8, min(18, max(nchar(result$modalite), na.rm = TRUE) * 0.62))
  graphics::par(mar = c(5, margins, 4, 2))
  colors <- ifelse(result$score_specificite >= 0, "#217ce7", "#e05a47")
  graphics::barplot(
    result$score_specificite,
    names.arg = result$modalite,
    horiz = TRUE,
    las = 1,
    col = colors,
    border = NA,
    xlab = if (identical(index, "chi2")) "χ²" else "Score de spécificité (Lafon)",
    main = paste0("Spécificités de « ", term, " » par modalité")
  )
  graphics::abline(v = 0, col = "#444444", lwd = 1)
  grDevices::dev.off()
  on.exit(NULL, add = FALSE)

  variable_label <- if (identical(variable, "__classes_chd__")) "Classes CHD" else sub("^\\*", "", variable)
  configuration <- list(
    term = term,
    variable = variable,
    variable_label = variable_label,
    index = index,
    index_label = if (identical(index, "chi2")) "χ²" else "Loi hypergéométrique (Lafon)",
    modalities = colnames(counts),
    method = "Spécificité du terme sélectionné calculée à partir de la matrice lexicale complète traitée de la CHD."
  )
  jsonlite::write_json(configuration, file.path(output_dir, "configuration_specificites.json"), auto_unbox = TRUE, pretty = TRUE)
  summary <- c(configuration, list(
    best_modality = result$modalite[[which.max(result$score_specificite)]],
    best_score = max(result$score_specificite),
    n_modalities = ncol(counts)
  ))
  jsonlite::write_json(summary, file.path(output_dir, "resume_specificites.json"), auto_unbox = TRUE, pretty = TRUE)
  list(summary = summary, result = result)
}
