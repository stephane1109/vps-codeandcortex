if (!exists("%||%", mode = "function")) {
  `%||%` <- function(x, y) {
    if (is.null(x) || length(x) == 0) y else x
  }
}

arrondir_dataframe_numerique_sante <- function(df, digits = 6L) {
  if (is.null(df) || !is.data.frame(df) || !nrow(df)) {
    return(df)
  }

  sortie <- df
  colonnes_numeriques <- vapply(sortie, is.numeric, logical(1))
  if (!any(colonnes_numeriques)) {
    return(sortie)
  }

  for (nom_colonne in names(sortie)[colonnes_numeriques]) {
    sortie[[nom_colonne]] <- round(sortie[[nom_colonne]], digits = digits)
  }

  sortie
}

slugifier_nom_unite_sante <- function(value) {
  x <- trimws(as.character(value))
  if (!nzchar(x)) return("unite")
  x <- iconv(x, from = "", to = "ASCII//TRANSLIT")
  x[is.na(x)] <- "unite"
  x <- gsub("[^A-Za-z0-9]+", "_", x)
  x <- gsub("^_+|_+$", "", x)
  x <- tolower(x)
  if (!nzchar(x)) "unite" else x
}

formater_mode_comparaison_sante <- function(value) {
  x <- trimws(as.character(value %||% ""))
  x <- gsub("_", " ", x, fixed = TRUE)
  x_norm <- tolower(x)
  x_norm <- iconv(x_norm, from = "", to = "ASCII//TRANSLIT")
  x_norm[is.na(x_norm)] <- ""
  x_norm <- gsub("[^a-z0-9]+", " ", x_norm)
  x_norm <- trimws(gsub("\\s+", " ", x_norm))
  x_compact <- gsub("\\s+", "", x_norm)

  if (identical(x_norm, "premiere seance") || identical(x_compact, "premiereseance")) {
    return("Première séance")
  }
  if (identical(x_norm, "seance precedente") || identical(x_compact, "seanceprecedente")) {
    return("Séance précédente")
  }

  x
}

ajuster_positions_labels_sante <- function(values, lower, upper, min_gap) {
  valeurs_num <- suppressWarnings(as.numeric(values))
  n <- length(valeurs_num)
  if (!n) {
    return(numeric(0))
  }
  if (n == 1L || !all(is.finite(c(lower, upper, min_gap)))) {
    return(valeurs_num)
  }

  span <- upper - lower
  if (!is.finite(span) || span <= 0) {
    return(valeurs_num)
  }

  gap <- max(min_gap, 0)
  if (gap * (n - 1L) > span) {
    gap <- span / max(1, n - 1L)
  }

  ordre <- order(valeurs_num)
  ajustees <- valeurs_num[ordre]
  ajustees[1] <- max(ajustees[1], lower)

  if (n > 1L) {
    for (i in 2:n) {
      ajustees[i] <- max(ajustees[i], ajustees[i - 1L] + gap)
    }
  }

  depassement <- ajustees[n] - upper
  if (is.finite(depassement) && depassement > 0) {
    ajustees <- ajustees - depassement
  }

  if (n > 1L) {
    for (i in seq.int(n - 1L, 1L, by = -1L)) {
      ajustees[i] <- min(ajustees[i], ajustees[i + 1L] - gap)
    }
  }

  manque <- lower - ajustees[1]
  if (is.finite(manque) && manque > 0) {
    ajustees <- ajustees + manque
  }

  ajustees <- pmin(pmax(ajustees, lower), upper)
  sortie <- numeric(n)
  sortie[ordre] <- ajustees
  sortie
}

formater_valeur_relative_sante <- function(x, digits = 4L) {
  valeur <- suppressWarnings(as.numeric(x))
  if (!is.finite(valeur)) {
    return("")
  }
  if (identical(valeur, 0)) {
    return("0")
  }

  seuil <- 10^(-as.integer(digits))
  if (abs(valeur) < seuil) {
    return(formatC(valeur, format = "e", digits = 2))
  }

  formatC(valeur, format = "f", digits = digits)
}

normaliser_amplification_signal_sante <- function(value = 1) {
  x <- suppressWarnings(as.numeric(value))
  if (!length(x) || is.na(x) || !is.finite(x) || x <= 1) {
    return(1)
  }
  if (x >= 4) {
    return(4)
  }
  if (x >= 2) {
    return(2)
  }
  1
}

amplifier_signal_visuel_sante <- function(y_values, amplification_signal = 1, allow_negative = FALSE) {
  facteur <- normaliser_amplification_signal_sante(amplification_signal)
  valeurs <- suppressWarnings(as.numeric(y_values))
  if (facteur <= 1 || !length(valeurs) || !any(is.finite(valeurs))) {
    return(valeurs)
  }

  centre <- mean(valeurs, na.rm = TRUE)
  sortie <- centre + (valeurs - centre) * facteur
  sortie[!is.finite(sortie)] <- valeurs[!is.finite(sortie)]
  if (isTRUE(allow_negative)) sortie else pmax(sortie, 0)
}

tracer_courbe_suivi_sante <- function(x_labels,
                                      y_values,
                                      output_file,
                                      titre,
                                      ylab,
                                      couleur,
                                      ylim = NULL,
                                      amplification_signal = 1,
                                      allow_negative = FALSE) {
  if (!length(x_labels) || !length(y_values)) return(NULL)

  valeurs_affichees <- amplifier_signal_visuel_sante(
    y_values,
    amplification_signal = amplification_signal,
    allow_negative = allow_negative
  )
  facteur_affichage <- normaliser_amplification_signal_sante(amplification_signal)
  titre_affiche <- if (facteur_affichage > 1) {
    paste0(titre, " · signal amplifié ×", facteur_affichage)
  } else {
    titre
  }
  ylab_affiche <- if (facteur_affichage > 1) {
    paste0(ylab, " (affichage amplifié)")
  } else {
    ylab
  }

  if (is.null(ylim)) {
    y_range <- range(valeurs_affichees, na.rm = TRUE)
    if (!all(is.finite(y_range))) y_range <- c(0, 1)
    amplitude <- diff(y_range)
    marge <- if (is.finite(amplitude) && amplitude > 0) amplitude * 0.08 else 0.05
    ylim <- c(y_range[[1]] - marge, y_range[[2]] + marge)
  }

  grDevices::png(output_file, width = 1800, height = 1100, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(10, 5, 4, 2))
  x_pos <- seq_along(x_labels)
  y_ticks <- pretty(ylim, n = 5)
  y_ticks <- y_ticks[is.finite(y_ticks) & y_ticks >= ylim[[1]] & y_ticks <= ylim[[2]]]
  graphics::plot(
    x_pos,
    valeurs_affichees,
    type = "o",
    pch = 16,
    col = couleur,
    lwd = 2.4,
    xaxt = "n",
    yaxt = "n",
    xlab = "",
    ylab = ylab_affiche,
    main = titre_affiche,
    ylim = ylim
  )
  graphics::axis(1, at = x_pos, labels = x_labels, las = 2, cex.axis = 0.85)
  graphics::axis(2, at = y_ticks, labels = formatC(y_ticks, format = "f", digits = 4), las = 1, cex.axis = 0.9)
  graphics::grid(nx = NA, ny = NULL, col = "#dddddd", lty = "dotted")
}

tracer_barplot_empile_sante <- function(df,
                                        output_file,
                                        titre,
                                        ylab = "Proportion",
                                        palette = NULL) {
  if (is.null(df) || !is.data.frame(df) || !nrow(df) || !("Unite" %in% names(df))) {
    return(NULL)
  }

  value_cols <- setdiff(names(df), "Unite")
  if (!length(value_cols)) {
    return(NULL)
  }

  mat <- as.matrix(df[, value_cols, drop = FALSE])
  storage.mode(mat) <- "double"
  if (!nrow(mat) || !ncol(mat) || !any(is.finite(mat))) {
    return(NULL)
  }

  if (is.null(palette) || length(palette) < ncol(mat)) {
    palette <- grDevices::hcl.colors(max(3, ncol(mat)), palette = "Set 3")
  }

  grDevices::png(output_file, width = max(1800, 180 * nrow(mat)), height = 1200, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(12, 5, 4, 2))
  bp <- graphics::barplot(
    t(mat),
    beside = FALSE,
    col = palette[seq_len(ncol(mat))],
    border = NA,
    names.arg = df$Unite,
    las = 2,
    ylim = c(0, 1),
    ylab = ylab,
    main = titre
  )
  graphics::axis(2, at = pretty(c(0, 1), n = 5), labels = formatC(pretty(c(0, 1), n = 5), format = "f", digits = 4), las = 1, cex.axis = 0.9)
  graphics::grid(nx = NA, ny = NULL, col = "#dddddd", lty = "dotted")
  graphics::legend(
    "topright",
    legend = value_cols,
    fill = palette[seq_len(ncol(mat))],
    border = NA,
    bty = "n",
    cex = 0.9
  )
}

tracer_detection_ruptures_sante <- function(ruptures_df, output_file, amplification_signal = 1) {
  if (is.null(ruptures_df) || !is.data.frame(ruptures_df) || !nrow(ruptures_df)) {
    return(NULL)
  }

  y_values <- if ("Valeur_detection" %in% names(ruptures_df)) {
    suppressWarnings(as.numeric(ruptures_df$Valeur_detection))
  } else {
    suppressWarnings(as.numeric(ruptures_df$Divergence_Jensen_Shannon))
  }
  if (!length(y_values) || !any(is.finite(y_values))) {
    return(NULL)
  }
  autoriser_negatif <- FALSE
  valeurs_affichees <- amplifier_signal_visuel_sante(
    y_values,
    amplification_signal = amplification_signal,
    allow_negative = autoriser_negatif
  )
  facteur_affichage <- normaliser_amplification_signal_sante(amplification_signal)
  titre_affiche <- if (facteur_affichage > 1) {
    paste0(
      "Détection explicite des ruptures discursives",
      " · signal amplifié ×",
      facteur_affichage
    )
  } else {
    "Détection explicite des ruptures discursives"
  }

  labels_x <- paste(ruptures_df$Unite_depart, "→", ruptures_df$Unite_arrivee)
  rupture_detectee <- tolower(trimws(as.character(ruptures_df$Rupture_detectee %||% ""))) == "oui"
  score_z <- suppressWarnings(as.numeric(ruptures_df$Score_standardise))
  seuil_affiche <- if (length(score_z) >= 3L && any(is.finite(score_z))) {
    base::mean(y_values, na.rm = TRUE) + stats::sd(y_values, na.rm = TRUE)
  } else {
    NA_real_
  }

  y_range <- range(valeurs_affichees, na.rm = TRUE)
  amplitude <- diff(y_range)
  marge <- if (is.finite(amplitude) && amplitude > 0) amplitude * 0.12 else 0.05
  ylim <- if (autoriser_negatif) {
    c(y_range[[1]] - marge, y_range[[2]] + marge)
  } else {
    c(max(0, y_range[[1]] - marge), y_range[[2]] + marge)
  }

  grDevices::png(output_file, width = 2000, height = 1150, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(10, 5, 4, 2))
  x_pos <- seq_along(y_values)
  graphics::plot(
    x_pos,
    valeurs_affichees,
    type = "o",
    pch = 16,
    col = "#5f3dc4",
    lwd = 2.6,
    xaxt = "n",
    yaxt = "n",
    xlab = "",
    ylab = if (facteur_affichage > 1) "Divergence de Jensen-Shannon (affichage amplifié)" else "Divergence de Jensen-Shannon",
    main = titre_affiche,
    ylim = ylim
  )
  graphics::axis(1, at = x_pos, labels = labels_x, las = 2, cex.axis = 0.85)
  y_ticks <- pretty(ylim, n = 5)
  y_ticks <- y_ticks[is.finite(y_ticks) & y_ticks >= ylim[[1]] & y_ticks <= ylim[[2]]]
  graphics::axis(2, at = y_ticks, labels = formatC(y_ticks, format = "f", digits = 4), las = 1, cex.axis = 0.9)
  graphics::grid(nx = NA, ny = NULL, col = "#dddddd", lty = "dotted")

  if (is.finite(seuil_affiche)) {
    seuil_affiche_plot <- amplifier_signal_visuel_sante(
      seuil_affiche,
      amplification_signal = amplification_signal,
      allow_negative = autoriser_negatif
    )
    graphics::abline(h = seuil_affiche_plot, col = "#c92a2a", lty = 2, lwd = 1.6)
    graphics::text(
      x = max(1, length(x_pos) - 0.2),
      y = seuil_affiche_plot,
      labels = "Seuil indicatif",
      pos = 3,
      cex = 0.8,
      col = "#c92a2a",
      xpd = TRUE
    )
  }

  if (any(rupture_detectee)) {
    graphics::points(x_pos[rupture_detectee], valeurs_affichees[rupture_detectee], pch = 19, cex = 1.2, col = "#c92a2a")
    graphics::text(
      x = x_pos[rupture_detectee],
      y = valeurs_affichees[rupture_detectee],
      labels = "rupture",
      pos = 3,
      cex = 0.8,
      col = "#c92a2a"
    )
  }
}

tracer_heatmap_divergence_jensen_shannon_sante <- function(jsd_mat, output_file, variable_label) {
  if (is.null(jsd_mat) || !is.matrix(jsd_mat) || !nrow(jsd_mat)) {
    return(NULL)
  }

  display_mat <- jsd_mat[nrow(jsd_mat):1, , drop = FALSE]
  palette <- grDevices::colorRampPalette(c("#f8f9fa", "#ffe8cc", "#ff922b", "#d9480f", "#7f2704"))(120)
  n_cols <- ncol(display_mat)
  n_rows <- nrow(display_mat)
  max_dim <- max(n_cols, n_rows)
  plot_width <- min(5600, max(1900, 110 * n_cols))
  plot_height <- min(5600, max(1500, 110 * n_rows))
  axis_cex <- if (max_dim <= 12) {
    0.92
  } else if (max_dim <= 20) {
    0.82
  } else if (max_dim <= 30) {
    0.72
  } else {
    0.62
  }
  cell_cex <- if (max_dim <= 12) {
    0.78
  } else if (max_dim <= 20) {
    0.7
  } else if (max_dim <= 30) {
    0.6
  } else {
    0.52
  }

  grDevices::png(output_file, width = plot_width, height = plot_height, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(10, 10, 5, 2))
  graphics::image(
    x = seq_len(ncol(display_mat)),
    y = seq_len(nrow(display_mat)),
    z = t(display_mat),
    col = palette,
    zlim = c(0, 1),
    xaxt = "n",
    yaxt = "n",
    xlab = variable_label,
    ylab = variable_label,
    main = "Matrice de divergence de Jensen-Shannon"
  )
  graphics::axis(1, at = seq_len(ncol(display_mat)), labels = colnames(display_mat), las = 2, cex.axis = axis_cex)
  graphics::axis(2, at = seq_len(nrow(display_mat)), labels = rev(rownames(jsd_mat)), las = 2, cex.axis = axis_cex)
  graphics::box()

  for (row in seq_len(nrow(display_mat))) {
    for (col in seq_len(ncol(display_mat))) {
      value <- round(display_mat[row, col], 4)
      text_col <- if (is.finite(value) && value >= 0.45) "white" else "#1f1f1f"
      graphics::text(col, row, labels = format(value, nsmall = 4), cex = cell_cex, col = text_col)
    }
  }
}

generer_wordclouds_suivi_sante <- function(grouped_mat, unites_ordonnees, wordcloud_dir, top_n_terms = 20L) {
  dir.create(wordcloud_dir, recursive = TRUE, showWarnings = FALSE)
  top_n_wc <- max(20L, as.integer(top_n_terms %||% 20L) * 3L)
  wordcloud_files <- character(0)

  for (unit in unites_ordonnees) {
    freq <- grouped_mat[unit, ]
    freq <- freq[freq > 0]
    if (!length(freq)) next
    freq <- sort(freq, decreasing = TRUE)
    keep <- utils::head(freq, top_n_wc)
    words <- names(keep)
    weights <- as.numeric(keep)
    if (!length(words) || !length(weights)) next

    out_file <- file.path(wordcloud_dir, paste0(slugifier_nom_unite_sante(unit), "_wordcloud.png"))
    try({
      grDevices::png(out_file, width = 1200, height = 900, res = 150)
      suppressWarnings(wordcloud::wordcloud(
        words = words,
        freq = weights,
        scale = c(6, 0.8),
        min.freq = 0,
        random.order = FALSE,
        rot.per = 0.08,
        max.words = length(words),
        colors = grDevices::hcl.colors(8, "Dark 3")
      ))
      grDevices::dev.off()
      wordcloud_files <- c(wordcloud_files, out_file)
    }, silent = TRUE)
  }

  wordcloud_files
}

tracer_frise_emergences_jsd_sante <- function(terms_df,
                                              output_file,
                                              titre,
                                              top_n_terms = 20L) {
  if (is.null(terms_df) || !nrow(terms_df)) {
    return(NULL)
  }

  colonnes_requises <- c("Mode_comparaison", "Unite_depart", "Unite_arrivee", "Terme", "Type_evolution", "Difference_relative")
  if (!all(colonnes_requises %in% names(terms_df))) {
    return(NULL)
  }

  normaliser_type <- function(x) {
    valeur <- tolower(trimws(as.character(x %||% "")))
    if (valeur %in% c("nouveau", "hausse", "baisse", "disparu")) {
      return(valeur)
    }
    NA_character_
  }

  transitions_ordre <- unique(
    paste(
      as.character(terms_df$Unite_depart),
      "→",
      as.character(terms_df$Unite_arrivee)
    )
  )

  plot_df <- data.frame(
    Transition = paste(as.character(terms_df$Unite_depart), "→", as.character(terms_df$Unite_arrivee)),
    Terme = trimws(as.character(terms_df$Terme)),
    Type_evolution = vapply(terms_df$Type_evolution, normaliser_type, character(1)),
    Difference_relative = suppressWarnings(as.numeric(terms_df$Difference_relative)),
    stringsAsFactors = FALSE
  )

  plot_df <- plot_df[
    nzchar(plot_df$Terme) &
      nzchar(plot_df$Transition) &
      !is.na(plot_df$Type_evolution) &
      is.finite(plot_df$Difference_relative),
    ,
    drop = FALSE
  ]
  if (!nrow(plot_df)) {
    return(NULL)
  }

  plot_df$Amplitude <- abs(plot_df$Difference_relative)
  plot_df <- plot_df[order(plot_df$Amplitude, decreasing = TRUE), , drop = FALSE]
  plot_df <- plot_df[!duplicated(paste(plot_df$Transition, plot_df$Terme, sep = "|||")), , drop = FALSE]
  if (!nrow(plot_df)) {
    return(NULL)
  }

  transitions <- transitions_ordre[transitions_ordre %in% plot_df$Transition]
  if (!length(transitions)) {
    transitions <- unique(plot_df$Transition)
  }

  importance_termes <- stats::aggregate(Amplitude ~ Terme, data = plot_df, FUN = sum)
  importance_termes <- importance_termes[order(importance_termes$Amplitude, decreasing = TRUE), , drop = FALSE]
  termes_retenus <- utils::head(as.character(importance_termes$Terme), max(4L, as.integer(top_n_terms %||% 20L)))
  plot_df <- plot_df[plot_df$Terme %in% termes_retenus, , drop = FALSE]
  if (!nrow(plot_df)) {
    return(NULL)
  }
  termes_ordonnes <- importance_termes$Terme[importance_termes$Terme %in% termes_retenus]
  termes_ordonnes <- termes_ordonnes[!duplicated(termes_ordonnes)]
  termes_affiches <- rev(as.character(termes_ordonnes))

  nb_transitions <- length(transitions)
  nb_termes <- length(termes_affiches)
  if (nb_transitions < 1L || nb_termes < 1L) {
    return(NULL)
  }

  couleurs_types <- c(
    nouveau = "#0b7285",
    hausse = "#2b8a3e",
    baisse = "#e67700",
    disparu = "#c92a2a"
  )

  x_pos <- match(plot_df$Transition, transitions)
  y_pos <- match(plot_df$Terme, termes_affiches)
  amplitude_max <- max(plot_df$Amplitude, na.rm = TRUE)
  if (!is.finite(amplitude_max) || amplitude_max <= 0) {
    amplitude_max <- 1
  }
  cex_points <- 0.9 + 1.6 * (plot_df$Amplitude / amplitude_max)

  largeur_png <- max(2600, 420 * nb_transitions)
  hauteur_png <- max(1500, 88 * nb_termes + 420)

  grDevices::png(output_file, width = largeur_png, height = hauteur_png, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(12, 22, 7, 4))
  graphics::plot(
    NA,
    NA,
    xlim = c(0.5, nb_transitions + 0.5),
    ylim = c(0.5, nb_termes + 0.5),
    xaxt = "n",
    yaxt = "n",
    xlab = "",
    ylab = "",
    main = titre
  )

  for (i in seq_len(nb_transitions)) {
    if (i %% 2L == 1L) {
      graphics::rect(i - 0.5, 0.5, i + 0.5, nb_termes + 0.5, col = "#f8f9fa", border = NA)
    }
  }
  graphics::grid(nx = NULL, ny = NA, col = "#dddddd", lty = "dotted")
  graphics::axis(1, at = seq_len(nb_transitions), labels = transitions, las = 2, cex.axis = 1.05)
  graphics::axis(2, at = seq_len(nb_termes), labels = termes_affiches, las = 2, cex.axis = 1.02)

  graphics::mtext("Transitions entre entretiens", side = 1, line = 9.7, cex = 1.05)
  graphics::mtext("Termes les plus changeants", side = 2, line = 17.2, cex = 1.05)

  for (i in seq_len(nrow(plot_df))) {
    couleur <- couleurs_types[[plot_df$Type_evolution[[i]]]] %||% "#495057"
    graphics::points(
      x_pos[[i]],
      y_pos[[i]],
      pch = 15,
      cex = cex_points[[i]],
      col = couleur
    )
  }

  graphics::legend(
    "topright",
    inset = c(0.01, 0.01),
    legend = c("Nouveaux", "Hausse", "Baisse", "Disparus"),
    col = c(couleurs_types[["nouveau"]], couleurs_types[["hausse"]], couleurs_types[["baisse"]], couleurs_types[["disparu"]]),
    pch = 15,
    pt.cex = 1.4,
    bty = "n",
    cex = 1,
    title = "Type d'évolution"
  )
}

generer_frises_emergences_suivi_sante <- function(terms_df, frise_dir, top_n_terms = 20L) {
  dir.create(frise_dir, recursive = TRUE, showWarnings = FALSE)

  if (is.null(terms_df) || !nrow(terms_df) || !"Mode_comparaison" %in% names(terms_df)) {
    return(character(0))
  }

  modes <- unique(trimws(as.character(terms_df$Mode_comparaison)))
  modes <- modes[nzchar(modes)]
  if (!length(modes)) {
    return(character(0))
  }

  frise_files <- character(0)

  for (mode_comparaison in modes) {
    mode_df <- terms_df[trimws(as.character(terms_df$Mode_comparaison)) == mode_comparaison, , drop = FALSE]
    if (!nrow(mode_df)) next

    out_file <- file.path(
      frise_dir,
      paste0(
        "frise_emergences__",
        slugifier_nom_unite_sante(mode_comparaison),
        ".png"
      )
    )

    titre <- paste0(
      "Frise des émergences - ",
      formater_mode_comparaison_sante(mode_comparaison)
    )

    tracer_frise_emergences_jsd_sante(
      terms_df = mode_df,
      output_file = out_file,
      titre = titre,
      top_n_terms = top_n_terms
    )
    if (file.exists(out_file)) {
      frise_files <- c(frise_files, out_file)
    }
  }

  frise_files
}

tracer_barres_divergentes_termes_jsd_sante <- function(terms_df,
                                                       output_file,
                                                       titre,
                                                       unite_depart,
                                                       unite_arrivee) {
  if (is.null(terms_df) || !nrow(terms_df)) {
    return(NULL)
  }

  values_diff <- suppressWarnings(as.numeric(terms_df$Difference_relative))
  terms <- as.character(terms_df$Terme)
  types <- as.character(terms_df$Type_evolution)

  idx_valides <- which(
    nzchar(terms) &
      is.finite(values_diff) &
      abs(values_diff) > 0
  )
  if (!length(idx_valides)) {
    return(NULL)
  }

  plot_df <- data.frame(
    Terme = terms[idx_valides],
    Type_evolution = types[idx_valides],
    Difference_relative = values_diff[idx_valides],
    stringsAsFactors = FALSE
  )
  plot_df <- plot_df[!duplicated(plot_df$Terme), , drop = FALSE]
  if (!nrow(plot_df)) {
    return(NULL)
  }

  plot_df$Direction <- ifelse(plot_df$Difference_relative >= 0, "positif", "negatif")
  neg_df <- plot_df[plot_df$Direction == "negatif", , drop = FALSE]
  pos_df <- plot_df[plot_df$Direction == "positif", , drop = FALSE]

  if (nrow(neg_df)) {
    neg_df <- neg_df[order(neg_df$Difference_relative), , drop = FALSE]
  }
  if (nrow(pos_df)) {
    pos_df <- pos_df[order(pos_df$Difference_relative), , drop = FALSE]
  }

  plot_df <- rbind(neg_df, pos_df)
  if (!nrow(plot_df)) {
    return(NULL)
  }

  colorier_barre <- function(type_evolution) {
    type_chr <- tolower(trimws(as.character(type_evolution)))
    if (type_chr %in% c("hausse", "nouveau")) return("#2b8a3e")
    if (type_chr %in% c("baisse", "disparu")) return("#c92a2a")
    "#495057"
  }

  couleurs <- vapply(plot_df$Type_evolution, colorier_barre, character(1))
  x_min <- min(plot_df$Difference_relative, na.rm = TRUE)
  x_max <- max(plot_df$Difference_relative, na.rm = TRUE)
  amplitude <- max(abs(c(x_min, x_max)), na.rm = TRUE)
  marge <- if (is.finite(amplitude) && amplitude > 0) amplitude * 0.15 else 0.01
  x_lim <- c(-amplitude - marge, amplitude + marge)

  grDevices::png(output_file, width = 1900, height = 1400, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(6, 14, 7, 4))
  y_pos <- seq_len(nrow(plot_df))
  graphics::plot(
    NA,
    NA,
    xlim = x_lim,
    ylim = c(0.5, nrow(plot_df) + 0.5),
    xaxt = "n",
    yaxt = "n",
    xlab = "Différence relative",
    ylab = "",
    main = titre
  )
  graphics::grid(nx = NULL, ny = NA, col = "#dddddd", lty = "dotted")
  graphics::abline(v = 0, col = "#1f1f1f", lwd = 1.2)
  x_ticks <- pretty(x_lim, n = 6)
  x_ticks <- x_ticks[is.finite(x_ticks) & x_ticks >= x_lim[[1]] & x_ticks <= x_lim[[2]]]
  graphics::axis(1, at = x_ticks, labels = formatC(x_ticks, format = "f", digits = 4), cex.axis = 0.88)

  for (i in seq_len(nrow(plot_df))) {
    value <- plot_df$Difference_relative[[i]]
    couleur <- couleurs[[i]]
    graphics::segments(0, y_pos[[i]], value, y_pos[[i]], lwd = 8, col = couleur)
  }

  graphics::axis(2, at = y_pos, labels = plot_df$Terme, las = 2, cex.axis = 0.9)

  etiquettes <- ifelse(
    plot_df$Difference_relative >= 0,
    paste0("+", formatC(plot_df$Difference_relative, format = "f", digits = 4)),
    formatC(plot_df$Difference_relative, format = "f", digits = 4)
  )
  for (i in seq_len(nrow(plot_df))) {
    pos_label <- if (plot_df$Difference_relative[[i]] >= 0) 4 else 2
    offset <- if (plot_df$Difference_relative[[i]] >= 0) 0.02 else -0.02
    graphics::text(
      plot_df$Difference_relative[[i]] + offset * diff(x_lim),
      y_pos[[i]],
      labels = etiquettes[[i]],
      pos = pos_label,
      cex = 0.82,
      col = couleurs[[i]],
      xpd = TRUE
    )
  }

  graphics::mtext(
    paste0(unite_depart, "  |  ", unite_arrivee),
    side = 3,
    line = 0.6,
    cex = 0.92,
    col = "#495057"
  )
}

generer_barres_divergentes_suivi_sante <- function(terms_df, divergent_dir, top_n_terms = 20L) {
  dir.create(divergent_dir, recursive = TRUE, showWarnings = FALSE)

  if (is.null(terms_df) || !nrow(terms_df)) {
    return(character(0))
  }

  colonnes_requises <- c("Mode_comparaison", "Unite_depart", "Unite_arrivee", "Terme", "Difference_relative")
  if (!all(colonnes_requises %in% names(terms_df))) {
    return(character(0))
  }

  combinaisons <- unique(terms_df[, c("Mode_comparaison", "Unite_depart", "Unite_arrivee"), drop = FALSE])
  divergent_files <- character(0)

  for (i in seq_len(nrow(combinaisons))) {
    mode_comparaison <- as.character(combinaisons$Mode_comparaison[[i]])
    unite_depart <- as.character(combinaisons$Unite_depart[[i]])
    unite_arrivee <- as.character(combinaisons$Unite_arrivee[[i]])

    plot_df <- subset(
      terms_df,
      Mode_comparaison == mode_comparaison &
        Unite_depart == unite_depart &
        Unite_arrivee == unite_arrivee
    )
    if (!nrow(plot_df)) next

    diff_values <- suppressWarnings(as.numeric(plot_df$Difference_relative))
    plot_df <- plot_df[is.finite(diff_values), , drop = FALSE]
    diff_values <- suppressWarnings(as.numeric(plot_df$Difference_relative))

    neg_df <- plot_df[diff_values < 0, , drop = FALSE]
    pos_df <- plot_df[diff_values > 0, , drop = FALSE]

    if (nrow(neg_df)) {
      neg_df <- neg_df[order(suppressWarnings(as.numeric(neg_df$Difference_relative))), , drop = FALSE]
      neg_df <- utils::tail(neg_df, max(1L, as.integer(top_n_terms %||% 20L)))
    }
    if (nrow(pos_df)) {
      pos_df <- pos_df[order(suppressWarnings(as.numeric(pos_df$Difference_relative)), decreasing = TRUE), , drop = FALSE]
      pos_df <- utils::head(pos_df, max(1L, as.integer(top_n_terms %||% 20L)))
    }

    plot_df <- rbind(neg_df, pos_df)
    if (!nrow(plot_df)) next

    out_file <- file.path(
      divergent_dir,
      paste0(
        "barres_divergentes__",
        slugifier_nom_unite_sante(mode_comparaison),
        "__",
        slugifier_nom_unite_sante(unite_depart),
        "__vers__",
        slugifier_nom_unite_sante(unite_arrivee),
        ".png"
      )
    )

    titre <- paste0(
      "Barres divergentes - ",
      formater_mode_comparaison_sante(mode_comparaison),
      " - ",
      unite_depart,
      " -> ",
      unite_arrivee
    )

    tracer_barres_divergentes_termes_jsd_sante(
      terms_df = plot_df,
      output_file = out_file,
      titre = titre,
      unite_depart = unite_depart,
      unite_arrivee = unite_arrivee
    )
    if (file.exists(out_file)) {
      divergent_files <- c(divergent_files, out_file)
    }
  }

  divergent_files
}

tracer_waterfall_contributions_jsd_sante <- function(contributions_df,
                                                     output_file,
                                                     titre,
                                                     unite_depart,
                                                     unite_arrivee) {
  if (is.null(contributions_df) || !nrow(contributions_df)) {
    return(NULL)
  }

  contributions <- suppressWarnings(as.numeric(contributions_df$Contribution_Jensen_Shannon))
  termes <- as.character(contributions_df$Terme)

  idx_valides <- which(
    nzchar(termes) &
      is.finite(contributions) &
      contributions > 0
  )
  if (!length(idx_valides)) {
    return(NULL)
  }

  plot_df <- data.frame(
    Terme = termes[idx_valides],
    Contribution_Jensen_Shannon = contributions[idx_valides],
    stringsAsFactors = FALSE
  )
  plot_df <- plot_df[order(plot_df$Contribution_Jensen_Shannon, decreasing = TRUE), , drop = FALSE]
  plot_df <- plot_df[!duplicated(plot_df$Terme), , drop = FALSE]
  if (!nrow(plot_df)) {
    return(NULL)
  }

  plot_df$Cumul_avant <- c(0, cumsum(plot_df$Contribution_Jensen_Shannon[-nrow(plot_df)]))
  plot_df$Cumul_apres <- cumsum(plot_df$Contribution_Jensen_Shannon)
  total_jsd <- sum(plot_df$Contribution_Jensen_Shannon)

  labels_x <- c(plot_df$Terme, "Total")
  y_max <- max(c(plot_df$Cumul_apres, total_jsd), na.rm = TRUE)
  y_lim <- c(0, y_max * 1.18)
  if (!is.finite(y_lim[[2]]) || y_lim[[2]] <= 0) {
    y_lim[[2]] <- 0.05
  }

  grDevices::png(output_file, width = 2000, height = 1300, res = 180)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({
    graphics::par(old_par)
    grDevices::dev.off()
  }, add = TRUE)

  graphics::par(mar = c(12, 6, 6, 3))
  x_positions <- seq_along(labels_x)
  graphics::plot(
    NA,
    NA,
    xlim = c(0.4, length(labels_x) + 0.6),
    ylim = y_lim,
    xaxt = "n",
    yaxt = "n",
    xlab = "",
    ylab = "Contribution à la divergence de Jensen-Shannon",
    main = titre
  )
  graphics::axis(1, at = x_positions, labels = labels_x, las = 2, cex.axis = 0.82)
  y_ticks <- pretty(y_lim, n = 6)
  y_ticks <- y_ticks[is.finite(y_ticks) & y_ticks >= y_lim[[1]] & y_ticks <= y_lim[[2]]]
  graphics::axis(2, at = y_ticks, labels = formatC(y_ticks, format = "f", digits = 4), las = 1, cex.axis = 0.88)
  graphics::grid(nx = NA, ny = NULL, col = "#dddddd", lty = "dotted")

  for (i in seq_len(nrow(plot_df))) {
    x <- x_positions[[i]]
    y0 <- plot_df$Cumul_avant[[i]]
    y1 <- plot_df$Cumul_apres[[i]]
    graphics::rect(x - 0.34, y0, x + 0.34, y1, col = "#1971c2", border = "#0b4f8a", lwd = 1.2)
    graphics::text(
      x,
      y1 + diff(y_lim) * 0.018,
      labels = formatC(plot_df$Contribution_Jensen_Shannon[[i]], format = "f", digits = 4),
      cex = 0.72,
      col = "#0b4f8a",
      xpd = TRUE
    )
  }

  total_x <- x_positions[[length(x_positions)]]
  graphics::rect(total_x - 0.34, 0, total_x + 0.34, total_jsd, col = "#ff922b", border = "#d9480f", lwd = 1.4)
  graphics::segments(0.7, total_jsd, total_x - 0.34, total_jsd, lty = "dashed", lwd = 1.2, col = "#d9480f")
  graphics::text(
    total_x,
    total_jsd + diff(y_lim) * 0.022,
    labels = paste0("Total = ", formatC(total_jsd, format = "f", digits = 4)),
    cex = 0.8,
    col = "#d9480f",
    font = 2,
    xpd = TRUE
  )

  graphics::mtext(
    paste0("Lecture : chaque barre ajoute la contribution d'un terme à l'écart ", unite_depart, " -> ", unite_arrivee, "."),
    side = 3,
    line = 0.8,
    cex = 0.82,
    col = "#495057"
  )
}

generer_waterfalls_contributions_suivi_sante <- function(contributions_df,
                                                         waterfall_dir,
                                                         top_n_terms = 20L) {
  dir.create(waterfall_dir, recursive = TRUE, showWarnings = FALSE)

  if (is.null(contributions_df) || !nrow(contributions_df)) {
    return(character(0))
  }

  colonnes_requises <- c("Mode_comparaison", "Unite_depart", "Unite_arrivee", "Terme", "Contribution_Jensen_Shannon")
  if (!all(colonnes_requises %in% names(contributions_df))) {
    return(character(0))
  }

  combinaisons <- unique(contributions_df[, c("Mode_comparaison", "Unite_depart", "Unite_arrivee"), drop = FALSE])
  waterfall_files <- character(0)

  for (i in seq_len(nrow(combinaisons))) {
    mode_comparaison <- as.character(combinaisons$Mode_comparaison[[i]])
    unite_depart <- as.character(combinaisons$Unite_depart[[i]])
    unite_arrivee <- as.character(combinaisons$Unite_arrivee[[i]])

    plot_df <- subset(
      contributions_df,
      Mode_comparaison == mode_comparaison &
        Unite_depart == unite_depart &
        Unite_arrivee == unite_arrivee
    )
    if (!nrow(plot_df)) next

    plot_df <- plot_df[order(
      suppressWarnings(as.numeric(plot_df$Contribution_Jensen_Shannon)),
      decreasing = TRUE
    ), , drop = FALSE]
    plot_df <- utils::head(plot_df, max(4L, as.integer(top_n_terms %||% 20L)))
    if (!nrow(plot_df)) next

    out_file <- file.path(
      waterfall_dir,
      paste0(
        "waterfall__",
        slugifier_nom_unite_sante(mode_comparaison),
        "__",
        slugifier_nom_unite_sante(unite_depart),
        "__vers__",
        slugifier_nom_unite_sante(unite_arrivee),
        ".png"
      )
    )

    titre <- paste0(
      "Waterfall des contributions - ",
      formater_mode_comparaison_sante(mode_comparaison),
      " - ",
      unite_depart,
      " -> ",
      unite_arrivee
    )

    tracer_waterfall_contributions_jsd_sante(
      contributions_df = plot_df,
      output_file = out_file,
      titre = titre,
      unite_depart = unite_depart,
      unite_arrivee = unite_arrivee
    )
    if (file.exists(out_file)) {
      waterfall_files <- c(waterfall_files, out_file)
    }
  }

  waterfall_files
}

detecter_segments_contenant_terme_jsd_sante <- function(textes, terme) {
  textes_chr <- as.character(textes)
  terme_chr <- trimws(as.character(terme))
  if (!length(textes_chr) || !nzchar(terme_chr)) {
    return(rep(FALSE, length(textes_chr)))
  }

  if (exists("detecter_segments_contenant_termes_unicode", mode = "function")) {
    return(detecter_segments_contenant_termes_unicode(textes_chr, terme_chr))
  }

  terme_escaped <- gsub("([.|()\\^{}+$*?]|\\[|\\]|\\\\)", "\\\\\\1", terme_chr)
  motif <- paste0("(^|[^[:alnum:]_])", terme_escaped, "($|[^[:alnum:]_])")
  grepl(motif, textes_chr, perl = TRUE, ignore.case = TRUE)
}

detecter_segments_contenant_plusieurs_termes_jsd_sante <- function(textes, termes) {
  termes_chr <- unique(trimws(as.character(termes %||% character(0))))
  termes_chr <- termes_chr[nzchar(termes_chr)]
  if (!length(termes_chr)) {
    return(rep(FALSE, length(as.character(textes))))
  }

  Reduce(`|`, lapply(termes_chr, function(terme) {
    detecter_segments_contenant_terme_jsd_sante(textes, terme)
  }))
}

construire_segments_lexicaux_jsd_sante <- function(tok_ok, dfm_ok) {
  if (is.null(tok_ok) || is.null(dfm_ok)) {
    return(NULL)
  }

  featnames_finales <- quanteda::featnames(dfm_ok)
  if (!length(featnames_finales)) {
    return(NULL)
  }

  tok_filtre <- quanteda::tokens_select(
    tok_ok,
    pattern = featnames_finales,
    selection = "keep",
    valuetype = "fixed",
    case_insensitive = FALSE,
    padding = FALSE
  )

  segments <- vapply(
    as.list(tok_filtre),
    function(x) paste(as.character(x), collapse = " "),
    FUN.VALUE = character(1)
  )
  names(segments) <- as.character(quanteda::docnames(tok_filtre))
  segments
}

preparer_terme_concordancier_jsd_sante <- function(terme, unite_lexicale = "unigramme") {
  terme_chr <- trimws(as.character(terme %||% ""))
  if (!nzchar(terme_chr)) {
    return("")
  }

  if (identical(normaliser_unite_lexicale_sante(unite_lexicale), "bigramme")) {
    return(gsub("_", " ", terme_chr, fixed = TRUE))
  }

  terme_chr
}

generer_concordancier_jsd_sante <- function(filtered_corpus_ok,
                                            dfm_ok = NULL,
                                            tok_ok = NULL,
                                            variable_suivi,
                                            contributions_df,
                                            unite_lexicale = "unigramme",
                                            couche_analyse = "lexicale_brute",
                                            lexique_emotionnel = "feel",
                                            output_file) {
  if (is.null(filtered_corpus_ok) || is.null(contributions_df) || !nrow(contributions_df)) {
    return(NULL)
  }

  dv <- tryCatch(
    as.data.frame(quanteda::docvars(filtered_corpus_ok), stringsAsFactors = FALSE),
    error = function(e) NULL
  )
  if (is.null(dv) || !is.data.frame(dv) || !variable_suivi %in% names(dv)) {
    return(NULL)
  }

  unite_lexicale_resolue <- normaliser_unite_lexicale_sante(unite_lexicale)
  couche_analyse_resolue <- normaliser_couche_analyse_sante(couche_analyse)
  textes_source <- as.character(filtered_corpus_ok)
  segments_lexicaux <- construire_segments_lexicaux_jsd_sante(tok_ok = tok_ok, dfm_ok = dfm_ok)
  unites <- trimws(as.character(dv[[variable_suivi]]))
  unites[is.na(unites)] <- ""
  lexique_emotionnel_df <- NULL

  if (identical(couche_analyse_resolue, "emotionnelle")) {
    lexique_info <- charger_lexique_emotionnel_sante(
      source = lexique_emotionnel,
      repo_root = obtenir_repo_root_sante()
    )
    lexique_emotionnel_df <- lexique_info$data
  }

  demandes <- unique(
    contributions_df[, c("Mode_comparaison", "Unite_depart", "Unite_arrivee", "Terme"), drop = FALSE]
  )
  if (!nrow(demandes)) {
    return(NULL)
  }

  concordance_rows <- vector("list", 0)

  for (i in seq_len(nrow(demandes))) {
    terme <- trimws(as.character(demandes$Terme[[i]]))
    terme_recherche <- preparer_terme_concordancier_jsd_sante(terme, unite_lexicale = unite_lexicale_resolue)
    unite_depart <- trimws(as.character(demandes$Unite_depart[[i]]))
    unite_arrivee <- trimws(as.character(demandes$Unite_arrivee[[i]]))
    mode_comparaison <- trimws(as.character(demandes$Mode_comparaison[[i]]))
    termes_emotion <- if (!is.null(lexique_emotionnel_df) && is.data.frame(lexique_emotionnel_df) && nrow(lexique_emotionnel_df)) {
      unique(lexique_emotionnel_df$terme[lexique_emotionnel_df$emotion == terme])
    } else {
      character(0)
    }

    for (unite in unique(c(unite_depart, unite_arrivee))) {
      if (!nzchar(unite)) next
      idx_unite <- which(unites == unite)
      if (!length(idx_unite)) next

      textes_source_unite <- textes_source[idx_unite]
      textes_recherche_unite <- if (!is.null(segments_lexicaux) && identical(unite_lexicale_resolue, "bigramme")) {
        segments_lexicaux[idx_unite]
      } else {
        if (!is.null(segments_lexicaux)) segments_lexicaux[idx_unite] else textes_source_unite
      }

      idx_segments <- if (identical(couche_analyse_resolue, "emotionnelle")) {
        detecter_segments_contenant_plusieurs_termes_jsd_sante(textes_recherche_unite, termes_emotion)
      } else {
        detecter_segments_contenant_terme_jsd_sante(textes_recherche_unite, terme_recherche)
      }
      if (!any(idx_segments)) next

      segments_source <- textes_source_unite[idx_segments]
      segments_lexicaux_unite <- if (is.null(segments_lexicaux)) {
        rep("", sum(idx_segments))
      } else {
        as.character(segments_lexicaux[idx_unite][idx_segments])
      }

      for (j in seq_along(segments_source)) {
        segment_source <- as.character(segments_source[[j]])
        segment_lexical <- as.character(segments_lexicaux_unite[[j]])
        segment_affiche <- if (identical(unite_lexicale_resolue, "bigramme") && nzchar(segment_lexical)) {
          segment_lexical
        } else {
          segment_source
        }
        concordance_rows[[length(concordance_rows) + 1L]] <- data.frame(
          Mode_comparaison = mode_comparaison,
          Unite_depart = unite_depart,
          Unite_arrivee = unite_arrivee,
          Unite = unite,
          Terme = terme,
          Segment = segment_affiche,
          Segment_source = segment_source,
          Segment_lexical = segment_lexical,
          stringsAsFactors = FALSE
        )
      }
    }
  }

  if (!length(concordance_rows)) {
    return(NULL)
  }

  concordance_df <- do.call(rbind, concordance_rows)
  utils::write.csv(concordance_df, output_file, row.names = FALSE, fileEncoding = "UTF-8")
  output_file
}

generer_exports_suivi_longitudinal_jsd <- function(filtered_corpus_ok,
                                                   dfm_ok,
                                                   tok_ok = NULL,
                                                   output_dir,
                                                   textes_indexation = NULL,
                                                   variable_suivi = NULL,
                                                   variable_filtre = NULL,
                                                   modalite_filtre = NULL,
                                                   modalites_selectionnees = character(0),
                                                   ordre_chronologique = "asc",
                                                   unite_lexicale = "unigramme",
                                                   couche_analyse = "lexicale_brute",
                                                   lexique_emotionnel = "feel",
                                                   top_n_terms = 20L,
                                                   amplification_signal = 1,
                                                   pretraitement_label = NULL,
                                                   source_dictionnaire = "lexique_fr",
                                                   filtrage_morpho = FALSE,
                                                   pos_lexique_a_conserver = character(0),
                                                   morpho_exclure_etre = FALSE,
                                                   morpho_conserver_hors_lexique = TRUE,
                                                   logger = NULL) {
  if (is.null(filtered_corpus_ok) || is.null(dfm_ok)) {
    return(NULL)
  }

  log_suivi <- function(message) {
    if (is.function(logger)) logger(message)
  }

  # Le calcul lexical reste indépendant de la CHD.
  resultat_suivi <- calculer_suivi_longitudinal_jsd(
    filtered_corpus_ok = filtered_corpus_ok,
    dfm_ok = dfm_ok,
    tok_ok = tok_ok,
    variable_suivi = variable_suivi,
    variable_filtre = variable_filtre,
    modalite_filtre = modalite_filtre,
    modalites_selectionnees = modalites_selectionnees,
    ordre_chronologique = ordre_chronologique,
    unite_lexicale = unite_lexicale,
    couche_analyse = couche_analyse,
    lexique_emotionnel = lexique_emotionnel,
    top_n_terms = top_n_terms,
    logger = logger
  )
  if (is.null(resultat_suivi)) {
    return(NULL)
  }

  suivi_dir <- file.path(output_dir, "sante")
  dir.create(suivi_dir, recursive = TRUE, showWarnings = FALSE)

  meta_df <- data.frame(
    Indicateur = c(
      "Couche d'analyse",
      "Lexique émotionnel",
      "Variable de suivi",
      "Ordre chronologique",
      "Unité lexicale",
      "Amplification visuelle du signal",
      "Source lexicale",
      "Prétraitement",
      "Filtrage morphosyntaxique",
      "Catégories morphosyntaxiques",
      "Exclure « être »",
      "Conserver formes hors lexique",
      "Filtre appliqué",
      "Entretiens retenus",
      "Taille du vocabulaire commun",
      "Note"
    ),
    Valeur = c(
      if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) "trajectoire émotionnelle" else "trajectoire lexicale brute",
      if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) toupper(as.character(resultat_suivi$lexique_emotionnel %||% lexique_emotionnel %||% "feel")) else "non utilisé",
      sub("^\\*", "", resultat_suivi$variable),
      if (identical(resultat_suivi$ordre_utilise, "desc")) "décroissant" else "croissant",
      if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
        "grammes / unigrammes"
      } else if (identical(resultat_suivi$unite_lexicale, "bigramme")) {
        "bigrammes"
      } else {
        "grammes / unigrammes"
      },
      paste0("x", normaliser_amplification_signal_sante(amplification_signal), " (graphes uniquement)"),
      as.character(source_dictionnaire %||% "lexique_fr"),
      if (nzchar(as.character(pretraitement_label %||% ""))) as.character(pretraitement_label) else "formes",
      if (isTRUE(filtrage_morpho)) "actif" else "inactif",
      if (isTRUE(filtrage_morpho)) {
        categories <- unique(trimws(as.character(pos_lexique_a_conserver %||% character(0))))
        categories <- categories[nzchar(categories)]
        if (length(categories)) paste(categories, collapse = ", ") else "aucune catégorie sélectionnée"
      } else {
        "non appliquées"
      },
      if (isTRUE(filtrage_morpho)) if (isTRUE(morpho_exclure_etre)) "oui" else "non" else "non appliqué",
      if (isTRUE(filtrage_morpho)) if (isTRUE(morpho_conserver_hors_lexique)) "oui" else "non" else "non appliqué",
      if (!is.null(resultat_suivi$variable_filtre) && nzchar(as.character(resultat_suivi$modalite_filtre %||% ""))) {
        paste0(sub("^\\*", "", resultat_suivi$variable_filtre), " = ", as.character(resultat_suivi$modalite_filtre))
      } else {
        "aucun"
      },
      length(resultat_suivi$unites),
      resultat_suivi$n_vocabulaire,
      if (nzchar(resultat_suivi$note)) resultat_suivi$note else "Analyse longitudinale disponible."
    ),
    stringsAsFactors = FALSE
  )

  matrix_df <- data.frame(
    Unite = rownames(resultat_suivi$jsd_mat),
    resultat_suivi$jsd_mat,
    check.names = FALSE,
    stringsAsFactors = FALSE
  )

  meta_file <- file.path(suivi_dir, "suivi_meta.csv")
  indicateurs_file <- file.path(suivi_dir, "indicateurs_entretiens.csv")
  successive_file <- file.path(suivi_dir, "divergence_jensen_shannon_successive.csv")
  reference_file <- file.path(suivi_dir, "divergence_jensen_shannon_reference.csv")
  ruptures_file <- file.path(suivi_dir, "detection_ruptures_discursives.csv")
  terms_file <- file.path(suivi_dir, "termes_evolution.csv")
  contributions_file <- file.path(suivi_dir, "contributions_divergence_jensen_shannon.csv")
  matrix_file <- file.path(suivi_dir, "matrice_divergence_jensen_shannon.csv")
  concordancier_file <- file.path(suivi_dir, "concordancier_jsd.csv")
  profils_emotionnels_file <- file.path(suivi_dir, "profils_emotionnels.csv")
  profils_valence_file <- file.path(suivi_dir, "profils_valence.csv")

  utils::write.csv(arrondir_dataframe_numerique_sante(meta_df, digits = 6L), meta_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$indicateurs_df, digits = 6L), indicateurs_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$successive_df, digits = 6L), successive_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$reference_df, digits = 6L), reference_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$ruptures_df, digits = 6L), ruptures_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$terms_df, digits = 6L), terms_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$contributions_df, digits = 6L), contributions_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(matrix_df, digits = 6L), matrix_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$profils_emotionnels_df, digits = 6L), profils_emotionnels_file, row.names = FALSE, fileEncoding = "UTF-8")
  utils::write.csv(arrondir_dataframe_numerique_sante(resultat_suivi$profils_valence_df, digits = 6L), profils_valence_file, row.names = FALSE, fileEncoding = "UTF-8")
  concordancier_path <- generer_concordancier_jsd_sante(
    filtered_corpus_ok = filtered_corpus_ok,
    dfm_ok = dfm_ok,
    tok_ok = tok_ok,
    variable_suivi = resultat_suivi$variable,
    contributions_df = resultat_suivi$contributions_df,
    unite_lexicale = resultat_suivi$unite_lexicale,
    couche_analyse = resultat_suivi$couche_analyse %||% "lexicale_brute",
    lexique_emotionnel = resultat_suivi$lexique_emotionnel %||% lexique_emotionnel,
    output_file = concordancier_file
  )

  entropy_plot_file <- file.path(suivi_dir, "entropie_lexicale.png")
  redundancy_plot_file <- file.path(suivi_dir, "redondance_relative.png")
  successive_plot_file <- file.path(suivi_dir, "divergence_jensen_shannon_successive.png")
  reference_plot_file <- file.path(suivi_dir, "divergence_jensen_shannon_reference.png")
  ruptures_plot_file <- file.path(suivi_dir, "detection_ruptures_discursives.png")
  matrix_plot_file <- file.path(suivi_dir, "matrice_divergence_jensen_shannon.png")
  profils_emotionnels_plot_file <- file.path(suivi_dir, "profils_emotionnels.png")
  profils_valence_plot_file <- file.path(suivi_dir, "profils_valence.png")

  tracer_courbe_suivi_sante(
    x_labels = resultat_suivi$indicateurs_df$Unite,
    y_values = resultat_suivi$indicateurs_df$Entropie_lexicale,
    output_file = entropy_plot_file,
    titre = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
      "Entropie émotionnelle par entretien"
    } else {
      "Entropie lexicale par entretien"
    },
    ylab = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) "Entropie émotionnelle" else "Entropie lexicale",
    couleur = "#1971c2",
    amplification_signal = 1
  )

  tracer_courbe_suivi_sante(
    x_labels = resultat_suivi$indicateurs_df$Unite,
    y_values = resultat_suivi$indicateurs_df$Redondance_relative,
    output_file = redundancy_plot_file,
    titre = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
      "Redondance émotionnelle relative par entretien"
    } else {
      "Redondance relative par entretien"
    },
    ylab = "Redondance relative",
    couleur = "#d9480f",
    ylim = c(0, 1),
    amplification_signal = 1
  )

  if (nrow(resultat_suivi$successive_df) >= 1L) {
    tracer_courbe_suivi_sante(
      x_labels = paste(resultat_suivi$successive_df$Unite_depart, "→", resultat_suivi$successive_df$Unite_arrivee),
      y_values = resultat_suivi$successive_df$Divergence_Jensen_Shannon,
      output_file = successive_plot_file,
      titre = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
        "Divergence de Jensen-Shannon émotionnelle entre séances successives"
      } else {
        "Divergence de Jensen-Shannon entre séances successives"
      },
      ylab = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
        "Divergence de Jensen-Shannon émotionnelle"
      } else {
        "Divergence de Jensen-Shannon"
      },
      couleur = "#5f3dc4",
      ylim = c(0, 1),
      amplification_signal = amplification_signal
    )
  } else {
    successive_plot_file <- NULL
  }

  if (nrow(resultat_suivi$reference_df) >= 1L) {
    tracer_courbe_suivi_sante(
      x_labels = resultat_suivi$reference_df$Unite_comparee,
      y_values = resultat_suivi$reference_df$Divergence_Jensen_Shannon,
      output_file = reference_plot_file,
      titre = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
        "Divergence de Jensen-Shannon émotionnelle par rapport à la première séance"
      } else {
        "Divergence de Jensen-Shannon par rapport à la première séance"
      },
      ylab = if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle")) {
        "Divergence de Jensen-Shannon émotionnelle"
      } else {
        "Divergence de Jensen-Shannon"
      },
      couleur = "#2b8a3e",
      ylim = c(0, 1),
      amplification_signal = amplification_signal
    )
  } else {
    reference_plot_file <- NULL
  }

  if (nrow(resultat_suivi$ruptures_df) >= 1L) {
    tracer_detection_ruptures_sante(
      ruptures_df = resultat_suivi$ruptures_df,
      output_file = ruptures_plot_file,
      amplification_signal = amplification_signal
    )
  } else {
    ruptures_plot_file <- NULL
  }

  tracer_heatmap_divergence_jensen_shannon_sante(
    resultat_suivi$jsd_mat,
    matrix_plot_file,
    variable_label = sub("^\\*", "", resultat_suivi$variable)
  )

  if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle") &&
      is.data.frame(resultat_suivi$profils_emotionnels_df) && nrow(resultat_suivi$profils_emotionnels_df)) {
    tracer_barplot_empile_sante(
      resultat_suivi$profils_emotionnels_df,
      profils_emotionnels_plot_file,
      titre = paste0("Profils émotionnels · ", toupper(resultat_suivi$lexique_emotionnel %||% lexique_emotionnel %||% "FEEL"))
    )
  } else {
    profils_emotionnels_plot_file <- NULL
  }

  if (identical(resultat_suivi$couche_analyse %||% "lexicale_brute", "emotionnelle") &&
      is.data.frame(resultat_suivi$profils_valence_df) && nrow(resultat_suivi$profils_valence_df) &&
      ncol(resultat_suivi$profils_valence_df) > 1L) {
    tracer_barplot_empile_sante(
      resultat_suivi$profils_valence_df,
      profils_valence_plot_file,
      titre = "Résumé de valence positive / négative",
      palette = c("#2b8a3e", "#c92a2a")
    )
  } else {
    profils_valence_plot_file <- NULL
  }

  frise_dir <- file.path(suivi_dir, "frises_emergences")
  frise_files <- generer_frises_emergences_suivi_sante(
    terms_df = resultat_suivi$terms_df,
    frise_dir = frise_dir,
    top_n_terms = top_n_terms
  )

  divergent_dir <- file.path(suivi_dir, "barres_divergentes")
  divergent_files <- generer_barres_divergentes_suivi_sante(
    terms_df = resultat_suivi$terms_df,
    divergent_dir = divergent_dir,
    top_n_terms = top_n_terms
  )

  waterfall_dir <- file.path(suivi_dir, "waterfalls")
  waterfall_files <- generer_waterfalls_contributions_suivi_sante(
    contributions_df = resultat_suivi$contributions_df,
    waterfall_dir = waterfall_dir,
    top_n_terms = top_n_terms
  )

  wordcloud_dir <- file.path(suivi_dir, "wordclouds")
  wordcloud_files <- generer_wordclouds_suivi_sante(
    grouped_mat = resultat_suivi$grouped_mat,
    unites_ordonnees = resultat_suivi$unites,
    wordcloud_dir = wordcloud_dir,
    top_n_terms = top_n_terms
  )

  log_suivi(
    paste0(
      "Suivi longitudinal : ",
      length(resultat_suivi$unites),
      " entretiens comparés avec la variable ",
      resultat_suivi$variable,
      "."
    )
  )

  list(
    files = list(
      meta = meta_file,
      indicators = indicateurs_file,
      jsd_successive = successive_file,
      jsd_reference = reference_file,
      ruptures = ruptures_file,
      terms = terms_file,
      contributions = contributions_file,
      matrix = matrix_file,
      concordancier = concordancier_path,
      emotion_profiles = profils_emotionnels_file,
      valence_profiles = profils_valence_file,
      entropy_plot = entropy_plot_file,
      redundancy_plot = redundancy_plot_file,
      jsd_successive_plot = successive_plot_file,
      jsd_reference_plot = reference_plot_file,
      ruptures_plot = ruptures_plot_file,
      matrix_plot = matrix_plot_file,
      emotion_profiles_plot = profils_emotionnels_plot_file,
      valence_profiles_plot = profils_valence_plot_file,
      frises_emergences = frise_files,
      divergent_bars = divergent_files,
      waterfalls = waterfall_files,
      wordclouds = wordcloud_files
    ),
    note = resultat_suivi$note,
    variable = resultat_suivi$variable,
    unites = resultat_suivi$unites
  )
}
