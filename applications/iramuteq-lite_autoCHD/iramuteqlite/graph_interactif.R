# Donnees de la vue AFC interactive.
# Ce module ne recalcule ni la CHD ni l'AFC : il relit les exports AFC
# et prepare uniquement les coordonnees necessaires a l'affichage SVG.

construire_donnees_graph_interactif_afc <- function(
    coords_classes_file,
    coords_termes_file,
    stats_termes_file,
    seuil_p = 0.05,
    top_termes = 120L
) {
  lire_coordonnees <- function(path) {
    if (is.null(path) || !file.exists(path)) return(NULL)
    read.csv(path, row.names = 1, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
  }

  classes_df <- lire_coordonnees(coords_classes_file)
  termes_coord_df <- lire_coordonnees(coords_termes_file)
  if (is.null(classes_df) || is.null(termes_coord_df)) {
    stop("Exports de coordonnées AFC manquants pour le graphe interactif.")
  }

  extraire_xy <- function(df) {
    values <- as.data.frame(df, stringsAsFactors = FALSE)
    x <- suppressWarnings(as.numeric(values[[1]]))
    y <- if (ncol(values) >= 2) suppressWarnings(as.numeric(values[[2]])) else rep(0, nrow(values))
    data.frame(x = x, y = y, stringsAsFactors = FALSE, row.names = rownames(values))
  }

  classes_xy <- extraire_xy(classes_df)
  termes_xy <- extraire_xy(termes_coord_df)
  classes <- lapply(seq_len(nrow(classes_xy)), function(i) {
    list(
      label = rownames(classes_xy)[i],
      x = classes_xy$x[i],
      y = classes_xy$y[i]
    )
  })

  stats_df <- if (!is.null(stats_termes_file) && file.exists(stats_termes_file)) {
    read.csv(stats_termes_file, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "UTF-8")
  } else {
    data.frame()
  }

  termes <- list()
  if (nrow(stats_df) > 0 && "Terme" %in% names(stats_df)) {
    p_col <- if ("p_value" %in% names(stats_df)) "p_value" else if ("p" %in% names(stats_df)) "p" else NULL
    if (!is.null(p_col)) {
      p_values <- suppressWarnings(as.numeric(stats_df[[p_col]]))
      keep <- is.finite(p_values) & !is.na(p_values) & p_values <= seuil_p
      stats_df <- stats_df[keep, , drop = FALSE]
      stats_df$p_interactif <- p_values[keep]
    } else {
      stats_df <- stats_df[0, , drop = FALSE]
    }

    if (nrow(stats_df) > 0) {
      frequency <- if ("frequency" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$frequency)) else rep(0, nrow(stats_df))
      stats_df <- stats_df[order(-frequency, na.last = TRUE), , drop = FALSE]
      if (is.finite(top_termes) && nrow(stats_df) > top_termes) {
        stats_df <- stats_df[seq_len(top_termes), , drop = FALSE]
      }

      for (i in seq_len(nrow(stats_df))) {
        term <- as.character(stats_df$Terme[i])
        coord_index <- match(tolower(term), tolower(rownames(termes_xy)))
        if (is.na(coord_index)) next
        chi2 <- if ("chi2" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$chi2[i])) else NA_real_
        freq <- if ("frequency" %in% names(stats_df)) suppressWarnings(as.numeric(stats_df$frequency[i])) else NA_real_
        classe <- if ("Classe_max" %in% names(stats_df)) as.character(stats_df$Classe_max[i]) else ""
        termes[[length(termes) + 1L]] <- list(
          label = term,
          classe = classe,
          x = termes_xy$x[coord_index],
          y = termes_xy$y[coord_index],
          chi2 = chi2,
          p_value = stats_df$p_interactif[i],
          frequency = freq
        )
      }
    }
  }

  list(
    version = 1L,
    seuil_p = seuil_p,
    axes = list(x = "Axe 1", y = "Axe 2"),
    classes = classes,
    termes = termes
  )
}

ecrire_graph_interactif_afc <- function(
    coords_classes_file,
    coords_termes_file,
    stats_termes_file,
    output_file,
    seuil_p = 0.05,
    top_termes = 120L
) {
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Le package jsonlite est requis pour le graphe AFC interactif.")
  }
  payload <- construire_donnees_graph_interactif_afc(
    coords_classes_file = coords_classes_file,
    coords_termes_file = coords_termes_file,
    stats_termes_file = stats_termes_file,
    seuil_p = seuil_p,
    top_termes = top_termes
  )
  dir.create(dirname(output_file), recursive = TRUE, showWarnings = FALSE)
  jsonlite::write_json(payload, output_file, auto_unbox = TRUE, pretty = FALSE, na = "null")
  invisible(output_file)
}
