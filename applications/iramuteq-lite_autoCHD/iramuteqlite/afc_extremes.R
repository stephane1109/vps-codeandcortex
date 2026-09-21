# AFC secondaire : trois termes significatifs les plus éloignés de l'origine
# pour chaque classe. Ce rendu ne modifie ni la CHD ni l'AFC principale.

.extraire_xy_afc_extremes <- function(coords, axes = c(1, 2)) {
  if (is.null(coords)) return(NULL)
  values <- as.data.frame(coords, stringsAsFactors = FALSE)
  if (ncol(values) < max(axes) || !nrow(values)) return(NULL)
  data.frame(
    x = suppressWarnings(as.numeric(values[[axes[[1]]]])),
    y = suppressWarnings(as.numeric(values[[axes[[2]]]])),
    label = rownames(values),
    stringsAsFactors = FALSE
  )
}

selectionner_termes_extremes_afc <- function(afc_obj, stats_df, top_n = 3L, p_seuil = 0.05) {
  coords <- .extraire_xy_afc_extremes(afc_obj$colcoord)
  empty <- data.frame(classe = character(), terme = character(), x = numeric(), y = numeric(), distance_origine = numeric(), chi2 = numeric(), p_value = numeric(), stringsAsFactors = FALSE)
  if (is.null(coords) || !nrow(coords) || is.null(stats_df) || !is.data.frame(stats_df) || !nrow(stats_df)) return(empty)
  if (!"Terme" %in% names(stats_df)) return(empty)
  p_col <- if ("p_value" %in% names(stats_df)) "p_value" else if ("p" %in% names(stats_df)) "p" else NULL
  class_col <- if ("Classe_max" %in% names(stats_df)) "Classe_max" else if ("Classe" %in% names(stats_df)) "Classe" else NULL
  if (is.null(p_col) || is.null(class_col)) return(empty)

  rows <- data.frame(
    terme = as.character(stats_df$Terme),
    classe = as.character(stats_df[[class_col]]),
    p_value = suppressWarnings(as.numeric(stats_df[[p_col]])),
    chi2 = if ("chi2" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$chi2)) else NA_real_,
    stringsAsFactors = FALSE
  )
  rows <- rows[is.finite(rows$p_value) & rows$p_value <= p_seuil & nzchar(rows$terme), , drop = FALSE]
  if (!nrow(rows)) return(empty)
  index <- match(tolower(rows$terme), tolower(coords$label))
  rows$x <- coords$x[index]
  rows$y <- coords$y[index]
  rows <- rows[is.finite(rows$x) & is.finite(rows$y) & !is.na(index), , drop = FALSE]
  if (!nrow(rows)) return(empty)
  rows$distance_origine <- sqrt(rows$x^2 + rows$y^2)
  rows$classe <- ifelse(grepl("^classe", tolower(rows$classe)), rows$classe, paste("Classe", rows$classe))
  top_n <- max(1L, as.integer(top_n))
  selected <- lapply(split(rows, rows$classe), function(group) {
    group <- group[order(-group$distance_origine, -group$chi2, group$terme), , drop = FALSE]
    head(group, top_n)
  })
  result <- do.call(rbind, selected)
  rownames(result) <- NULL
  result[, c("classe", "terme", "x", "y", "distance_origine", "chi2", "p_value"), drop = FALSE]
}

tracer_afc_termes_extremes <- function(afc_obj, termes_df, axes = c(1, 2)) {
  classes <- .extraire_xy_afc_extremes(afc_obj$rowcoord, axes = axes)
  if (is.null(classes) || !nrow(classes)) stop("Coordonnées AFC des classes indisponibles.")
  all_x <- c(classes$x, termes_df$x)
  all_y <- c(classes$y, termes_df$y)
  all_x <- all_x[is.finite(all_x)]
  all_y <- all_y[is.finite(all_y)]
  lim_x <- range(all_x, finite = TRUE)
  lim_y <- range(all_y, finite = TRUE)
  marge_x <- max(0.1, diff(lim_x) * 0.12)
  marge_y <- max(0.1, diff(lim_y) * 0.12)
  palette <- c("#5b8c85", "#6f86b5", "#d77a57", "#9a78a8", "#c49a4a", "#4c8caa", "#bd6470", "#6b9b63")
  classes$classe <- classes$label
  color_by_class <- setNames(rep(palette, length.out = nrow(classes)), classes$classe)
  plot(classes$x, classes$y, type = "n", asp = 1, xlim = lim_x + c(-marge_x, marge_x), ylim = lim_y + c(-marge_y, marge_y), xlab = "Axe 1", ylab = "Axe 2", main = "AFC : trois termes significatifs les plus extrêmes par classe")
  abline(h = 0, v = 0, col = "#c9cdd1", lty = 1)
  points(classes$x, classes$y, pch = 21, bg = "#ffffff", col = "#1f2a33", lwd = 1.5, cex = 1.4)
  text(classes$x, classes$y, labels = classes$label, pos = 3, cex = 0.9, font = 2, col = "#1f2a33")
  if (nrow(termes_df)) {
    term_colors <- unname(color_by_class[termes_df$classe])
    term_colors[is.na(term_colors)] <- "#5b6570"
    points(termes_df$x, termes_df$y, pch = 16, col = term_colors, cex = 1.1)
    text(termes_df$x, termes_df$y, labels = termes_df$terme, pos = 4, offset = 0.35, cex = 0.85, col = term_colors)
  }
  legend("topright", legend = c("Classes", "Termes significatifs"), pch = c(21, 16), pt.bg = c("#ffffff", NA), col = c("#1f2a33", "#5b8c85"), bty = "n", cex = 0.85)
}
