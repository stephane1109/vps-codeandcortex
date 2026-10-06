# Distance intertextuelle de Labbe.
#
# Calcul repris de l'implementation de Pierre Ratinaud
# (IRaMuTeQ, GNU/GPL), d'apres C. Labbe et D. Labbe (2003).

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0L) y else x
}

normaliser_modalite_labbe <- function(x) {
  value <- trimws(enc2utf8(as.character(x)))
  missing <- is.na(value) | !nzchar(value) | toupper(value) %in% c("NA", "N/A", "NULL")
  value[missing] <- NA_character_
  value
}

nom_variable_labbe <- function(variable) {
  sub("^\\*", "", variable)
}

variables_labbe_disponibles <- function(source) {
  variables <- list()
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
      "Le calcul utilise la table lexicale construite directement à partir du corpus.",
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
  large_index <- if (totals[[1L]] > totals[[2L]]) 1L else 2L
  small_index <- if (totals[[1L]] > totals[[2L]]) 2L else 1L

  # Ces deux branches reprennent volontairement les seuils du script officiel.
  if (large_index == 1L) {
    coefficient <- totals[[2L]] / totals[[1L]]
    pair[, 1L] <- pair[, 1L] * coefficient
    reduced_large <- pair[, 1L]
    reduced_large_sum <- sum(reduced_large[reduced_large >= 1])
  } else {
    coefficient <- totals[[1L]] / totals[[2L]]
    pair[, 2L] <- pair[, 2L] * coefficient
    reduced_large <- pair[, 2L]
    reduced_large_sum <- sum(reduced_large[reduced_large > 1])
  }

  common <- which((pair[, 1L] > 0) & (pair[, 2L] > 0))
  from_small <- which((pair[, small_index] > 0) & (pair[, large_index] == 0))
  from_large <- which((pair[, small_index] == 0) & (pair[, large_index] >= 1))
  numerator <-
    sum(abs(pair[common, small_index] - pair[common, large_index])) +
    sum(abs(pair[from_small, small_index] - pair[from_small, large_index])) +
    sum(abs(pair[from_large, small_index] - pair[from_large, large_index]))
  denominator <- totals[[small_index]] + reduced_large_sum
  distance <- numerator / denominator
  retained <- unique(c(common, from_small, from_large))

  list(
    distance = unname(distance),
    coefficient = unname(coefficient),
    taille_1 = unname(totals[[1L]]),
    taille_2 = unname(totals[[2L]]),
    rapport_tailles = unname(min(totals) / max(totals)),
    formes_retenues = length(retained)
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
  if (is.null(docvars) || !is.data.frame(docvars) || !variable %in% names(docvars)) {
    stop("La variable étoilée demandée n'est pas disponible dans ce corpus.")
  }
  groups <- normaliser_modalite_labbe(docvars[[variable]])

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
  if (!requireNamespace("ape", quietly = TRUE)) {
    stop("Le package R ape est nécessaire pour tracer l'arbre des distances.")
  }
  tree <- ape::as.phylo(clustering)
  text_count <- nrow(distance_matrix)

  grDevices::png(path, width = 1800, height = 1800, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mar = c(2, 2, 5, 2), xpd = NA)

  # Passage invisible : ape calcule les coordonnées de l'arbre non enraciné.
  ape::plot.phylo(
    tree,
    type = "unrooted",
    show.tip.label = FALSE,
    edge.color = grDevices::adjustcolor("#000000", alpha.f = 0),
    no.margin = FALSE
  )

  plot_environment <- get(".PlotPhyloEnv", envir = asNamespace("ape"))
  plot_state <- get("last_plot.phylo", envir = plot_environment)
  tip_x <- plot_state$xx[seq_len(text_count)]
  tip_y <- plot_state$yy[seq_len(text_count)]
  x_span <- diff(range(plot_state$xx, finite = TRUE))
  y_span <- diff(range(plot_state$yy, finite = TRUE))
  x_limits <- range(plot_state$xx, finite = TRUE) + c(-1, 1) * x_span * 0.28
  y_limits <- range(plot_state$yy, finite = TRUE) + c(-1, 1) * y_span * 0.22

  graphics::plot.new()
  graphics::plot.window(xlim = x_limits, ylim = y_limits, asp = 1)

  # Les branches terminales portent leur longueur Ward.D2 issue de la matrice de Labbé.
  for (edge_index in seq_len(nrow(tree$edge))) {
    parent <- tree$edge[edge_index, 1L]
    child <- tree$edge[edge_index, 2L]
    parent_x <- plot_state$xx[[parent]]
    parent_y <- plot_state$yy[[parent]]
    child_x <- plot_state$xx[[child]]
    child_y <- plot_state$yy[[child]]
    graphics::segments(
      parent_x, parent_y,
      child_x, child_y,
      col = "#1f252b",
      lwd = 1.35
    )
    if (child > text_count) next
    branch_label <- formatC(tree$edge.length[[edge_index]], format = "f", digits = 3)
    label_x <- (parent_x + child_x) / 2
    label_y <- (parent_y + child_y) / 2
    label_width <- graphics::strwidth(branch_label, cex = 0.58)
    label_height <- graphics::strheight(branch_label, cex = 0.58)
    graphics::rect(
      label_x - label_width * 0.62,
      label_y - label_height * 0.62,
      label_x + label_width * 0.62,
      label_y + label_height * 0.62,
      border = NA,
      col = grDevices::adjustcolor("white", alpha.f = 0.9)
    )
    graphics::text(label_x, label_y, labels = branch_label, cex = 0.58, col = "#374151")
  }
  center_x <- mean(range(plot_state$xx, finite = TRUE))
  label_cex <- max(0.58, min(0.9, 8 / max(text_count, 8)))
  label_positions <- ifelse(tip_x >= center_x, 4L, 2L)
  graphics::text(
    tip_x,
    tip_y,
    labels = gsub("_", " ", tree$tip.label, fixed = TRUE),
    pos = label_positions,
    offset = 0.45,
    cex = label_cex,
    col = "#217ce7",
    font = 1
  )
  graphics::title(main = "Arbre des distances intertextuelles de Labbé", cex.main = 1.15)
  graphics::mtext("Valeurs affichées : longueurs des branches terminales Ward.D2", side = 3, line = 0.4, cex = 0.72, col = "#5d6873")
  scale_length <- suppressWarnings(signif(max(tree$edge.length, na.rm = TRUE) / 4, 2))
  if (is.finite(scale_length) && scale_length > 0) {
    ape::add.scale.bar(
      x = x_limits[[1L]] + diff(x_limits) * 0.05,
      y = y_limits[[1L]] + diff(y_limits) * 0.04,
      length = scale_length,
      lwd = 1.2,
      lcol = "#1f252b",
      cex = 0.65
    )
  }
  invisible(clustering)
}

tracer_carte_labbe <- function(distance_matrix, path) {
  clustering <- stats::hclust(stats::as.dist(distance_matrix), method = "ward.D2")
  ordered_matrix <- distance_matrix[clustering$order, clustering$order, drop = FALSE]
  palette <- grDevices::colorRampPalette(c("#f7fbff", "#9ec9f7", "#217ce7", "#0b3972"))(100)
  value_range <- range(ordered_matrix, finite = TRUE)
  if (!all(is.finite(value_range)) || diff(value_range) <= 0) value_range <- c(0, 1)
  text_count <- nrow(ordered_matrix)
  axis_cex <- max(0.55, min(0.88, 8 / max(text_count, 8)))
  column_labels <- gsub("_", " ", colnames(ordered_matrix), fixed = TRUE)
  row_labels <- rev(gsub("_", " ", rownames(ordered_matrix), fixed = TRUE))

  grDevices::png(path, width = 1800, height = 1500, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)

  graphics::layout(matrix(c(1L, 2L), nrow = 1L), widths = c(5.6, 1))
  graphics::par(mar = c(11, 11, 5, 2))
  graphics::image(
    x = seq_len(text_count),
    y = seq_len(text_count),
    z = t(ordered_matrix[text_count:1L, , drop = FALSE]),
    col = palette,
    zlim = value_range,
    axes = FALSE,
    xlab = "",
    ylab = "",
    useRaster = TRUE
  )
  graphics::axis(1, at = seq_len(text_count), labels = column_labels, las = 2, cex.axis = axis_cex, tick = FALSE)
  graphics::axis(2, at = seq_len(text_count), labels = row_labels, las = 2, cex.axis = axis_cex, tick = FALSE)
  graphics::abline(v = seq(0.5, text_count + 0.5, by = 1), h = seq(0.5, text_count + 0.5, by = 1), col = grDevices::adjustcolor("white", alpha.f = 0.2), lwd = 0.7)
  graphics::box(col = "#d2d9e3")
  graphics::title(main = "Matrice des distances de Labbé", cex.main = 1.25)

  key_values <- seq(value_range[[1L]], value_range[[2L]], length.out = 100L)
  key_matrix <- outer(c(0, 1), key_values, function(x, y) y)
  graphics::par(mar = c(11, 1, 5, 5))
  graphics::image(
    x = c(0, 1),
    y = key_values,
    z = key_matrix,
    col = palette,
    zlim = value_range,
    axes = FALSE,
    xlab = "",
    ylab = "",
    useRaster = TRUE
  )
  legend_ticks <- pretty(value_range, n = 5)
  legend_ticks <- legend_ticks[legend_ticks >= value_range[[1L]] & legend_ticks <= value_range[[2L]]]
  graphics::axis(4, at = legend_ticks, labels = formatC(legend_ticks, format = "f", digits = 3), las = 1, cex.axis = 0.72)
  graphics::box(col = "#d2d9e3")
  graphics::mtext("Distance de Labbé", side = 4, line = 3, cex = 0.82)
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
    warnings = character(0),
    method = "Distance intertextuelle de Labbé sur la table lexicale construite à partir du corpus."
  )
  jsonlite::write_json(summary, file.path(output_dir, "resume_distance_labbe.json"), auto_unbox = TRUE, pretty = TRUE, null = "null")
  configuration <- list(
    variable = variable,
    variable_label = variable_label,
    min_effectif = as.integer(min_effectif),
    modalities = colnames(table),
    preprocessing = source$preprocessing %||% list(),
    formula = "somme des écarts absolus après réduction du grand texte, normalisée par les deux longueurs comparables",
    implementation = "Calcul compute.labbe du script officiel d'IRaMuTeQ ; matrice complétée symétriquement pour l'affichage."
  )
  jsonlite::write_json(configuration, file.path(output_dir, "configuration_distance_labbe.json"), auto_unbox = TRUE, pretty = TRUE, null = "null")
  list(summary = summary, matrix = matrix_distance, pairs = pairs)
}
