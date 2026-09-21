# Role du fichier: discriminationsimple.R ajoute un mode de discrimination
# volontairement plus simple. Le choix final peut reposer soit sur les mots
# significatifs de la CHD, soit sur les coordonnees AFC reelles des classes.

if (!exists("%||%", mode = "function", inherits = TRUE)) {
  `%||%` <- function(x, y) {
    if (is.null(x) || length(x) == 0) y else x
  }
}

normaliser_mode_score_discrimination_simple_iramuteq <- function(value,
                                                                 default = "afc_classes_direct") {
  raw <- tolower(trimws(as.character(value %||% default)[[1]]))
  if (is.na(raw) || !nzchar(raw)) {
    raw <- default
  }
  if (raw %in% c("afc_classes_direct", "classes_direct", "direct")) {
    return("afc_classes_direct")
  }
  if (raw %in% c("s_lexical", "s", "lexical")) {
    return("s_lexical")
  }
  default
}

etiquette_mode_score_discrimination_simple_iramuteq <- function(value) {
  mode <- normaliser_mode_score_discrimination_simple_iramuteq(value)
  if (identical(mode, "afc_classes_direct")) {
    return("Distance directe des classes AFC")
  }
  "Score S lexical"
}

# Utilise les positions produites directement par FactoMineR::CA() pour les
# lignes de la table classes x termes. Aucun centre lexical n'est reconstruit.
calculer_score_classes_direct_afc_iramuteq <- function(afc_obj) {
  empty_result <- list(
    value = 0,
    classes_coords = NULL,
    distances_by_pair = numeric(0)
  )

  coords_classes <- .extraire_coordonnees_xy_auto_chd(afc_obj$rowcoord)
  if (is.null(coords_classes) || nrow(coords_classes) < 2L) {
    return(empty_result)
  }

  good <- is.finite(coords_classes[, "x"]) & is.finite(coords_classes[, "y"])
  coords_classes <- coords_classes[good, , drop = FALSE]
  if (nrow(coords_classes) < 2L) {
    return(empty_result)
  }

  pair_index <- utils::combn(seq_len(nrow(coords_classes)), 2L)
  distances_by_pair <- vapply(seq_len(ncol(pair_index)), function(index) {
    point_a <- coords_classes[pair_index[1L, index], c("x", "y")]
    point_b <- coords_classes[pair_index[2L, index], c("x", "y")]
    sqrt(sum((point_a - point_b)^2))
  }, numeric(1))
  pair_labels <- vapply(seq_len(ncol(pair_index)), function(index) {
    paste(
      rownames(coords_classes)[pair_index[1L, index]],
      rownames(coords_classes)[pair_index[2L, index]],
      sep = " / "
    )
  }, character(1))
  names(distances_by_pair) <- pair_labels

  list(
    value = min(distances_by_pair),
    classes_coords = coords_classes,
    distances_by_pair = distances_by_pair
  )
}

# Retient des termes significatifs qui servent uniquement de reperes de
# lecture pour les axes AFC. Ils ne modifient ni l'AFC ni la selection CHD.
extraire_mots_reperes_axes_discrimination_simple_iramuteq <- function(afc_obj,
                                                                       res_stats_df,
                                                                       top_n = 3L,
                                                                       p_seuil = 0.05) {
  empty_result <- data.frame(
    classe = character(0),
    terme = character(0),
    axe_dominant = character(0),
    pole = character(0),
    x = numeric(0),
    y = numeric(0),
    amplitude = numeric(0),
    chi2 = numeric(0),
    stringsAsFactors = FALSE
  )

  coords_termes <- .extraire_coordonnees_xy_auto_chd(afc_obj$colcoord)
  if (is.null(coords_termes) || !nrow(coords_termes)) {
    return(empty_result)
  }

  top_n <- .as_int_auto_chd(top_n, default = 3L, min_value = 1L)
  rows <- .selectionner_lignes_chi2_afc_auto_chd(
    res_stats_df = res_stats_df,
    top_n = NULL,
    p_seuil = p_seuil
  )
  if (is.null(rows) || !is.data.frame(rows) || !nrow(rows) ||
      !"p_num" %in% names(rows)) {
    return(empty_result)
  }

  # Unlike the AFC construction fallback, axis labels must remain strictly
  # based on statistically significant characteristic terms.
  rows <- rows[
    is.finite(rows$p_num) & !is.na(rows$p_num) & rows$p_num <= p_seuil &
      rows$Terme %in% rownames(coords_termes),
    ,
    drop = FALSE
  ]
  if (!nrow(rows)) {
    return(empty_result)
  }

  coord_index <- match(rows$Terme, rownames(coords_termes))
  rows$x <- coords_termes[coord_index, "x"]
  rows$y <- coords_termes[coord_index, "y"]
  rows <- rows[
    is.finite(rows$x) & is.finite(rows$y) &
      !duplicated(paste(rows$Classe_num, rows$Terme, sep = "::")),
    ,
    drop = FALSE
  ]
  if (!nrow(rows)) {
    return(empty_result)
  }

  rows$amplitude <- pmax(abs(rows$x), abs(rows$y))
  rows <- rows[is.finite(rows$amplitude) & rows$amplitude > 0, , drop = FALSE]
  if (!nrow(rows)) {
    return(empty_result)
  }
  rows$axe_dominant <- ifelse(abs(rows$x) >= abs(rows$y), "Axe 1", "Axe 2")
  coord_dominante <- ifelse(rows$axe_dominant == "Axe 1", rows$x, rows$y)
  rows$pole <- ifelse(coord_dominante >= 0, "+", "-")

  classes <- sort(unique(rows$Classe_num))
  top_rows <- lapply(classes, function(classe_num) {
    rows_classe <- rows[rows$Classe_num == classe_num, , drop = FALSE]
    rows_classe <- rows_classe[order(-rows_classe$amplitude, -rows_classe$chi2_num), , drop = FALSE]
    utils::head(rows_classe, top_n)
  })
  top_rows <- top_rows[vapply(top_rows, nrow, integer(1)) > 0L]
  if (!length(top_rows)) {
    return(empty_result)
  }

  result <- do.call(rbind, top_rows)
  rownames(result) <- NULL
  data.frame(
    classe = paste("Classe", result$Classe_num),
    terme = as.character(result$Terme),
    axe_dominant = as.character(result$axe_dominant),
    pole = as.character(result$pole),
    x = suppressWarnings(as.numeric(result$x)),
    y = suppressWarnings(as.numeric(result$y)),
    amplitude = suppressWarnings(as.numeric(result$amplitude)),
    chi2 = suppressWarnings(as.numeric(result$chi2_num)),
    stringsAsFactors = FALSE
  )
}

calculer_score_discrimination_simple_iramuteq <- function(afc_obj,
                                                          res_stats_df,
                                                          top_n = NULL,
                                                          p_seuil = 0.05) {
  coords_termes <- .extraire_coordonnees_xy_auto_chd(afc_obj$colcoord)
  top_rows <- .selectionner_lignes_chi2_afc_auto_chd(
    res_stats_df = res_stats_df,
    top_n = top_n,
    p_seuil = p_seuil
  )

  empty_result <- list(
    S = 0,
    poles_by_class = NULL,
    dispersions_by_class = numeric(0),
    separations_by_pair = numeric(0),
    separations_plus_proches_by_class = numeric(0),
    termes_cibles = character(0),
    termes_cibles_par_classe = list()
  )

  if (is.null(coords_termes) || nrow(coords_termes) < 2L || is.null(top_rows) || !is.data.frame(top_rows) || !nrow(top_rows)) {
    return(empty_result)
  }

  top_rows <- top_rows[
    nzchar(top_rows$Terme) &
      top_rows$Terme %in% rownames(coords_termes),
    ,
    drop = FALSE
  ]
  if (!nrow(top_rows)) {
    return(empty_result)
  }

  class_ids <- sort(unique(top_rows$Classe_num))
  poles_by_class <- list()
  dispersions_by_class <- numeric(0)
  termes_par_classe <- list()

  for (class_num in class_ids) {
    df_cl <- top_rows[top_rows$Classe_num == class_num, , drop = FALSE]
    if (!nrow(df_cl)) next

    df_cl <- df_cl[!duplicated(df_cl$Terme), , drop = FALSE]
    term_coords <- coords_termes[match(df_cl$Terme, rownames(coords_termes)), c("x", "y"), drop = FALSE]
    good <- is.finite(term_coords[, "x"]) & is.finite(term_coords[, "y"])
    if (!any(good)) next

    df_cl <- df_cl[good, , drop = FALSE]
    term_coords <- term_coords[good, , drop = FALSE]
    # Le chi2 selectionne les termes significatifs, sans les reponderer.
    # Le centre de classe est uniquement la moyenne de leurs coordonnees AFC.
    pole_vec <- c(
      x = mean(term_coords[, "x"]),
      y = mean(term_coords[, "y"])
    )

    class_label <- paste0("Classe ", class_num)
    poles_by_class[[class_label]] <- pole_vec
    distances_au_centre <- sqrt(rowSums(sweep(term_coords, 2L, pole_vec, FUN = "-")^2))
    dispersions_by_class[[class_label]] <- if (length(distances_au_centre) >= 2L) {
      stats::median(distances_au_centre)
    } else {
      NA_real_
    }
    termes_par_classe[[class_label]] <- unique(as.character(df_cl$Terme))
  }

  if (length(poles_by_class) < 2L) {
    empty_result$termes_cibles <- unique(as.character(top_rows$Terme))
    empty_result$termes_cibles_par_classe <- termes_par_classe
    empty_result$dispersions_by_class <- dispersions_by_class
    return(empty_result)
  }

  poles_matrix <- do.call(rbind, lapply(poles_by_class, function(vec) c(x = vec[["x"]], y = vec[["y"]])))
  rownames(poles_matrix) <- names(poles_by_class)

  # On rapporte l'ecart entre deux centres a la dispersion lexicale des classes.
  # Cela permet de comparer equitablement des partitions a 3, 4, 5 classes ou plus.
  dispersion_reference <- suppressWarnings(stats::median(
    dispersions_by_class[is.finite(dispersions_by_class) & dispersions_by_class > 0],
    na.rm = TRUE
  ))
  if (!is.finite(dispersion_reference) || is.na(dispersion_reference) || dispersion_reference <= 0) {
    dispersion_reference <- suppressWarnings(stats::median(
      sqrt(rowSums(coords_termes[, c("x", "y"), drop = FALSE]^2)),
      na.rm = TRUE
    ))
  }
  if (!is.finite(dispersion_reference) || is.na(dispersion_reference) || dispersion_reference <= 0) {
    dispersion_reference <- 1
  }
  dispersions_effectives <- dispersions_by_class
  dispersions_effectives[!is.finite(dispersions_effectives) | is.na(dispersions_effectives) | dispersions_effectives <= 0] <- dispersion_reference

  pair_index <- utils::combn(seq_len(nrow(poles_matrix)), 2L)
  separations_by_pair <- vapply(seq_len(ncol(pair_index)), function(index) {
    point_a <- poles_matrix[pair_index[1L, index], ]
    point_b <- poles_matrix[pair_index[2L, index], ]
    class_a <- rownames(poles_matrix)[pair_index[1L, index]]
    class_b <- rownames(poles_matrix)[pair_index[2L, index]]
    distance_centres <- sqrt(sum((point_a - point_b)^2))
    dispersion_pair <- dispersions_effectives[[class_a]] + dispersions_effectives[[class_b]]
    distance_centres / max(dispersion_pair, .Machine$double.eps)
  }, numeric(1))
  separations_plus_proches_by_class <- vapply(seq_len(nrow(poles_matrix)), function(class_index) {
    pair_positions <- which(pair_index[1L, ] == class_index | pair_index[2L, ] == class_index)
    class_separations <- separations_by_pair[pair_positions]
    class_separations <- class_separations[is.finite(class_separations)]
    if (!length(class_separations)) return(NA_real_)
    min(class_separations)
  }, numeric(1))
  names(separations_plus_proches_by_class) <- rownames(poles_matrix)

  valid_nearest_separations <- separations_plus_proches_by_class[
    is.finite(separations_plus_proches_by_class) & !is.na(separations_plus_proches_by_class)
  ]
  if (!length(valid_nearest_separations)) {
    return(empty_result)
  }

  # S est la mediane des separations du voisin le plus proche par classe, et
  # non le minimum global. Une paire compte seulement pour les classes dont
  # elle est le voisin lexical le plus proche.
  score_separation_afc <- stats::median(valid_nearest_separations)

  list(
    S = score_separation_afc,
    poles_by_class = poles_matrix,
    dispersions_by_class = dispersions_effectives,
    separations_by_pair = separations_by_pair,
    separations_plus_proches_by_class = separations_plus_proches_by_class,
    termes_cibles = unique(as.character(top_rows$Terme)),
    termes_cibles_par_classe = termes_par_classe
  )
}

evaluer_partition_discrimination_simple_iramuteq <- function(dfm_obj,
                                                             partition_obj,
                                                             stats_mode = c("vectorise", "classique"),
                                                             top_n_diffusion = 20L,
                                                             top_n_afc = NULL,
                                                             p_seuil = 0.05,
                                                             afc_max_termes = 400L,
                                                             score_mode = "afc_classes_direct") {
  stats_mode <- match.arg(stats_mode)
  score_mode <- normaliser_mode_score_discrimination_simple_iramuteq(score_mode)
  if (is.null(partition_obj) || is.null(partition_obj$classes)) {
    stop("Auto discriminante : solution en classes invalide.")
  }

  classes <- suppressWarnings(as.integer(partition_obj$classes))
  ok <- is.finite(classes) & !is.na(classes) & classes > 0L
  counts <- table(classes[ok])
  total_assigned <- sum(counts)
  pct <- if (total_assigned > 0) 100 * counts / total_assigned else counts

  fn_stats <- get0("construire_stats_classes_iramuteq", mode = "function", inherits = TRUE)
  if (!is.function(fn_stats)) {
    stop("Auto discriminante : construire_stats_classes_iramuteq() est introuvable.")
  }
  fn_afc <- get0("executer_afc_classes", mode = "function", inherits = TRUE)
  if (!is.function(fn_afc)) {
    stop("Auto discriminante : executer_afc_classes() est introuvable.")
  }

  res_stats_df <- fn_stats(
    dfm_obj = dfm_obj,
    classes = classes,
    max_p = 1,
    stats_mode = stats_mode
  )

  # H, D, L and B belong to the former structural layer. They do not take
  # part in either direct AFC selection or lexical S selection.
  h_value <- NA_real_
  d_value <- NA_real_
  l_value <- NA_real_
  b_value <- NA_real_

  termes_cibles <- .selectionner_termes_caracteristiques_afc_auto_chd(
    res_stats_df = res_stats_df,
    top_n = top_n_afc,
    p_seuil = p_seuil
  )
  termes_cibles_par_classe <- .selectionner_termes_caracteristiques_par_classe_afc_auto_chd(
    res_stats_df = res_stats_df,
    top_n = top_n_afc,
    p_seuil = p_seuil
  )

  afc_obj <- fn_afc(
    dfm_obj = dfm_obj,
    groupes = classes,
    termes_cibles = if (length(termes_cibles) >= 2L) termes_cibles else NULL,
    max_termes = if (length(termes_cibles) >= 2L) {
      max(2L, suppressWarnings(as.integer(length(termes_cibles))))
    } else {
      .as_int_auto_chd(afc_max_termes, default = 400L, min_value = 2L)
    },
    seuil_p = p_seuil,
    rv = NULL
  )
  mots_reperes_axes <- extraire_mots_reperes_axes_discrimination_simple_iramuteq(
    afc_obj = afc_obj,
    res_stats_df = res_stats_df,
    top_n = 3L,
    p_seuil = p_seuil
  )

  # The lexical calculation is intentionally run only when the user selects
  # S. Direct AFC selection must remain a pure comparison of row coordinates.
  simple_scores <- NULL
  if (identical(score_mode, "s_lexical")) {
    simple_scores <- calculer_score_discrimination_simple_iramuteq(
      afc_obj = afc_obj,
      res_stats_df = res_stats_df,
      top_n = top_n_afc,
      p_seuil = p_seuil
    )
  }
  direct_class_scores <- if (identical(score_mode, "afc_classes_direct")) {
    calculer_score_classes_direct_afc_iramuteq(afc_obj)
  } else {
    list(value = NA_real_, classes_coords = NULL, distances_by_pair = numeric(0))
  }
  score_s_lexical <- if (is.null(simple_scores)) {
    NA_real_
  } else {
    suppressWarnings(as.numeric(simple_scores$S))
  }
  score_classes_direct <- suppressWarnings(as.numeric(direct_class_scores$value))
  score_selection <- if (identical(score_mode, "afc_classes_direct")) {
    score_classes_direct
  } else {
    score_s_lexical
  }

  metrics <- data.frame(
    partition = paste0("P", partition_obj$requested_k %||% partition_obj$k),
    etape_chd = as.integer(partition_obj$requested_k %||% partition_obj$k),
    k = as.integer(partition_obj$k),
    n_segments_assignes = as.integer(total_assigned),
    n_segments_non_assignes = as.integer(sum(!ok)),
    H = h_value,
    D = d_value,
    L = l_value,
    B = b_value,
    S = score_s_lexical,
    distance_classes_afc = score_classes_direct,
    score_mode = score_mode,
    score_label = etiquette_mode_score_discrimination_simple_iramuteq(score_mode),
    score_selection = score_selection,
    classes_effectifs = .formatter_resume_classes_auto_chd(counts, digits = 0L),
    classes_pourcentages = .formatter_resume_classes_auto_chd(pct, digits = 2L, suffix = "%"),
    stringsAsFactors = FALSE
  )

  list(
    partition = partition_obj,
    metrics = metrics,
    stats = res_stats_df,
    diffusion_by_class = NULL,
    afc = afc_obj,
    termes_cibles = unique(as.character(if (!is.null(simple_scores) && length(simple_scores$termes_cibles)) simple_scores$termes_cibles else termes_cibles)),
    termes_cibles_par_classe = if (!is.null(simple_scores) && length(simple_scores$termes_cibles_par_classe)) simple_scores$termes_cibles_par_classe else termes_cibles_par_classe,
    simple_dispersions_by_class = if (!is.null(simple_scores)) simple_scores$dispersions_by_class else NULL,
    simple_separations_by_pair = if (!is.null(simple_scores)) simple_scores$separations_by_pair else NULL,
    simple_poles = if (!is.null(simple_scores)) simple_scores$poles_by_class else NULL,
    direct_classes_coords = direct_class_scores$classes_coords,
    direct_classes_distances_by_pair = direct_class_scores$distances_by_pair,
    mots_reperes_axes = mots_reperes_axes
  )
}

selection_discrimination_simple_classes_iramuteq <- function(chd_obj,
                                                             dfm_obj,
                                                             k_min = NULL,
                                                             k_max = NULL,
                                                             mincl = 0,
                                                             mincl_mode = c("auto", "manuel"),
                                                             classif_mode = c("simple", "double"),
                                                             stats_mode = c("vectorise", "classique"),
                                                             top_n_diffusion = 20L,
                                                             top_n_afc = NULL,
                                                             p_seuil = 0.05,
                                                             afc_max_termes = 400L,
                                                             score_mode = "afc_classes_direct") {
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  stats_mode <- match.arg(stats_mode)
  score_mode <- normaliser_mode_score_discrimination_simple_iramuteq(score_mode)

  partitions <- lister_partitions_chd_iramuteq(
    chd_obj = chd_obj,
    k_min = k_min,
    k_max = k_max,
    mincl = mincl,
    mincl_mode = mincl_mode,
    classif_mode = classif_mode
  )
  if (!length(partitions)) {
    stop("Auto discriminante : aucune solution exploitable entre 3 classes et la borne maximale demandee.")
  }
  partitions <- partitions[order(
    vapply(partitions, function(partition_obj) suppressWarnings(as.integer(partition_obj$k)), integer(1)),
    vapply(partitions, function(partition_obj) suppressWarnings(as.integer(partition_obj$requested_k %||% partition_obj$k)), integer(1))
  )]

  evaluations <- lapply(partitions, function(partition_obj) {
    evaluer_partition_discrimination_simple_iramuteq(
      dfm_obj = dfm_obj,
      partition_obj = partition_obj,
      stats_mode = stats_mode,
      top_n_diffusion = top_n_diffusion,
      top_n_afc = top_n_afc,
      p_seuil = p_seuil,
      afc_max_termes = afc_max_termes,
      score_mode = score_mode
    )
  })

  metrics_df <- do.call(rbind, lapply(evaluations, `[[`, "metrics"))
  metrics_df$G <- NA_real_
  metrics_df$GS <- NA_real_

  if (nrow(metrics_df) > 1L) {
    b_values <- suppressWarnings(as.numeric(metrics_df$B))
    s_values <- suppressWarnings(as.numeric(metrics_df$score_selection))
    gains_b <- rep(NA_real_, length(b_values))
    gains_s <- rep(NA_real_, length(s_values))
    gains_b[-1L] <- b_values[-1L] - b_values[-length(b_values)]
    gains_s[-1L] <- s_values[-1L] - s_values[-length(s_values)]
    metrics_df$G <- gains_b
    metrics_df$GS <- gains_s
  }

  s_values <- suppressWarnings(as.numeric(metrics_df$score_selection))
  s_scores <- ifelse(is.finite(s_values) & !is.na(s_values), s_values, -Inf)
  if (!any(is.finite(s_scores) & s_scores > -Inf)) {
    stop("Auto discriminante : aucun score discriminant exploitable n'a pu etre calcule.")
  }

  k_values <- suppressWarnings(as.integer(metrics_df$k))
  etape_values <- suppressWarnings(as.integer(metrics_df$etape_chd))
  k_tie_break <- ifelse(is.finite(k_values) & !is.na(k_values), k_values, Inf)
  etape_tie_break <- ifelse(is.finite(etape_values) & !is.na(etape_values), etape_values, Inf)

  # Le critere choisi est prioritaire. En cas d'egalite, on privilegie une solution plus
  # parcimonieuse, puis une etape CHD plus courte.
  ordre <- order(-s_scores, k_tie_break, etape_tie_break, na.last = TRUE)
  selected_idx <- ordre[[1]]
  selection_rule <- if (identical(score_mode, "afc_classes_direct")) {
    "meilleure_distance_directe_classes_afc"
  } else {
    "meilleur_score_s_lexical"
  }

  metrics_df$selection <- ifelse(seq_len(nrow(metrics_df)) == selected_idx, "oui", "non")

  selected_partition <- partitions[[selected_idx]]
  selected_evaluation <- evaluations[[selected_idx]]
  k_max_tested <- suppressWarnings(max(as.integer(metrics_df$etape_chd), na.rm = TRUE))
  k_max_requested <- suppressWarnings(as.integer(chd_obj$auto_k_requested %||% k_max[[1]] %||% k_max))
  k_min_requested <- suppressWarnings(as.integer(k_min[[1]] %||% k_min))
  if (!length(k_max_requested) || is.na(k_max_requested) || !is.finite(k_max_requested)) {
    k_max_requested <- as.integer(k_max_tested)
  }
  if (!length(k_min_requested) || is.na(k_min_requested) || !is.finite(k_min_requested)) {
    k_min_requested <- suppressWarnings(min(as.integer(metrics_df$k), na.rm = TRUE))
  }
  k_min_requested <- max(3L, k_min_requested)
  k_max_requested <- max(2L, k_max_requested)
  k_min_tested <- suppressWarnings(min(as.integer(metrics_df$etape_chd), na.rm = TRUE))
  if (!is.finite(selected_partition$k) || is.na(selected_partition$k) || selected_partition$k < k_min_requested) {
    stop(paste0(
      "Auto discriminante : la solution retenue ne respecte pas la borne minimale demandee (",
      k_min_requested,
      " classes reelles minimum)."
    ))
  }

  list(
    mode = "discrimination_simple",
    mode_label = "CHD Opposition optimisée",
    score_column = "score_selection",
    score_mode = score_mode,
    score_label = etiquette_mode_score_discrimination_simple_iramuteq(score_mode),
    score_plot_title = "Selection de la configuration aux classes les plus separees",
    selection_rule = selection_rule,
    classes = selected_partition$classes,
    classes_raw = selected_partition$classes_raw,
    terminales = selected_partition$terminales,
    k_selected = as.integer(metrics_df$k[[selected_idx]]),
    k_chd_selected = as.integer(selected_partition$requested_k %||% metrics_df$etape_chd[[selected_idx]]),
    mincl_selected = selected_partition$mincl %||% NA_integer_,
    fallback_mincl1 = isTRUE(selected_partition$fallback_mincl1),
    selected_chd = selected_partition$chd,
    k_min_requested = as.integer(k_min_requested),
    k_min_tested = as.integer(k_min_tested),
    k_max_requested = as.integer(k_max_requested),
    k_max_tested = as.integer(k_max_tested),
    k_max_reduced = isTRUE(k_max_tested < k_max_requested),
    k_reduction_reason = chd_obj$auto_k_reduction_reason %||% NULL,
    evaluation = metrics_df,
    selected_metrics = metrics_df[selected_idx, , drop = FALSE],
    selected_stats = selected_evaluation$stats,
    selected_diffusion_by_class = selected_evaluation$diffusion_by_class,
    selected_afc = selected_evaluation$afc,
    selected_termes_cibles = selected_evaluation$termes_cibles,
    selected_termes_cibles_par_classe = selected_evaluation$termes_cibles_par_classe,
    selected_simple_dispersions_by_class = selected_evaluation$simple_dispersions_by_class,
    selected_simple_separations_by_pair = selected_evaluation$simple_separations_by_pair,
    selected_simple_poles = selected_evaluation$simple_poles,
    selected_direct_classes_coords = selected_evaluation$direct_classes_coords,
    selected_direct_classes_distances_by_pair = selected_evaluation$direct_classes_distances_by_pair,
    selected_mots_reperes_axes = selected_evaluation$mots_reperes_axes,
    partitions = partitions
  )
}

.resume_configuration_discrimination_simple <- function(candidate) {
  if (is.null(candidate) || !is.list(candidate)) return("")
  paste0(
    candidate$id %||% "",
    " [morpho=",
    candidate$profil_morpho %||% "n/a",
    " | lemmes=",
    ifelse(isTRUE(candidate$lexique_utiliser_lemmes), "oui", "non"),
    " | stopwords=",
    ifelse(isTRUE(candidate$retirer_stopwords), "oui", "non"),
    " | ponctuation=",
    ifelse(isTRUE(candidate$supprimer_ponctuation), "oui", "non"),
    " | chiffres=",
    ifelse(isTRUE(candidate$supprimer_chiffres), "supprimes", "conserves"),
    " | mincl=",
    candidate$mincl %||% candidate$config$iramuteq_mincl %||% NA_integer_,
    " (",
    candidate$config$iramuteq_mincl_mode %||% "auto",
    ")",
    " | min_docfreq=",
    candidate$min_docfreq %||% NA_integer_,
    " | classes_phase_1=",
    candidate$k_max_explore %||% candidate$config$k_iramuteq %||% NA_integer_,
    "]"
  )
}

.ligne_erreur_discrimination_simple <- function(candidate, error_message) {
  data.frame(
    configuration_id = candidate$id %||% NA_character_,
    configuration_label = .resume_configuration_discrimination_simple(candidate),
    profil_morpho = candidate$profil_morpho %||% NA_character_,
    lexique_utiliser_lemmes = ifelse(isTRUE(candidate$lexique_utiliser_lemmes), "oui", "non"),
    retirer_stopwords = ifelse(isTRUE(candidate$retirer_stopwords), "oui", "non"),
    supprimer_ponctuation = ifelse(isTRUE(candidate$supprimer_ponctuation), "oui", "non"),
    supprimer_chiffres = ifelse(isTRUE(candidate$supprimer_chiffres), "oui", "non"),
    min_docfreq = candidate$min_docfreq %||% NA_integer_,
    mincl_mode = candidate$config$iramuteq_mincl_mode %||% "auto",
    mincl = suppressWarnings(as.integer(candidate$config$iramuteq_mincl %||% NA_integer_)),
    k_max_explore = candidate$k_max_explore %||% candidate$config$k_iramuteq %||% NA_integer_,
    n_segments = NA_integer_,
    n_formes = NA_integer_,
    k_retenu = NA_integer_,
    k_chd_retenu = NA_integer_,
    S = NA_real_,
    distance_classes_afc = NA_real_,
    score_mode = normaliser_mode_score_discrimination_simple_iramuteq(candidate$config$iramuteq_discrimination_simple_score_mode),
    score_label = etiquette_mode_score_discrimination_simple_iramuteq(candidate$config$iramuteq_discrimination_simple_score_mode),
    score_selection = NA_real_,
    classes_effectifs = NA_character_,
    classes_pourcentages = NA_character_,
    selection = "echec",
    erreur = as.character(error_message %||% ""),
    stringsAsFactors = FALSE
  )
}

.ligne_succes_discrimination_simple <- function(candidate, pipeline_obj, res_ira) {
  if (is.null(res_ira$auto_selection) || !is.data.frame(res_ira$auto_selection$selected_metrics) || !nrow(res_ira$auto_selection$selected_metrics)) {
    stop("Auto discriminante : la configuration ne renvoie aucune selection exploitable.")
  }

  selected_metrics <- res_ira$auto_selection$selected_metrics[1, , drop = FALSE]
  metric_value <- function(name, default = NA) {
    if (!name %in% names(selected_metrics) || !length(selected_metrics[[name]])) return(default)
    selected_metrics[[name]][[1]] %||% default
  }
  score_mode <- normaliser_mode_score_discrimination_simple_iramuteq(
    metric_value("score_mode", candidate$config$iramuteq_discrimination_simple_score_mode)
  )
  score_selection <- suppressWarnings(as.numeric(metric_value("score_selection", metric_value("S", NA_real_))))

  data.frame(
    configuration_id = candidate$id %||% NA_character_,
    configuration_label = .resume_configuration_discrimination_simple(candidate),
    profil_morpho = candidate$profil_morpho %||% NA_character_,
    lexique_utiliser_lemmes = ifelse(isTRUE(candidate$lexique_utiliser_lemmes), "oui", "non"),
    retirer_stopwords = ifelse(isTRUE(candidate$retirer_stopwords), "oui", "non"),
    supprimer_ponctuation = ifelse(isTRUE(candidate$supprimer_ponctuation), "oui", "non"),
    supprimer_chiffres = ifelse(isTRUE(candidate$supprimer_chiffres), "oui", "non"),
    min_docfreq = candidate$min_docfreq %||% NA_integer_,
    mincl_mode = candidate$config$iramuteq_mincl_mode %||% "auto",
    mincl = suppressWarnings(as.integer(res_ira$mincl %||% candidate$config$iramuteq_mincl %||% NA_integer_)),
    k_max_explore = candidate$k_max_explore %||% candidate$config$k_iramuteq %||% NA_integer_,
    n_segments = suppressWarnings(as.integer(quanteda::ndoc(pipeline_obj$dfm_obj))),
    n_formes = suppressWarnings(as.integer(quanteda::nfeat(pipeline_obj$dfm_obj))),
    k_retenu = suppressWarnings(as.integer(res_ira$auto_selection$k_selected %||% selected_metrics$k[[1]])),
    k_chd_retenu = suppressWarnings(as.integer(res_ira$auto_selection$k_chd_selected %||% selected_metrics$etape_chd[[1]] %||% selected_metrics$k[[1]])),
    S = suppressWarnings(as.numeric(metric_value("S", NA_real_))),
    distance_classes_afc = suppressWarnings(as.numeric(metric_value("distance_classes_afc", NA_real_))),
    score_mode = score_mode,
    score_label = as.character(metric_value("score_label", etiquette_mode_score_discrimination_simple_iramuteq(score_mode))),
    score_selection = score_selection,
    classes_effectifs = as.character(metric_value("classes_effectifs", "")),
    classes_pourcentages = as.character(metric_value("classes_pourcentages", "")),
    selection = "testee",
    erreur = "",
    stringsAsFactors = FALSE
  )
}

selection_configuration_discrimination_simple_iramuteq <- function(config_base,
                                                                   preparer_pipeline_fn,
                                                                   lancer_discrimination_simple_fn,
                                                                   log_fn = NULL) {
  if (!is.list(config_base)) {
    stop("Auto discriminante : config_base doit etre une liste.")
  }
  if (!is.function(preparer_pipeline_fn)) {
    stop("Auto discriminante : preparer_pipeline_fn doit etre une fonction.")
  }
  if (!is.function(lancer_discrimination_simple_fn)) {
    stop("Auto discriminante : lancer_discrimination_simple_fn doit etre une fonction.")
  }

  score_mode <- normaliser_mode_score_discrimination_simple_iramuteq(
    config_base$iramuteq_discrimination_simple_score_mode
  )
  score_label <- etiquette_mode_score_discrimination_simple_iramuteq(score_mode)

  grid_obj <- construire_grille_discrimination_simple_iramuteq(config_base)
  candidates <- grid_obj$candidates %||% list()
  search_profile <- grid_obj$profile %||% "complet"
  search_profile_label <- grid_obj$profile_label %||% .label_profil_exploration_discrimination_simple(search_profile)
  total_candidates <- length(candidates)
  if (!length(candidates)) {
    stop("Auto discriminante : aucune configuration candidate n'a ete construite.")
  }

  if (is.function(log_fn)) {
    log_fn(
      paste0(
        "Auto discriminante : profil ",
        tolower(search_profile_label),
        " - recherche sur ",
        total_candidates,
        " configurations ; critere = ",
        score_label,
        "."
      ),
      progress = 45
    )
  }

  evaluation_rows <- vector("list", total_candidates)
  evaluation_details <- vector("list", total_candidates)
  best_idx <- NA_integer_
  pipeline_cache <- new.env(parent = emptyenv())
  chd_cache <- new.env(parent = emptyenv())
  cache_stats <- new.env(parent = emptyenv())
  cache_stats$pipeline_reused_count <- 0L
  cache_stats$chd_reused_count <- 0L

  for (i in seq_along(candidates)) {
    candidate <- candidates[[i]]
    progress_value <- 45 + floor((i / total_candidates) * 14)
    pipeline_key <- NULL
    dfm_fingerprint <- NULL
    chd_fingerprint <- NULL

    if (is.function(log_fn) && (total_candidates <= 10L || i == 1L || i == total_candidates || (i %% 10L) == 0L)) {
      log_fn(
        paste0(
        "Auto discriminante : CHD ",
          i,
          "/",
          total_candidates,
          " -> ",
          .resume_configuration_discrimination_simple(candidate)
        ),
        progress = progress_value
      )
    }

    attempt <- tryCatch(
      {
        # Dans le profil cible, seul min_docfreq modifie le DFM. Les variantes
        # de la phase 1 reutilisent donc la preparation lexicale deja construite.
        pipeline_key <- if (identical(search_profile, "ciblee")) {
          paste0("ciblee::min_docfreq=", candidate$min_docfreq %||% "")
        } else {
          paste0("configuration::", candidate$id %||% i)
        }
        if (exists(pipeline_key, envir = pipeline_cache, inherits = FALSE)) {
          cache_stats$pipeline_reused_count <- cache_stats$pipeline_reused_count + 1L
          pipeline_entry <- get(pipeline_key, envir = pipeline_cache, inherits = FALSE)
        } else {
          pipeline_obj <- preparer_pipeline_fn(candidate$config)
          if (is.null(pipeline_obj$dfm_obj)) {
            stop("DFM indisponible pour cette configuration.")
          }
          if (quanteda::ndoc(pipeline_obj$dfm_obj) < 2L || quanteda::nfeat(pipeline_obj$dfm_obj) < 2L) {
            stop("Configuration trop pauvre apres pretraitement.")
          }
          pipeline_entry <- list(
            pipeline = pipeline_obj,
            dfm_fingerprint = .empreinte_dfm_auto_chd(pipeline_obj$dfm_obj)
          )
          assign(pipeline_key, pipeline_entry, envir = pipeline_cache)
        }
        pipeline_obj <- pipeline_entry$pipeline
        dfm_fingerprint <- pipeline_entry$dfm_fingerprint

        chd_fingerprint <- paste(
          dfm_fingerprint,
          candidate$config$k_iramuteq %||% candidate$k_max_explore %||% "",
          candidate$config$iramuteq_auto_k_min %||% "",
          candidate$config$iramuteq_mincl_mode %||% "",
          candidate$config$iramuteq_mincl %||% "",
          candidate$config$iramuteq_classif_mode %||% "",
          candidate$config$iramuteq_svd_method %||% "",
          candidate$config$iramuteq_max_formes %||% "",
          candidate$config$iramuteq_stats_mode %||% "",
          candidate$config$iramuteq_discrimination_simple_score_mode %||% "afc_classes_direct",
          sep = "::"
        )
        cache_hit <- exists(chd_fingerprint, envir = chd_cache, inherits = FALSE)
        if (isTRUE(cache_hit)) {
          cache_stats$chd_reused_count <- cache_stats$chd_reused_count + 1L
          cached_attempt <- get(chd_fingerprint, envir = chd_cache, inherits = FALSE)
          if (isTRUE(cached_attempt$ok)) {
            row <- .ligne_succes_discrimination_simple(candidate, pipeline_obj, cached_attempt$res_ira)
            list(
              ok = TRUE,
              row = row,
              pipeline = pipeline_obj,
              res_ira = cached_attempt$res_ira,
              reused = TRUE,
              fingerprint = chd_fingerprint
            )
          } else {
            list(
              ok = FALSE,
              row = .ligne_erreur_discrimination_simple(candidate, cached_attempt$error_message %||% "Echec reutilise depuis le cache CHD."),
              error = cached_attempt$error,
              reused = TRUE,
              fingerprint = chd_fingerprint
            )
          }
        } else {
          res_ira <- lancer_discrimination_simple_fn(
            dfm_obj = pipeline_obj$dfm_obj,
            config_variant = candidate$config
          )

          if (is.null(res_ira$auto_selection)) {
            stop("Auto discriminante : aucune selection exploitable n'a ete retournee.")
          }

          row <- .ligne_succes_discrimination_simple(candidate, pipeline_obj, res_ira)
          assign(chd_fingerprint, list(ok = TRUE, res_ira = res_ira), envir = chd_cache)
          list(ok = TRUE, row = row, pipeline = pipeline_obj, res_ira = res_ira, reused = FALSE, fingerprint = chd_fingerprint)
        }
      },
      error = function(err) {
        if (!is.null(chd_fingerprint) && nzchar(chd_fingerprint)) {
          assign(
            chd_fingerprint,
            list(ok = FALSE, error = err, error_message = conditionMessage(err)),
            envir = chd_cache
          )
        }
        list(ok = FALSE, row = .ligne_erreur_discrimination_simple(candidate, conditionMessage(err)), error = err, reused = FALSE)
      }
    )

    evaluation_rows[[i]] <- attempt$row
    evaluation_details[[i]] <- attempt

    if (isTRUE(attempt$ok)) {
      current_row <- attempt$row
      current_score <- suppressWarnings(as.numeric(current_row$score_selection[[1]]))

      if (is.na(best_idx)) {
        best_idx <- i
      } else {
        best_row <- evaluation_rows[[best_idx]]
        best_score <- suppressWarnings(as.numeric(best_row$score_selection[[1]]))
        current_k <- suppressWarnings(as.integer(current_row$k_retenu[[1]]))
        best_k <- suppressWarnings(as.integer(best_row$k_retenu[[1]]))
        current_etape <- suppressWarnings(as.integer(current_row$k_chd_retenu[[1]]))
        best_etape <- suppressWarnings(as.integer(best_row$k_chd_retenu[[1]]))
        current_score <- ifelse(is.finite(current_score), current_score, -Inf)
        best_score <- ifelse(is.finite(best_score), best_score, -Inf)
        current_k <- ifelse(is.finite(current_k), current_k, Inf)
        best_k <- ifelse(is.finite(best_k), best_k, Inf)
        current_etape <- ifelse(is.finite(current_etape), current_etape, Inf)
        best_etape <- ifelse(is.finite(best_etape), best_etape, Inf)

        # Le critere choisi est prioritaire. En cas d'egalite, on prefere une solution avec
        # moins de classes, puis une etape CHD plus courte.
        if (
          current_score > best_score + 1e-12 ||
          (abs(current_score - best_score) <= 1e-12 &&
             (current_k < best_k ||
              (current_k == best_k && current_etape < best_etape)))
        ) {
          best_idx <- i
        }
      }
    }
  }

  if (is.na(best_idx)) {
    stop("Auto discriminante : aucune configuration n'a produit de CHD exploitable.")
  }

  metrics_df <- do.call(rbind, evaluation_rows)
  metrics_df$selection <- ifelse(seq_len(nrow(metrics_df)) == best_idx, "retenue", metrics_df$selection)

  best_detail <- evaluation_details[[best_idx]]
  best_row <- metrics_df[best_idx, , drop = FALSE]
  if (is.function(log_fn)) {
    log_fn(
      paste0(
        "Auto discriminante : ",
        length(ls(pipeline_cache)),
        " DFM uniques calculees, ",
        cache_stats$pipeline_reused_count,
        " configuration(s) ont reutilise leur DFM ; ",
        length(ls(chd_cache)),
        " CHD ont ete lancees."
      ),
      progress = 58
    )
    log_fn(
      paste0(
        "Auto discriminante : configuration retenue -> ",
        best_row$configuration_label[[1]],
        " | classes retenues=",
        best_row$k_retenu[[1]],
        " | ",
        score_label,
        "=",
        format(round(as.numeric(best_row$score_selection[[1]]), 4), nsmall = 4, trim = TRUE),
        " | min_docfreq=",
        best_row$min_docfreq[[1]],
        " | mincl=",
        best_row$mincl[[1]]
      ),
      progress = 59
    )
  }

  list(
    mode = "discrimination_simple",
    score_mode = score_mode,
    score_label = score_label,
    search_profile = search_profile,
    search_profile_label = search_profile_label,
    total_configurations = total_candidates,
    successful_configurations = sum(metrics_df$selection != "echec", na.rm = TRUE),
    unique_dfm_tested = length(ls(pipeline_cache)),
    reused_configurations = cache_stats$pipeline_reused_count,
    unique_chd_tested = length(ls(chd_cache)),
    reused_chd_configurations = cache_stats$chd_reused_count,
    k_min_requested = best_detail$res_ira$auto_selection$k_min_requested %||% NA_integer_,
    k_max_requested = best_detail$res_ira$auto_selection$k_max_requested %||% NA_integer_,
    evaluation = metrics_df,
    selected_index = best_idx,
    selected_metrics = best_row,
    selected_candidate = candidates[[best_idx]],
    selected_pipeline = best_detail$pipeline,
    selected_result = best_detail$res_ira
  )
}

tracer_scores_discrimination_simple_iramuteq <- function(metrics_df,
                                                         selected_id = NULL,
                                                         top_n = 12L,
                                                         score_column = "score_selection",
                                                         score_label = "Distance directe des classes AFC") {
  if (is.null(metrics_df) || !is.data.frame(metrics_df) || !nrow(metrics_df)) {
    plot.new()
    text(0.5, 0.5, "Aucune configuration Auto discriminante a afficher.", cex = 1.0)
    return(invisible(NULL))
  }

  score_column <- as.character(score_column %||% "score_selection")[[1]]
  if (!score_column %in% names(metrics_df)) score_column <- "S"
  df <- metrics_df
  df$score_num <- suppressWarnings(as.numeric(df[[score_column]]))
  df <- df[is.finite(df$score_num) & !is.na(df$score_num), , drop = FALSE]
  if (!nrow(df)) {
    plot.new()
    text(0.5, 0.5, "Les scores Auto discriminante sont indisponibles.", cex = 1.0)
    return(invisible(NULL))
  }

  top_n <- .as_int_auto_chd(top_n, default = 12L, min_value = 1L)
  df <- df[order(df$score_num, decreasing = TRUE), , drop = FALSE]
  df <- utils::head(df, top_n)

  labels <- as.character(df$configuration_id)
  values <- df$score_num
  cols <- rep("#9cb7dc", length(values))
  if (!is.null(selected_id) && length(selected_id)) {
    idx_selected <- which(labels == as.character(selected_id[[1]]))
    if (length(idx_selected)) cols[idx_selected[[1]]] <- "#d96b4d"
  }

  old_par <- graphics::par(no.readonly = TRUE)
  on.exit(graphics::par(old_par), add = TRUE)
  graphics::par(mar = c(6, 10, 4, 2))

  bar_pos <- graphics::barplot(
    rev(values),
    horiz = TRUE,
    col = rev(cols),
    border = NA,
    las = 1,
    names.arg = rev(labels),
    xlab = score_label,
    main = "Configurations aux classes les plus separees sur l'AFC"
  )
  graphics::grid(col = "#d6c8b8", lty = "dotted")

  selected_idx <- if (!is.null(selected_id) && length(selected_id)) which(labels == as.character(selected_id[[1]])) else integer(0)
  if (length(selected_idx)) {
    graphics::text(
      x = rev(values)[length(values) - selected_idx[[1]] + 1L],
      y = bar_pos[length(values) - selected_idx[[1]] + 1L],
      labels = " retenue",
      pos = 4,
      col = "#5f1a18",
      xpd = NA
    )
  }

  invisible(NULL)
}

.preparer_metrics_export_discrimination_simple <- function(metrics_df) {
  if (is.null(metrics_df) || !is.data.frame(metrics_df) || !nrow(metrics_df)) {
    return(data.frame(stringsAsFactors = FALSE))
  }

  col <- function(name, default = NA) {
    if (name %in% names(metrics_df)) metrics_df[[name]] else rep(default, nrow(metrics_df))
  }

  score_mode <- as.character(col("score_mode", "s_lexical"))
  score_mode[is.na(score_mode) | !nzchar(score_mode)] <- "s_lexical"
  score_mode <- vapply(score_mode, normaliser_mode_score_discrimination_simple_iramuteq, character(1))
  score_label <- as.character(col("score_label", NA_character_))
  missing_score_label <- is.na(score_label) | !nzchar(score_label)
  score_label[missing_score_label] <- vapply(
    score_mode[missing_score_label],
    etiquette_mode_score_discrimination_simple_iramuteq,
    character(1)
  )
  score_s_lexical <- suppressWarnings(as.numeric(col("S", NA_real_)))
  distance_classes_afc <- suppressWarnings(as.numeric(col("distance_classes_afc", NA_real_)))
  score_selection <- suppressWarnings(as.numeric(col("score_selection", NA_real_)))
  score_selection[!is.finite(score_selection) | is.na(score_selection)] <- score_s_lexical[!is.finite(score_selection) | is.na(score_selection)]

  data.frame(
    configuration_id = col("configuration_id", NA_character_),
    profil_morpho = col("profil_morpho", NA_character_),
    lexique_utiliser_lemmes = col("lexique_utiliser_lemmes", NA_character_),
    retirer_stopwords = col("retirer_stopwords", NA_character_),
    supprimer_ponctuation = col("supprimer_ponctuation", NA_character_),
    supprimer_chiffres = col("supprimer_chiffres", NA_character_),
    min_docfreq = suppressWarnings(as.integer(col("min_docfreq", NA_integer_))),
    mincl_mode = col("mincl_mode", NA_character_),
    mincl = suppressWarnings(as.integer(col("mincl", NA_integer_))),
    k_max_explore = suppressWarnings(as.integer(col("k_max_explore", NA_integer_))),
    n_segments = suppressWarnings(as.integer(col("n_segments", NA_integer_))),
    n_formes = suppressWarnings(as.integer(col("n_formes", NA_integer_))),
    classes_retenues = suppressWarnings(as.integer(col("k_retenu", NA_integer_))),
    k_chd_retenu = suppressWarnings(as.integer(col("k_chd_retenu", NA_integer_))),
    score_mode = score_mode,
    score_label = score_label,
    score_s_lexical = score_s_lexical,
    distance_classes_afc = distance_classes_afc,
    score_selection = score_selection,
    separation_afc = score_selection,
    classes_effectifs = col("classes_effectifs", NA_character_),
    classes_pourcentages = col("classes_pourcentages", NA_character_),
    selection = col("selection", NA_character_),
    erreur = col("erreur", NA_character_),
    stringsAsFactors = FALSE
  )
}

exporter_discrimination_simple_iramuteq <- function(selection_obj,
                                                     output_dir,
                                                     mots_reperes_axes = NULL) {
  if (is.null(selection_obj) || !is.list(selection_obj)) {
    stop("Auto discriminante : objet de selection manquant.")
  }
  if (is.null(output_dir) || !nzchar(output_dir)) {
    stop("Auto discriminante : dossier de sortie manquant.")
  }

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  metrics_df <- selection_obj$evaluation
  selected_df <- selection_obj$selected_metrics
  metrics_public_df <- .preparer_metrics_export_discrimination_simple(metrics_df)
  selected_public_df <- .preparer_metrics_export_discrimination_simple(selected_df)
  manual_replay_config <- selection_obj$selected_candidate$config %||% list()
  manual_replay_k <- suppressWarnings(as.integer(
    selection_obj$selected_result$auto_selection$k_chd_selected %||%
      selected_df$k_chd_retenu[[1]] %||%
      selected_df$k_retenu[[1]]
  ))
  if (!length(manual_replay_k) || is.na(manual_replay_k) || !is.finite(manual_replay_k)) {
    manual_replay_k <- NULL
  }
  manual_replay_config$iramuteq_classes_mode <- "manuel"
  if (!is.null(manual_replay_k)) {
    manual_replay_config$k_iramuteq <- manual_replay_k
  }
  manual_replay_config$iramuteq_discrimination_simple_profile <- NULL
  manual_replay_config$iramuteq_discrimination_simple_vary_mincl <- NULL
  manual_replay_config$iramuteq_discrimination_simple_mincl_min <- NULL
  manual_replay_config$iramuteq_discrimination_simple_mincl_max <- NULL
  manual_replay_config$iramuteq_discrimination_simple_vary_min_docfreq <- NULL
  manual_replay_config$iramuteq_discrimination_simple_min_docfreq_min <- NULL
  manual_replay_config$iramuteq_discrimination_simple_min_docfreq_max <- NULL
  manual_replay_config$iramuteq_discrimination_simple_vary_k_max <- NULL
  manual_replay_config$iramuteq_discrimination_simple_k_max_min <- NULL
  manual_replay_config$iramuteq_discrimination_simple_k_max_max <- NULL
  manual_replay_config$iramuteq_discrimination_simple_score_mode <- NULL
  summary_json <- file.path(output_dir, "discrimination_simple_summary.json")
  metrics_csv <- file.path(output_dir, "discrimination_simple_metrics.csv")
  score_png <- file.path(output_dir, "discrimination_simple_score.png")

  .write_metrics_csv_auto_chd(metrics_public_df, metrics_csv)

  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Auto discriminante : le package jsonlite est requis pour exporter le resume JSON.")
  }

  axis_terms <- if (is.null(mots_reperes_axes)) {
    selection_obj$selected_result$auto_selection$selected_mots_reperes_axes
  } else {
    mots_reperes_axes
  }

  payload <- list(
    mode = "discrimination_simple",
    score_mode = selection_obj$score_mode %||% "afc_classes_direct",
    score_label = selection_obj$score_label %||% etiquette_mode_score_discrimination_simple_iramuteq(selection_obj$score_mode),
    search_profile = selection_obj$search_profile %||% "complet",
    search_profile_label = selection_obj$search_profile_label %||% .label_profil_exploration_discrimination_simple(selection_obj$search_profile %||% "complet"),
    total_configurations = selection_obj$total_configurations %||% NA_integer_,
    successful_configurations = selection_obj$successful_configurations %||% NA_integer_,
    unique_dfm_tested = selection_obj$unique_dfm_tested %||% NA_integer_,
    reused_configurations = selection_obj$reused_configurations %||% NA_integer_,
    unique_chd_tested = selection_obj$unique_chd_tested %||% NA_integer_,
    reused_chd_configurations = selection_obj$reused_chd_configurations %||% NA_integer_,
    k_min_requested = selection_obj$k_min_requested %||% NA_integer_,
    k_max_requested = selection_obj$k_max_requested %||% NA_integer_,
    manual_replay_config = manual_replay_config,
    selected_termes_cibles = as.list(as.character(selection_obj$selected_result$auto_selection$selected_termes_cibles %||% character(0))),
    selected_termes_cibles_par_classe = stats::setNames(
      lapply(selection_obj$selected_result$auto_selection$selected_termes_cibles_par_classe %||% list(), function(terms) {
        as.list(as.character(terms %||% character(0)))
      }),
      names(selection_obj$selected_result$auto_selection$selected_termes_cibles_par_classe %||% list())
    ),
    selected_mots_reperes_axes = {
      if (is.data.frame(axis_terms) && nrow(axis_terms)) {
        lapply(seq_len(nrow(axis_terms)), function(index) {
          .dataframe_row_to_list_auto_chd(axis_terms[index, , drop = FALSE])
        })
      } else {
        list()
      }
    },
    selected = if (!is.null(selected_public_df) && nrow(selected_public_df)) {
      .dataframe_row_to_list_auto_chd(selected_public_df[1, , drop = FALSE])
    } else {
      NULL
    },
    metrics = lapply(seq_len(nrow(metrics_public_df)), function(i) {
      .dataframe_row_to_list_auto_chd(metrics_public_df[i, , drop = FALSE])
    })
  )
  jsonlite::write_json(payload, summary_json, auto_unbox = TRUE, pretty = TRUE, null = "null")

  grDevices::png(score_png, width = 1800, height = 1200, res = 180)
  tracer_scores_discrimination_simple_iramuteq(
    metrics_df,
    selected_id = selected_df$configuration_id %||% NULL,
    score_column = selection_obj$score_column %||% "score_selection",
    score_label = selection_obj$score_label %||% "Distance directe des classes AFC"
  )
  grDevices::dev.off()

  list(
    metrics_csv = metrics_csv,
    summary_json = summary_json,
    score_png = score_png
  )
}
