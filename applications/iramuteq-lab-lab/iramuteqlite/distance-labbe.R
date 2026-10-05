# Distance intertextuelle de Labbe.
#
# Adaptation testee de l'implementation historique de Pierre Ratinaud
# (IRaMuTeQ, GNU/GPL), d'apres C. Labbe et D. Labbe (2003).

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0L) y else x
}

normaliser_modalite_labbe <- function(x) {
  value <- trimws(enc2utf8(as.character(x)))
  value[is.na(value) | !nzchar(value)] <- NA_character_
  value
}

nom_variable_labbe <- function(variable) {
  if (identical(variable, "__classes_chd__")) "Classes CHD" else sub("^\\*", "", variable)
}

variables_labbe_disponibles <- function(source) {
  variables <- list()
  classes <- suppressWarnings(as.integer(source$classes))
  class_values <- sort(unique(classes[is.finite(classes) & classes > 0L]))
  if (length(class_values) >= 2L) {
    variables[[length(variables) + 1L]] <- list(
      id = "__classes_chd__",
      label = "Classes CHD",
      modalities = paste0("Classe ", class_values),
      n_modalities = length(class_values)
    )
  }

  docvars <- source$docvars
  if (is.null(docvars) || !is.data.frame(docvars)) return(variables)
  reserved <- c("Classes", "doc_id", "segment_source", "rst_source")
  candidates <- setdiff(names(docvars), reserved)
  candidates <- candidates[startsWith(candidates, "*")]
  for (variable in candidates) {
    modalities <- sort(unique(normaliser_modalite_labbe(docvars[[variable]])), na.last = NA)
    if (length(modalities) < 2L) next
    variables[[length(variables) + 1L]] <- list(
      id = variable,
      label = nom_variable_labbe(variable),
      modalities = modalities,
      n_modalities = length(modalities)
    )
  }
  variables
}

decrire_distance_labbe <- function(source) {
  variables <- variables_labbe_disponibles(source)
  list(
    available = length(variables) > 0L,
    variables = variables,
    preprocessing = source$preprocessing %||% list(),
    note = paste(
      "Le calcul réutilise la matrice lexicale finale de la CHD.",
      "Chaque modalité sélectionnée est traitée comme un texte à comparer."
    )
  )
}

valider_table_labbe <- function(tab) {
  if (inherits(tab, "Matrix")) tab <- as.matrix(tab)
  tab <- as.matrix(tab)
  storage.mode(tab) <- "double"
  if (length(dim(tab)) != 2L || ncol(tab) < 2L) {
    stop("La distance de Labbé nécessite au moins deux textes ou modalités.")
  }
  if (!nrow(tab)) stop("La table lexicale ne contient aucune forme.")
  if (any(!is.finite(tab)) || any(tab < 0)) {
    stop("La table lexicale doit contenir uniquement des effectifs finis et positifs ou nuls.")
  }
  if (any(colSums(tab) <= 0)) {
    stop("Chaque texte ou modalité doit contenir au moins une occurrence.")
  }
  if (is.null(colnames(tab)) || any(!nzchar(trimws(colnames(tab))))) {
    colnames(tab) <- paste0("Texte ", seq_len(ncol(tab)))
  }
  tab
}

calculer_distance_labbe_paire <- function(x, y, tab, valider = TRUE) {
  if (isTRUE(valider)) tab <- valider_table_labbe(tab)
  x <- suppressWarnings(as.integer(x))
  y <- suppressWarnings(as.integer(y))
  if (!is.finite(x) || !is.finite(y) || x < 1L || y < 1L || x > ncol(tab) || y > ncol(tab) || x == y) {
    stop("Les deux colonnes à comparer doivent être différentes et présentes dans la table.")
  }

  pair <- cbind(tab[, x], tab[, y])
  totals <- colSums(pair)
  small_index <- if (totals[[1L]] <= totals[[2L]]) 1L else 2L
  large_index <- 3L - small_index
  small <- pair[, small_index]
  large <- pair[, large_index]
  coefficient <- totals[[small_index]] / totals[[large_index]]
  large_reduced <- large * coefficient

  # Le vocabulaire réduit conserve les formes du petit texte et les formes du
  # grand texte dont la fréquence ramenée à la petite taille atteint au moins 1.
  retained <- small > 0 | large_reduced >= 1
  numerator <- sum(abs(small[retained] - large_reduced[retained]))
  denominator <- totals[[small_index]] + sum(large_reduced[large_reduced >= 1])
  distance <- if (denominator > 0) numerator / denominator else NA_real_
  distance <- min(1, max(0, distance))

  list(
    distance = unname(distance),
    coefficient = unname(coefficient),
    taille_1 = unname(totals[[1L]]),
    taille_2 = unname(totals[[2L]]),
    rapport_tailles = unname(min(totals) / max(totals)),
    formes_retenues = sum(retained)
  )
}

calculer_matrice_distance_labbe <- function(tab) {
  tab <- valider_table_labbe(tab)
  result <- matrix(0, nrow = ncol(tab), ncol = ncol(tab), dimnames = list(colnames(tab), colnames(tab)))
  details <- vector("list", choose(ncol(tab), 2L))
  detail_index <- 0L
  for (i in seq_len(ncol(tab) - 1L)) {
    for (j in seq.int(i + 1L, ncol(tab))) {
      current <- calculer_distance_labbe_paire(i, j, tab, valider = FALSE)
      result[i, j] <- current$distance
      result[j, i] <- current$distance
      detail_index <- detail_index + 1L
      details[[detail_index]] <- data.frame(
        texte_1 = colnames(tab)[[i]],
        texte_2 = colnames(tab)[[j]],
        distance_labbe = current$distance,
        occurrences_texte_1 = current$taille_1,
        occurrences_texte_2 = current$taille_2,
        rapport_tailles = current$rapport_tailles,
        coefficient_reduction = current$coefficient,
        formes_retenues = current$formes_retenues,
        prudence = if (current$rapport_tailles < 0.1) "tailles très déséquilibrées" else "",
        stringsAsFactors = FALSE
      )
    }
  }
  list(matrice = result, paires = do.call(rbind, details))
}

# Alias compatibles avec le nommage du script historique d'IRaMuTeQ.
compute.labbe <- function(x, y, tab) calculer_distance_labbe_paire(x, y, tab)$distance
dist.labbe <- function(tab) calculer_matrice_distance_labbe(tab)$matrice

table_labbe_par_modalite <- function(source, variable, min_effectif = 1L) {
  min_effectif <- suppressWarnings(as.integer(min_effectif))
  if (!is.finite(min_effectif) || min_effectif < 1L) min_effectif <- 1L
  docvars <- source$docvars
  classes <- suppressWarnings(as.integer(source$classes))
  groups <- if (identical(variable, "__classes_chd__")) {
    if (!length(classes)) stop("Les classes CHD sont indisponibles.")
    ifelse(is.finite(classes) & classes > 0L, paste0("Classe ", classes), NA_character_)
  } else {
    if (is.null(docvars) || !is.data.frame(docvars) || !variable %in% names(docvars)) {
      stop("La variable étoilée demandée n'est pas disponible dans cette CHD.")
    }
    normaliser_modalite_labbe(docvars[[variable]])
  }

  dfm <- source$dfm
  if (is.null(dfm) || nrow(dfm) != length(groups)) {
    stop("La matrice lexicale et les modalités ne sont pas alignées.")
  }
  keep <- !is.na(groups) & nzchar(groups)
  if (sum(keep) < 2L) stop("Pas assez de segments renseignés pour cette variable.")
  groups <- factor(groups[keep], levels = sort(unique(groups[keep])))
  if (nlevels(groups) < 2L) stop("La variable doit comporter au moins deux modalités.")

  dfm <- dfm[keep, , drop = FALSE]
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
  table <- table[Matrix::rowSums(table) >= min_effectif, , drop = FALSE]
  if (!nrow(table)) stop("Aucune forme ne respecte la fréquence minimale choisie.")
  valider_table_labbe(table)
}

ecrire_csv_utf8_labbe <- function(data, path, row.names = FALSE) {
  connection <- file(path, open = "wt", encoding = "UTF-8")
  on.exit(close(connection), add = TRUE)
  utils::write.csv(data, connection, row.names = row.names, fileEncoding = "")
}

tracer_dendrogramme_labbe <- function(distance_matrix, path) {
  clustering <- stats::hclust(stats::as.dist(distance_matrix), method = "ward.D2")
  grDevices::png(path, width = 1800, height = 1200, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mar = c(8, 5, 4, 2))
  graphics::plot(
    clustering,
    main = "Classification des distances intertextuelles",
    xlab = "Textes ou modalités",
    sub = "Méthode Ward.D2",
    ylab = "Distance de Labbé",
    hang = -1,
    col = "#217ce7"
  )
  invisible(clustering)
}

tracer_carte_labbe <- function(distance_matrix, path) {
  clustering <- stats::hclust(stats::as.dist(distance_matrix), method = "ward.D2")
  palette <- grDevices::colorRampPalette(c("#f7fbff", "#9ec9f7", "#217ce7", "#0b3972"))(100)
  grDevices::png(path, width = 1800, height = 1500, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mar = c(10, 10, 5, 3))
  stats::heatmap(
    distance_matrix,
    Rowv = stats::as.dendrogram(clustering),
    Colv = "Rowv",
    symm = TRUE,
    scale = "none",
    col = palette,
    margins = c(12, 12),
    main = "Matrice des distances de Labbé"
  )
  invisible(clustering)
}

ecrire_resultats_distance_labbe <- function(source, variable, min_effectif, output_dir) {
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  table <- table_labbe_par_modalite(source, variable, min_effectif)
  calculated <- calculer_matrice_distance_labbe(table)
  matrix_distance <- calculated$matrice
  pairs <- calculated$paires
  pairs$distance_labbe <- round(pairs$distance_labbe, 6)
  pairs$rapport_tailles <- round(pairs$rapport_tailles, 6)
  pairs$coefficient_reduction <- round(pairs$coefficient_reduction, 6)

  ecrire_csv_utf8_labbe(matrix_distance, file.path(output_dir, "distance_labbe_matrice.csv"), row.names = TRUE)
  ecrire_csv_utf8_labbe(pairs, file.path(output_dir, "distance_labbe_paires.csv"))
  text_stats <- data.frame(
    texte_modalite = colnames(table),
    occurrences = as.numeric(colSums(table)),
    formes_distinctes = as.integer(colSums(table > 0)),
    stringsAsFactors = FALSE
  )
  ecrire_csv_utf8_labbe(text_stats, file.path(output_dir, "distance_labbe_textes.csv"))
  tracer_dendrogramme_labbe(matrix_distance, file.path(output_dir, "distance_labbe_dendrogramme.png"))
  tracer_carte_labbe(matrix_distance, file.path(output_dir, "distance_labbe_carte.png"))

  sizes <- colSums(table)
  warnings <- character(0)
  small <- names(sizes)[sizes < 1000]
  if (length(small)) {
    warnings <- c(warnings, paste0("Interprétation prudente : moins de 1 000 occurrences pour ", paste(small, collapse = ", "), "."))
  }
  if (any(pairs$rapport_tailles < 0.1)) {
    warnings <- c(warnings, "Interprétation prudente : au moins une paire présente un rapport de tailles inférieur à 1:10.")
  }
  variable_label <- nom_variable_labbe(variable)
  summary <- list(
    variable = variable,
    variable_label = variable_label,
    min_effectif = as.integer(min_effectif),
    n_textes = ncol(table),
    n_formes = nrow(table),
    distance_min = min(pairs$distance_labbe),
    distance_max = max(pairs$distance_labbe),
    paire_plus_proche = paste(pairs$texte_1[[which.min(pairs$distance_labbe)]], pairs$texte_2[[which.min(pairs$distance_labbe)]], sep = " / "),
    paire_plus_eloignee = paste(pairs$texte_1[[which.max(pairs$distance_labbe)]], pairs$texte_2[[which.max(pairs$distance_labbe)]], sep = " / "),
    warnings = unname(warnings),
    method = "Distance intertextuelle de Labbé sur la matrice lexicale traitée de la CHD."
  )
  jsonlite::write_json(summary, file.path(output_dir, "resume_distance_labbe.json"), auto_unbox = TRUE, pretty = TRUE, null = "null")
  configuration <- list(
    variable = variable,
    variable_label = variable_label,
    min_effectif = as.integer(min_effectif),
    modalities = colnames(table),
    preprocessing = source$preprocessing %||% list(),
    formula = "somme des écarts absolus après réduction du grand texte, normalisée par les deux longueurs comparables",
    implementation = "Matrice symétrique ; seuil du vocabulaire réduit appliqué uniformément à fréquence attendue >= 1."
  )
  jsonlite::write_json(configuration, file.path(output_dir, "configuration_distance_labbe.json"), auto_unbox = TRUE, pretty = TRUE, null = "null")
  list(summary = summary, matrix = matrix_distance, pairs = pairs)
}
