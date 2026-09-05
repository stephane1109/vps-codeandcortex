# Role du fichier: discriminationsimple.R ajoute un mode de discrimination
# volontairement plus simple. Le choix final repose uniquement sur les mots
# significatifs de la CHD, leur chi2, et leurs coordonnees x/y sur l'AFC.

if (!exists("%||%", mode = "function", inherits = TRUE)) {
  `%||%` <- function(x, y) {
    if (is.null(x) || length(x) == 0) y else x
  }
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
    S_distance_min = 0,
    S_distance_moyenne = 0,
    poles_by_class = NULL,
    distances_by_pair = numeric(0),
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
    termes_par_classe[[class_label]] <- unique(as.character(df_cl$Terme))
  }

  if (length(poles_by_class) < 2L) {
    empty_result$termes_cibles <- unique(as.character(top_rows$Terme))
    empty_result$termes_cibles_par_classe <- termes_par_classe
    return(empty_result)
  }

  poles_matrix <- do.call(rbind, lapply(poles_by_class, function(vec) c(x = vec[["x"]], y = vec[["y"]])))
  rownames(poles_matrix) <- names(poles_by_class)

  # On compare toutes les paires de centres de classes sur les axes x et y.
  # La distance minimale protege contre une solution ou deux classes restent proches.
  pair_index <- utils::combn(seq_len(nrow(poles_matrix)), 2L)
  distances_brutes <- vapply(seq_len(ncol(pair_index)), function(index) {
    point_a <- poles_matrix[pair_index[1L, index], ]
    point_b <- poles_matrix[pair_index[2L, index], ]
    sqrt(sum((point_a - point_b)^2))
  }, numeric(1))

  term_norms <- sqrt(rowSums(coords_termes[, c("x", "y"), drop = FALSE]^2))
  max_term_radius <- suppressWarnings(max(term_norms, na.rm = TRUE))
  if (!is.finite(max_term_radius) || is.na(max_term_radius) || max_term_radius <= 0) {
    max_term_radius <- 1
  }
  distances_norm <- pmin(1, pmax(0, distances_brutes / (2 * max_term_radius)))
  s_distance_min <- .borner_score_auto_chd(min(distances_norm))
  s_distance_moyenne <- .borner_score_auto_chd(mean(distances_norm))

  list(
    S = s_distance_min,
    S_distance_min = s_distance_min,
    S_distance_moyenne = s_distance_moyenne,
    poles_by_class = poles_matrix,
    distances_by_pair = distances_norm,
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
                                                             afc_max_termes = 400L) {
  stats_mode <- match.arg(stats_mode)
  if (is.null(partition_obj) || is.null(partition_obj$classes)) {
    stop("Discrimination simple: solution en classes invalide.")
  }

  classes <- suppressWarnings(as.integer(partition_obj$classes))
  ok <- is.finite(classes) & !is.na(classes) & classes > 0L
  counts <- table(classes[ok])
  total_assigned <- sum(counts)
  pct <- if (total_assigned > 0) 100 * counts / total_assigned else counts

  fn_stats <- get0("construire_stats_classes_iramuteq", mode = "function", inherits = TRUE)
  if (!is.function(fn_stats)) {
    stop("Discrimination simple: construire_stats_classes_iramuteq() est introuvable.")
  }
  fn_afc <- get0("executer_afc_classes", mode = "function", inherits = TRUE)
  if (!is.function(fn_afc)) {
    stop("Discrimination simple: executer_afc_classes() est introuvable.")
  }

  res_stats_df <- fn_stats(
    dfm_obj = dfm_obj,
    classes = classes,
    max_p = 1,
    stats_mode = stats_mode
  )

  h_value <- calculer_homogeneite_auto_chd(dfm_obj, classes)
  d_value <- calculer_distinction_auto_chd(dfm_obj, classes)
  diffusion <- calculer_diffusion_auto_chd(
    dfm_obj = dfm_obj,
    classes = classes,
    stats_mode = stats_mode,
    top_n = top_n_diffusion,
    p_seuil = p_seuil,
    res_stats_df = res_stats_df
  )
  l_value <- diffusion$value
  b_value <- .borner_score_auto_chd(mean(c(h_value, d_value, l_value)))

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

  simple_scores <- calculer_score_discrimination_simple_iramuteq(
    afc_obj = afc_obj,
    res_stats_df = res_stats_df,
    top_n = top_n_afc,
    p_seuil = p_seuil
  )

  metrics <- data.frame(
    partition = paste0("P", partition_obj$k),
    k = as.integer(partition_obj$k),
    n_segments_assignes = as.integer(total_assigned),
    n_segments_non_assignes = as.integer(sum(!ok)),
    H = .borner_score_auto_chd(h_value),
    D = .borner_score_auto_chd(d_value),
    L = .borner_score_auto_chd(l_value),
    B = .borner_score_auto_chd(b_value),
    S = .borner_score_auto_chd(simple_scores$S),
    S_distance_min = .borner_score_auto_chd(simple_scores$S_distance_min),
    S_distance_moyenne = .borner_score_auto_chd(simple_scores$S_distance_moyenne),
    classes_effectifs = .formatter_resume_classes_auto_chd(counts, digits = 0L),
    classes_pourcentages = .formatter_resume_classes_auto_chd(pct, digits = 2L, suffix = "%"),
    stringsAsFactors = FALSE
  )

  list(
    partition = partition_obj,
    metrics = metrics,
    stats = res_stats_df,
    diffusion_by_class = diffusion$by_class,
    afc = afc_obj,
    termes_cibles = unique(as.character(simple_scores$termes_cibles %||% termes_cibles)),
    termes_cibles_par_classe = if (length(simple_scores$termes_cibles_par_classe)) simple_scores$termes_cibles_par_classe else termes_cibles_par_classe,
    simple_distances_by_pair = simple_scores$distances_by_pair,
    simple_poles = simple_scores$poles_by_class
  )
}

selection_discrimination_simple_classes_iramuteq <- function(chd_obj,
                                                             dfm_obj,
                                                             k_min = NULL,
                                                             k_max = NULL,
                                                             stats_mode = c("vectorise", "classique"),
                                                             top_n_diffusion = 20L,
                                                             top_n_afc = NULL,
                                                             p_seuil = 0.05,
                                                             afc_max_termes = 400L) {
  stats_mode <- match.arg(stats_mode)

  partitions <- lister_partitions_chd_iramuteq(chd_obj, k_min = k_min, k_max = k_max)
  if (!length(partitions)) {
    stop("Discrimination simple: aucune solution exploitable entre 3 classes et la borne maximale demandee.")
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
      afc_max_termes = afc_max_termes
    )
  })

  metrics_df <- do.call(rbind, lapply(evaluations, `[[`, "metrics"))
  metrics_df$G <- NA_real_
  metrics_df$GS <- NA_real_

  if (nrow(metrics_df) > 1L) {
    b_values <- suppressWarnings(as.numeric(metrics_df$B))
    s_values <- suppressWarnings(as.numeric(metrics_df$S))
    gains_b <- rep(NA_real_, length(b_values))
    gains_s <- rep(NA_real_, length(s_values))
    gains_b[-1L] <- b_values[-1L] - b_values[-length(b_values)]
    gains_s[-1L] <- s_values[-1L] - s_values[-length(s_values)]
    metrics_df$G <- gains_b
    metrics_df$GS <- gains_s
  }

  s_values <- suppressWarnings(as.numeric(metrics_df$S))
  s_distance_moyenne_values <- suppressWarnings(as.numeric(metrics_df$S_distance_moyenne))
  s_scores <- ifelse(is.finite(s_values) & !is.na(s_values), s_values, -Inf)
  if (!any(is.finite(s_scores) & s_scores > -Inf)) {
    stop("Discrimination simple: aucun score simple exploitable n'a pu etre calcule.")
  }

  selected_idx <- which.max(s_scores)
  if (length(selected_idx) > 1L) {
    selected_idx <- selected_idx[[1]]
  }
  for (idx in seq_len(nrow(metrics_df))) {
    if (idx == selected_idx) next
    better_s <- is.finite(s_values[[idx]]) && is.finite(s_values[[selected_idx]]) && (s_values[[idx]] > s_values[[selected_idx]] + 1e-12)
    equal_s <- is.finite(s_values[[idx]]) && is.finite(s_values[[selected_idx]]) && abs(s_values[[idx]] - s_values[[selected_idx]]) <= 1e-12
    better_distance_moyenne <- is.finite(s_distance_moyenne_values[[idx]]) && (!is.finite(s_distance_moyenne_values[[selected_idx]]) || s_distance_moyenne_values[[idx]] > s_distance_moyenne_values[[selected_idx]] + 1e-12)

    if (better_s || (equal_s && better_distance_moyenne)) {
      selected_idx <- idx
    }
  }

  metrics_df$selection <- ifelse(seq_len(nrow(metrics_df)) == selected_idx, "oui", "non")

  selected_partition <- partitions[[selected_idx]]
  selected_evaluation <- evaluations[[selected_idx]]
  k_max_tested <- suppressWarnings(max(as.integer(metrics_df$k), na.rm = TRUE))
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
  k_min_tested <- suppressWarnings(min(as.integer(metrics_df$k), na.rm = TRUE))
  if (!is.finite(selected_partition$k) || is.na(selected_partition$k) || selected_partition$k < k_min_requested) {
    stop(paste0(
      "Discrimination simple: la solution retenue ne respecte pas la borne minimale demandee (",
      k_min_requested,
      " classes reelles minimum)."
    ))
  }

  list(
    mode = "discrimination_simple",
    mode_label = "Discrimination simple",
    score_column = "S",
    score_label = "Distance minimale AFC entre classes",
    score_plot_title = "Selection de la configuration aux classes les plus separees",
    classes = selected_partition$classes,
    classes_raw = selected_partition$classes_raw,
    terminales = selected_partition$terminales,
    k_selected = as.integer(metrics_df$k[[selected_idx]]),
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
    selected_simple_distances_by_pair = selected_evaluation$simple_distances_by_pair,
    selected_simple_poles = selected_evaluation$simple_poles,
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
    " | min_docfreq=",
    candidate$min_docfreq %||% NA_integer_,
    " | kmax=",
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
    k_max_explore = candidate$k_max_explore %||% candidate$config$k_iramuteq %||% NA_integer_,
    n_segments = NA_integer_,
    n_formes = NA_integer_,
    k_retenu = NA_integer_,
    S = NA_real_,
    S_distance_min = NA_real_,
    S_distance_moyenne = NA_real_,
    classes_effectifs = NA_character_,
    classes_pourcentages = NA_character_,
    selection = "echec",
    erreur = as.character(error_message %||% ""),
    stringsAsFactors = FALSE
  )
}

.ligne_succes_discrimination_simple <- function(candidate, pipeline_obj, res_ira) {
  if (is.null(res_ira$auto_selection) || !is.data.frame(res_ira$auto_selection$selected_metrics) || !nrow(res_ira$auto_selection$selected_metrics)) {
    stop("Discrimination simple: la configuration ne renvoie aucune selection exploitable.")
  }

  selected_metrics <- res_ira$auto_selection$selected_metrics[1, , drop = FALSE]

  data.frame(
    configuration_id = candidate$id %||% NA_character_,
    configuration_label = .resume_configuration_discrimination_simple(candidate),
    profil_morpho = candidate$profil_morpho %||% NA_character_,
    lexique_utiliser_lemmes = ifelse(isTRUE(candidate$lexique_utiliser_lemmes), "oui", "non"),
    retirer_stopwords = ifelse(isTRUE(candidate$retirer_stopwords), "oui", "non"),
    supprimer_ponctuation = ifelse(isTRUE(candidate$supprimer_ponctuation), "oui", "non"),
    supprimer_chiffres = ifelse(isTRUE(candidate$supprimer_chiffres), "oui", "non"),
    min_docfreq = candidate$min_docfreq %||% NA_integer_,
    k_max_explore = candidate$k_max_explore %||% candidate$config$k_iramuteq %||% NA_integer_,
    n_segments = suppressWarnings(as.integer(quanteda::ndoc(pipeline_obj$dfm_obj))),
    n_formes = suppressWarnings(as.integer(quanteda::nfeat(pipeline_obj$dfm_obj))),
    k_retenu = suppressWarnings(as.integer(res_ira$auto_selection$k_selected %||% selected_metrics$k[[1]])),
    S = .borner_score_auto_chd(selected_metrics$S[[1]]),
    S_distance_min = .borner_score_auto_chd(selected_metrics$S_distance_min[[1]]),
    S_distance_moyenne = .borner_score_auto_chd(selected_metrics$S_distance_moyenne[[1]]),
    classes_effectifs = as.character(selected_metrics$classes_effectifs[[1]] %||% ""),
    classes_pourcentages = as.character(selected_metrics$classes_pourcentages[[1]] %||% ""),
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
    stop("Discrimination simple: config_base doit etre une liste.")
  }
  if (!is.function(preparer_pipeline_fn)) {
    stop("Discrimination simple: preparer_pipeline_fn doit etre une fonction.")
  }
  if (!is.function(lancer_discrimination_simple_fn)) {
    stop("Discrimination simple: lancer_discrimination_simple_fn doit etre une fonction.")
  }

  grid_obj <- construire_grille_auto_discriminante_iramuteq(config_base)
  candidates <- grid_obj$candidates %||% list()
  search_profile <- grid_obj$profile %||% "complet"
  search_profile_label <- grid_obj$profile_label %||% .label_profil_exploration_auto_discriminante(search_profile)
  total_candidates <- length(candidates)
  if (!length(candidates)) {
    stop("Discrimination simple: aucune configuration candidate n'a ete construite.")
  }

  if (is.function(log_fn)) {
    log_fn(
      paste0(
        "Discrimination simple : profil ",
        tolower(search_profile_label),
        " - recherche sur ",
        total_candidates,
        " configurations."
      ),
      progress = 45
    )
  }

  evaluation_rows <- vector("list", total_candidates)
  evaluation_details <- vector("list", total_candidates)
  best_idx <- NA_integer_
  dfm_cache <- new.env(parent = emptyenv())
  reused_count <- 0L

  for (i in seq_along(candidates)) {
    candidate <- candidates[[i]]
    progress_value <- 45 + floor((i / total_candidates) * 14)
    dfm_fingerprint <- NULL

    if (is.function(log_fn) && (total_candidates <= 10L || i == 1L || i == total_candidates || (i %% 10L) == 0L)) {
      log_fn(
        paste0(
          "Discrimination simple : CHD ",
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
        pipeline_obj <- preparer_pipeline_fn(candidate$config)
        if (is.null(pipeline_obj$dfm_obj)) {
          stop("DFM indisponible pour cette configuration.")
        }
        if (quanteda::ndoc(pipeline_obj$dfm_obj) < 2L || quanteda::nfeat(pipeline_obj$dfm_obj) < 2L) {
          stop("Configuration trop pauvre apres pretraitement.")
        }

        dfm_fingerprint <- paste(
          .empreinte_dfm_auto_chd(pipeline_obj$dfm_obj),
          candidate$config$k_iramuteq %||% candidate$k_max_explore %||% "",
          candidate$config$iramuteq_auto_k_min %||% "",
          candidate$config$iramuteq_stats_mode %||% "",
          sep = "::"
        )
        cache_hit <- exists(dfm_fingerprint, envir = dfm_cache, inherits = FALSE)
        if (isTRUE(cache_hit)) {
          reused_count <<- reused_count + 1L
          cached_attempt <- get(dfm_fingerprint, envir = dfm_cache, inherits = FALSE)
          if (isTRUE(cached_attempt$ok)) {
            row <- .ligne_succes_discrimination_simple(candidate, pipeline_obj, cached_attempt$res_ira)
            list(
              ok = TRUE,
              row = row,
              pipeline = pipeline_obj,
              res_ira = cached_attempt$res_ira,
              reused = TRUE,
              fingerprint = dfm_fingerprint
            )
          } else {
            list(
              ok = FALSE,
              row = .ligne_erreur_discrimination_simple(candidate, cached_attempt$error_message %||% "Echec reutilise depuis le cache DFM."),
              error = cached_attempt$error,
              reused = TRUE,
              fingerprint = dfm_fingerprint
            )
          }
        } else {
          res_ira <- lancer_discrimination_simple_fn(
            dfm_obj = pipeline_obj$dfm_obj,
            config_variant = candidate$config
          )

          if (is.null(res_ira$auto_selection)) {
            stop("La discrimination simple n'a retourne aucune selection exploitable.")
          }

          row <- .ligne_succes_discrimination_simple(candidate, pipeline_obj, res_ira)
          assign(dfm_fingerprint, list(ok = TRUE, res_ira = res_ira), envir = dfm_cache)
          list(ok = TRUE, row = row, pipeline = pipeline_obj, res_ira = res_ira, reused = FALSE, fingerprint = dfm_fingerprint)
        }
      },
      error = function(err) {
        if (!is.null(dfm_fingerprint) && nzchar(dfm_fingerprint)) {
          assign(
            dfm_fingerprint,
            list(ok = FALSE, error = err, error_message = conditionMessage(err)),
            envir = dfm_cache
          )
        }
        list(ok = FALSE, row = .ligne_erreur_discrimination_simple(candidate, conditionMessage(err)), error = err, reused = FALSE)
      }
    )

    evaluation_rows[[i]] <- attempt$row
    evaluation_details[[i]] <- attempt

    if (isTRUE(attempt$ok)) {
      current_row <- attempt$row
      current_score <- suppressWarnings(as.numeric(current_row$S[[1]]))
      current_distance_moyenne <- suppressWarnings(as.numeric(current_row$S_distance_moyenne[[1]]))

      if (is.na(best_idx)) {
        best_idx <- i
      } else {
        best_row <- evaluation_rows[[best_idx]]
        best_score <- suppressWarnings(as.numeric(best_row$S[[1]]))
        best_distance_moyenne <- suppressWarnings(as.numeric(best_row$S_distance_moyenne[[1]]))

        if (
          (is.finite(current_score) && !is.na(current_score) && (!is.finite(best_score) || is.na(best_score) || current_score > best_score + 1e-12)) ||
          (is.finite(current_score) && is.finite(best_score) && abs(current_score - best_score) <= 1e-12 &&
             is.finite(current_distance_moyenne) && (!is.finite(best_distance_moyenne) || current_distance_moyenne > best_distance_moyenne + 1e-12))
        ) {
          best_idx <- i
        }
      }
    }
  }

  if (is.na(best_idx)) {
    stop("Discrimination simple: aucune configuration n'a produit de CHD exploitable.")
  }

  metrics_df <- do.call(rbind, evaluation_rows)
  metrics_df$selection <- ifelse(seq_len(nrow(metrics_df)) == best_idx, "retenue", metrics_df$selection)

  best_detail <- evaluation_details[[best_idx]]
  best_row <- metrics_df[best_idx, , drop = FALSE]
  if (is.function(log_fn)) {
    log_fn(
      paste0(
        "Discrimination simple : ",
        length(ls(dfm_cache)),
        " DFM uniques calculees, ",
        reused_count,
        " configuration(s) ont reutilise une DFM deja testee."
      ),
      progress = 58
    )
    log_fn(
      paste0(
        "Discrimination simple : configuration retenue -> ",
        best_row$configuration_label[[1]],
        " | classes retenues=",
        best_row$k_retenu[[1]],
        " | distance minimale AFC=",
        format(round(as.numeric(best_row$S[[1]]), 4), nsmall = 4, trim = TRUE),
        " | min_docfreq=",
        best_row$min_docfreq[[1]]
      ),
      progress = 59
    )
  }

  list(
    mode = "discrimination_simple",
    search_profile = search_profile,
    search_profile_label = search_profile_label,
    total_configurations = total_candidates,
    successful_configurations = sum(metrics_df$selection != "echec", na.rm = TRUE),
    unique_dfm_tested = length(ls(dfm_cache)),
    reused_configurations = reused_count,
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

tracer_scores_discrimination_simple_iramuteq <- function(metrics_df, selected_id = NULL, top_n = 12L) {
  if (is.null(metrics_df) || !is.data.frame(metrics_df) || !nrow(metrics_df)) {
    plot.new()
    text(0.5, 0.5, "Aucune configuration de discrimination simple a afficher.", cex = 1.0)
    return(invisible(NULL))
  }

  df <- metrics_df
  df$S_num <- suppressWarnings(as.numeric(df$S))
  df <- df[is.finite(df$S_num) & !is.na(df$S_num), , drop = FALSE]
  if (!nrow(df)) {
    plot.new()
    text(0.5, 0.5, "Les scores de discrimination simple sont indisponibles.", cex = 1.0)
    return(invisible(NULL))
  }

  top_n <- .as_int_auto_chd(top_n, default = 12L, min_value = 1L)
  df <- df[order(df$S_num, decreasing = TRUE), , drop = FALSE]
  df <- utils::head(df, top_n)

  labels <- as.character(df$configuration_id)
  values <- df$S_num
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
    xlab = "Distance minimale AFC entre classes (normalisee)",
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

  data.frame(
    configuration_id = col("configuration_id", NA_character_),
    profil_morpho = col("profil_morpho", NA_character_),
    lexique_utiliser_lemmes = col("lexique_utiliser_lemmes", NA_character_),
    retirer_stopwords = col("retirer_stopwords", NA_character_),
    supprimer_ponctuation = col("supprimer_ponctuation", NA_character_),
    supprimer_chiffres = col("supprimer_chiffres", NA_character_),
    min_docfreq = suppressWarnings(as.integer(col("min_docfreq", NA_integer_))),
    k_max_explore = suppressWarnings(as.integer(col("k_max_explore", NA_integer_))),
    n_segments = suppressWarnings(as.integer(col("n_segments", NA_integer_))),
    n_formes = suppressWarnings(as.integer(col("n_formes", NA_integer_))),
    classes_retenues = suppressWarnings(as.integer(col("k_retenu", NA_integer_))),
    distance_minimale_afc = suppressWarnings(as.numeric(
      if ("S_distance_min" %in% names(metrics_df)) col("S_distance_min") else col("S", NA_real_)
    )),
    classes_effectifs = col("classes_effectifs", NA_character_),
    classes_pourcentages = col("classes_pourcentages", NA_character_),
    selection = col("selection", NA_character_),
    erreur = col("erreur", NA_character_),
    stringsAsFactors = FALSE
  )
}

exporter_discrimination_simple_iramuteq <- function(selection_obj, output_dir) {
  if (is.null(selection_obj) || !is.list(selection_obj)) {
    stop("Discrimination simple: objet de selection manquant.")
  }
  if (is.null(output_dir) || !nzchar(output_dir)) {
    stop("Discrimination simple: dossier de sortie manquant.")
  }

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  metrics_df <- selection_obj$evaluation
  selected_df <- selection_obj$selected_metrics
  metrics_public_df <- .preparer_metrics_export_discrimination_simple(metrics_df)
  selected_public_df <- .preparer_metrics_export_discrimination_simple(selected_df)
  summary_json <- file.path(output_dir, "discrimination_simple_summary.json")
  metrics_csv <- file.path(output_dir, "discrimination_simple_metrics.csv")
  score_png <- file.path(output_dir, "discrimination_simple_score.png")

  .write_metrics_csv_auto_chd(metrics_public_df, metrics_csv)

  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Discrimination simple: le package jsonlite est requis pour exporter le resume JSON.")
  }

  payload <- list(
    mode = "discrimination_simple",
    search_profile = selection_obj$search_profile %||% "complet",
    search_profile_label = selection_obj$search_profile_label %||% .label_profil_exploration_auto_discriminante(selection_obj$search_profile %||% "complet"),
    total_configurations = selection_obj$total_configurations %||% NA_integer_,
    successful_configurations = selection_obj$successful_configurations %||% NA_integer_,
    unique_dfm_tested = selection_obj$unique_dfm_tested %||% NA_integer_,
    reused_configurations = selection_obj$reused_configurations %||% NA_integer_,
    k_min_requested = selection_obj$k_min_requested %||% NA_integer_,
    k_max_requested = selection_obj$k_max_requested %||% NA_integer_,
    selected_termes_cibles = as.list(as.character(selection_obj$selected_result$auto_selection$selected_termes_cibles %||% character(0))),
    selected_termes_cibles_par_classe = stats::setNames(
      lapply(selection_obj$selected_result$auto_selection$selected_termes_cibles_par_classe %||% list(), function(terms) {
        as.list(as.character(terms %||% character(0)))
      }),
      names(selection_obj$selected_result$auto_selection$selected_termes_cibles_par_classe %||% list())
    ),
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
  tracer_scores_discrimination_simple_iramuteq(metrics_df, selected_id = selected_df$configuration_id %||% NULL)
  grDevices::dev.off()

  list(
    metrics_csv = metrics_csv,
    summary_json = summary_json,
    score_png = score_png
  )
}
