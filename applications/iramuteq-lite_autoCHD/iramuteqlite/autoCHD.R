# Role du fichier: autoCHD.R fournit les utilitaires partages par les calculs
# automatiques utilises par Discrimination simple.
# La CHD historique n'est pas modifiee: les utilitaires reutilisent ses
# partitions successives et ses statistiques lexicales existantes.

if (!exists("%||%", mode = "function", inherits = TRUE)) {
  `%||%` <- function(x, y) {
    if (is.null(x) || length(x) == 0) y else x
  }
}

.normaliser_n1_auto_chd <- function(n1) {
  fn <- get0(".normaliser_n1_chd", mode = "function", inherits = TRUE)
  if (is.function(fn)) return(fn(n1))

  if (is.null(n1)) return(NULL)
  if (is.data.frame(n1)) n1 <- as.matrix(n1)
  if (is.vector(n1)) n1 <- matrix(as.integer(n1), ncol = 1)
  if (!is.matrix(n1)) return(NULL)
  if (nrow(n1) < 1 || ncol(n1) < 1) return(NULL)
  n1
}

.borner_score_auto_chd <- function(value) {
  value <- suppressWarnings(as.numeric(value))
  if (!length(value) || is.na(value) || !is.finite(value)) return(0)
  max(0, min(1, value[[1]]))
}

.limite_top_n_active_auto_chd <- function(top_n) {
  top_n_num <- suppressWarnings(as.integer(top_n[[1]] %||% NA))
  length(top_n_num) > 0L && is.finite(top_n_num) && !is.na(top_n_num) && top_n_num >= 1L
}

.est_erreur_limite_partition_auto_chd <- function(err) {
  msg <- tolower(trimws(conditionMessage(err) %||% ""))
  if (!nzchar(msg)) return(FALSE)

  patterns <- c(
    "too many dimensions",
    "matrice trop pauvre",
    ">=2 lignes et >=2 colonnes"
  )

  any(vapply(patterns, grepl, logical(1), x = msg, fixed = TRUE))
}

.formatter_resume_classes_auto_chd <- function(values, digits = 0L, suffix = "") {
  if (!length(values)) return("")
  labels <- names(values)
  if (is.null(labels) || !length(labels)) labels <- as.character(seq_along(values))
  parts <- vapply(seq_along(values), function(i) {
    val <- as.numeric(values[[i]])
    if (!is.finite(val) || is.na(val)) return("")
    formatted <- if (digits > 0L) {
      format(round(val, digits), nsmall = digits, trim = TRUE, scientific = FALSE)
    } else {
      as.character(as.integer(round(val)))
    }
    paste0(labels[[i]], ":", formatted, suffix)
  }, character(1))
  parts <- parts[nzchar(parts)]
  paste(parts, collapse = " | ")
}

normaliser_partition_classes_iramuteq <- function(classes_raw) {
  classes_raw <- suppressWarnings(as.integer(classes_raw))
  out <- rep.int(0L, length(classes_raw))
  ok <- is.finite(classes_raw) & !is.na(classes_raw) & classes_raw > 0L
  if (!any(ok)) return(out)

  ids <- sort(unique(classes_raw[ok]))
  for (i in seq_along(ids)) {
    out[classes_raw == ids[[i]]] <- as.integer(i)
  }
  out
}

.extraire_etape_chd_auto_chd <- function(chd_obj, column_index) {
  n1 <- .normaliser_n1_auto_chd(chd_obj$n1)
  if (is.null(n1)) stop("Discrimination simple: objet CHD invalide ou sans matrice n1.")

  column_index <- suppressWarnings(as.integer(column_index))
  if (!is.finite(column_index) || is.na(column_index) || column_index < 1L || column_index > ncol(n1)) {
    stop("Discrimination simple: etape CHD indisponible.")
  }

  list_mere <- chd_obj$list_mere
  list_fille <- chd_obj$list_fille
  if (!is.list(list_mere) || !is.list(list_fille)) {
    stop("Discrimination simple: arbre CHD incomplet.")
  }

  # Chaque colonne de n1 correspond a une etape de division. Pour reproduire
  # exactement le manuel, on tronque aussi l'arbre a cette etape avant de
  # reconstruire les classes terminales avec mincl.
  max_node <- as.integer((2L * column_index) + 1L)
  chd_step <- chd_obj
  chd_step$n1 <- n1[, seq_len(column_index), drop = FALSE]
  chd_step$list_mere <- list_mere[seq_len(min(length(list_mere), max_node))]
  chd_step$list_fille <- list_fille[seq_len(min(length(list_fille), max_node))]
  chd_step$list_fille <- lapply(chd_step$list_fille, function(children) {
    ids <- suppressWarnings(as.integer(children))
    ids <- ids[is.finite(ids) & !is.na(ids) & ids > 0L]
    if (length(ids) != 2L || any(ids > max_node)) return(NULL)
    ids
  })
  chd_step
}

.reconstruire_partition_auto_chd <- function(chd_step,
                                              mincl = 5L,
                                              mincl_mode = c("auto", "manuel"),
                                              classif_mode = c("simple", "double")) {
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  reconstruire_fn <- get0("reconstruire_classes_terminales_iramuteq", mode = "function", inherits = TRUE)
  if (!is.function(reconstruire_fn)) {
    stop("Discrimination simple: reconstruction des classes IRaMuTeQ introuvable.")
  }

  classes_obj <- reconstruire_fn(
    chd_obj = chd_step,
    mincl = mincl,
    mincl_mode = mincl_mode,
    classif_mode = classif_mode,
    nb_classes_cible = NULL,
    respecter_nb_classes = FALSE
  )

  classes <- normaliser_partition_classes_iramuteq(classes_obj$classes)
  fallback_mincl1 <- FALSE

  list(
    classes = classes,
    terminales = suppressWarnings(as.integer(classes_obj$terminales)),
    mincl = suppressWarnings(as.integer(classes_obj$mincl)),
    fallback_mincl1 = fallback_mincl1
  )
}

extraire_partition_chd_iramuteq <- function(chd_obj,
                                             k,
                                             mincl = 5L,
                                             mincl_mode = c("auto", "manuel"),
                                             classif_mode = c("simple", "double")) {
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  n1 <- .normaliser_n1_auto_chd(chd_obj$n1)
  if (is.null(n1)) stop("Discrimination simple: objet CHD invalide ou sans matrice n1.")

  k <- suppressWarnings(as.integer(k))
  if (!is.finite(k) || is.na(k) || k < 2L) {
    stop("Discrimination simple: k doit etre >= 2.")
  }

  col_index <- k - 1L
  if (col_index > ncol(n1)) {
    stop("Discrimination simple: solution en classes demandee indisponible dans n1.")
  }

  classes_chd_brutes <- suppressWarnings(as.integer(n1[, col_index]))
  chd_step <- .extraire_etape_chd_auto_chd(chd_obj, column_index = col_index)
  reconstruction <- .reconstruire_partition_auto_chd(
    chd_step = chd_step,
    mincl = mincl,
    mincl_mode = mincl_mode,
    classif_mode = classif_mode
  )
  classes <- reconstruction$classes

  list(
    k = as.integer(length(unique(classes[classes > 0L]))),
    requested_k = as.integer(k),
    column_index = as.integer(col_index),
    classes_raw = classes_chd_brutes,
    classes = classes,
    terminales = reconstruction$terminales,
    mincl = reconstruction$mincl,
    fallback_mincl1 = reconstruction$fallback_mincl1,
    chd = chd_step
  )
}

lister_partitions_chd_iramuteq <- function(chd_obj,
                                            k_min = NULL,
                                            k_max = NULL,
                                            mincl = 5L,
                                            mincl_mode = c("auto", "manuel"),
                                            classif_mode = c("simple", "double")) {
  mincl_mode <- match.arg(mincl_mode)
  classif_mode <- match.arg(classif_mode)
  n1 <- .normaliser_n1_auto_chd(chd_obj$n1)
  if (is.null(n1)) stop("Discrimination simple: objet CHD invalide ou sans matrice n1.")

  max_available <- ncol(n1) + 1L
  if (is.null(k_min) || !length(k_min) || is.na(k_min[[1]]) || !is.finite(as.numeric(k_min[[1]]))) {
    k_min_use <- 2L
  } else {
    k_min_use <- max(2L, as.integer(k_min[[1]]))
  }
  if (is.null(k_max) || !length(k_max) || is.na(k_max[[1]]) || !is.finite(as.numeric(k_max[[1]]))) {
    k_max_use <- max_available
  } else {
    k_max_use <- min(max_available, max(2L, as.integer(k_max[[1]])))
  }

  if (k_min_use > k_max_use) {
    return(list())
  }

  partitions <- lapply(seq.int(k_min_use, k_max_use), function(k) {
    extraire_partition_chd_iramuteq(
      chd_obj = chd_obj,
      k = k,
      mincl = mincl,
      mincl_mode = mincl_mode,
      classif_mode = classif_mode
    )
  })
  partitions <- Filter(function(partition_obj) {
    is.list(partition_obj) &&
      is.finite(partition_obj$k) &&
      !is.na(partition_obj$k) &&
      partition_obj$k >= k_min_use
  }, partitions)

  if (!length(partitions)) {
    return(list())
  }

  # Toutes les etapes sont conservees. Deux etapes peuvent avoir le meme
  # nombre de classes finales tout en formant des groupes differents.
  partitions
}

resoudre_borne_chd_auto_iramuteq <- function(calculer_chd_fn,
                                             dfm_obj,
                                             k_max,
                                             mode_patate = FALSE,
                                             svd_method = c("irlba", "svdR"),
                                             libsvdc_path = NULL,
                                             binariser = FALSE,
                                             rscripts_dir = NULL,
                                             max_formes = 20000L) {
  if (!is.function(calculer_chd_fn)) {
    stop("Discrimination simple: calculer_chd_fn doit etre une fonction.")
  }
  if (is.null(dfm_obj)) {
    stop("Discrimination simple: dfm_obj manquant pour la recherche de la borne maximale.")
  }

  svd_method <- match.arg(svd_method)
  k_requested <- suppressWarnings(as.integer(k_max[[1]]))
  if (!length(k_requested) || is.na(k_requested) || !is.finite(k_requested)) k_requested <- 2L
  k_requested <- max(2L, k_requested)

  reduction_reason <- NULL

  for (k_candidate in seq.int(k_requested, 2L, by = -1L)) {
    tentative <- tryCatch(
      list(
        ok = TRUE,
        value = calculer_chd_fn(
          dfm_obj = dfm_obj,
          k = k_candidate,
          mode_patate = mode_patate,
          svd_method = svd_method,
          libsvdc_path = libsvdc_path,
          binariser = binariser,
          rscripts_dir = rscripts_dir,
          max_formes = max_formes
        )
      ),
      error = function(err) list(ok = FALSE, error = err)
    )

    if (isTRUE(tentative$ok)) {
      chd_obj <- tentative$value
      chd_obj$auto_k_requested <- as.integer(k_requested)
      chd_obj$auto_k_effective <- as.integer(k_candidate)
      chd_obj$auto_k_reduced <- isTRUE(k_candidate < k_requested)
      chd_obj$auto_k_reduction_reason <- reduction_reason
      return(chd_obj)
    }

    if (!.est_erreur_limite_partition_auto_chd(tentative$error)) {
      stop(tentative$error)
    }

    reduction_reason <- conditionMessage(tentative$error)
  }

  stop(
    "Discrimination simple: impossible de calculer une solution exploitable entre 2 et ",
    k_requested,
    " classes."
  )
}

.as_dgc_matrix_auto_chd <- function(dfm_obj, binary = FALSE) {
  if (is.null(dfm_obj)) stop("Discrimination simple: dfm_obj manquant.")

  mat <- tryCatch(
    methods::as(dfm_obj, "dgCMatrix"),
    error = function(e) {
      Matrix::Matrix(as.matrix(dfm_obj), sparse = TRUE)
    }
  )

  if (isTRUE(binary) && length(mat@x) > 0L) {
    mat@x[] <- 1
  }

  mat
}

calculer_homogeneite_auto_chd <- function(dfm_obj, classes) {
  mat_bin <- .as_dgc_matrix_auto_chd(dfm_obj, binary = TRUE)
  classes <- suppressWarnings(as.integer(classes))
  ok <- is.finite(classes) & !is.na(classes) & classes > 0L
  mat_bin <- mat_bin[ok, , drop = FALSE]
  classes <- classes[ok]

  classes_uniques <- sort(unique(classes))
  if (nrow(mat_bin) < 2L || ncol(mat_bin) < 1L || length(classes_uniques) < 2L) return(0)

  row_norms <- sqrt(as.numeric(Matrix::rowSums(mat_bin)))
  h_by_class <- numeric(length(classes_uniques))

  for (i in seq_along(classes_uniques)) {
    cl <- classes_uniques[[i]]
    idx <- which(classes == cl)
    if (!length(idx)) {
      h_by_class[[i]] <- 0
      next
    }

    # Une classe singleton n'offre pas de variabilite interne observable :
    # sa coherence ne doit donc pas etre notee comme parfaite par defaut.
    if (length(idx) < 2L) {
      h_by_class[[i]] <- 0
      next
    }

    class_mat <- mat_bin[idx, , drop = FALSE]
    profile <- as.numeric(Matrix::colSums(class_mat)) / length(idx)
    profile_norm <- sqrt(sum(profile^2))
    if (!is.finite(profile_norm) || is.na(profile_norm) || profile_norm <= 0) {
      h_by_class[[i]] <- 0
      next
    }

    numerators <- as.numeric(class_mat %*% profile)
    denom <- row_norms[idx] * profile_norm
    similarities <- ifelse(is.finite(denom) & denom > 0, numerators / denom, 0)
    similarities[!is.finite(similarities) | is.na(similarities)] <- 0
    h_by_class[[i]] <- mean(similarities)
  }

  .borner_score_auto_chd(mean(h_by_class))
}

.jensen_shannon_base2_auto_chd <- function(p, q) {
  p <- as.numeric(p)
  q <- as.numeric(q)
  p[!is.finite(p) | is.na(p)] <- 0
  q[!is.finite(q) | is.na(q)] <- 0

  sum_p <- sum(p)
  sum_q <- sum(q)
  if (sum_p <= 0 || sum_q <= 0) return(0)

  p <- p / sum_p
  q <- q / sum_q
  m <- (p + q) / 2

  kl_div <- function(a, b) {
    idx <- a > 0 & b > 0
    if (!any(idx)) return(0)
    sum(a[idx] * log2(a[idx] / b[idx]))
  }

  .borner_score_auto_chd(0.5 * kl_div(p, m) + 0.5 * kl_div(q, m))
}

calculer_distinction_auto_chd <- function(dfm_obj, classes) {
  mat <- .as_dgc_matrix_auto_chd(dfm_obj, binary = FALSE)
  classes <- suppressWarnings(as.integer(classes))
  ok <- is.finite(classes) & !is.na(classes) & classes > 0L
  mat <- mat[ok, , drop = FALSE]
  classes <- classes[ok]

  classes_uniques <- sort(unique(classes))
  if (nrow(mat) < 2L || ncol(mat) < 1L || length(classes_uniques) < 2L) return(0)

  profiles <- lapply(classes_uniques, function(cl) {
    idx <- which(classes == cl)
    totals <- as.numeric(Matrix::colSums(mat[idx, , drop = FALSE]))
    total_sum <- sum(totals)
    if (!is.finite(total_sum) || is.na(total_sum) || total_sum <= 0) {
      rep(0, length(totals))
    } else {
      totals / total_sum
    }
  })

  min_js <- Inf
  for (i in seq_len(length(profiles) - 1L)) {
    for (j in (i + 1L):length(profiles)) {
      js <- .jensen_shannon_base2_auto_chd(profiles[[i]], profiles[[j]])
      if (is.finite(js) && !is.na(js) && js < min_js) min_js <- js
    }
  }

  if (!is.finite(min_js) || is.na(min_js)) return(0)
  .borner_score_auto_chd(min_js)
}

calculer_diffusion_auto_chd <- function(dfm_obj,
                                        classes,
                                        stats_mode = c("vectorise", "classique"),
                                        top_n = 20L,
                                        p_seuil = 0.05,
                                        res_stats_df = NULL) {
  stats_mode <- match.arg(stats_mode)
  top_n <- suppressWarnings(as.integer(top_n))
  if (!is.finite(top_n) || is.na(top_n) || top_n < 1L) top_n <- 20L

  fn_stats <- get0("construire_stats_classes_iramuteq", mode = "function", inherits = TRUE)
  if (!is.function(fn_stats)) {
    stop("Discrimination simple: construire_stats_classes_iramuteq() est introuvable.")
  }

  classes <- suppressWarnings(as.integer(classes))
  if (is.null(res_stats_df)) {
    res_stats_df <- fn_stats(
      dfm_obj = dfm_obj,
      classes = classes,
      max_p = 1,
      stats_mode = stats_mode
    )
  }

  classes_uniques <- sort(unique(classes[is.finite(classes) & !is.na(classes) & classes > 0L]))
  if (!length(classes_uniques)) {
    return(list(value = 0, by_class = numeric(0), stats = res_stats_df))
  }

  if (is.null(res_stats_df) || !is.data.frame(res_stats_df) || !nrow(res_stats_df)) {
    by_class <- stats::setNames(rep(0, length(classes_uniques)), as.character(classes_uniques))
    return(list(value = 0, by_class = by_class, stats = res_stats_df))
  }

  p_col <- if ("p" %in% names(res_stats_df)) "p" else if ("p_value" %in% names(res_stats_df)) "p_value" else NULL
  if (!all(c("Classe", "chi2", "docprop") %in% names(res_stats_df)) || is.null(p_col)) {
    by_class <- stats::setNames(rep(0, length(classes_uniques)), as.character(classes_uniques))
    return(list(value = 0, by_class = by_class, stats = res_stats_df))
  }

  df <- res_stats_df
  df$Classe <- suppressWarnings(as.integer(df$Classe))
  df$chi2_num <- suppressWarnings(as.numeric(df$chi2))
  df$docprop_num <- suppressWarnings(as.numeric(df$docprop))
  df$p_num <- suppressWarnings(as.numeric(df[[p_col]]))

  by_class <- stats::setNames(rep(0, length(classes_uniques)), as.character(classes_uniques))
  class_sizes <- table(classes[is.finite(classes) & !is.na(classes) & classes > 0L])

  for (cl in classes_uniques) {
    cl_size <- suppressWarnings(as.integer(class_sizes[[as.character(cl)]]))
    # Une diffusion lexicale n'est interpretable que si plusieurs segments
    # portent la classe. Avec un seul segment, l'identite lexicale n'est pas diffusee.
    if (!is.finite(cl_size) || is.na(cl_size) || cl_size < 2L) {
      by_class[[as.character(cl)]] <- 0
      next
    }

    df_cl <- df[
      df$Classe == cl &
        is.finite(df$chi2_num) &
        !is.na(df$chi2_num) &
        df$chi2_num > 0 &
        is.finite(df$p_num) &
        !is.na(df$p_num) &
        df$p_num <= p_seuil &
        is.finite(df$docprop_num) &
        !is.na(df$docprop_num),
      ,
      drop = FALSE
    ]

    if (!nrow(df_cl)) {
      by_class[[as.character(cl)]] <- 0
      next
    }

    df_cl <- df_cl[order(df_cl$chi2_num, decreasing = TRUE), , drop = FALSE]
    df_cl <- utils::head(df_cl, top_n)
    value <- stats::median(df_cl$docprop_num)
    by_class[[as.character(cl)]] <- .borner_score_auto_chd(value)
  }

  list(
    value = .borner_score_auto_chd(min(by_class)),
    by_class = by_class,
    stats = res_stats_df
  )
}


.extraire_coordonnees_xy_auto_chd <- function(coords) {
  if (is.null(coords)) {
    return(NULL)
  }

  if (is.vector(coords)) {
    row_labels <- names(coords)
    mat <- matrix(
      suppressWarnings(as.numeric(coords)),
      ncol = 1L,
      dimnames = list(row_labels, NULL)
    )
  } else if (is.matrix(coords) || is.data.frame(coords)) {
    mat <- as.matrix(coords)
  } else {
    return(NULL)
  }

  if (nrow(mat) < 1L || ncol(mat) < 1L) {
    return(NULL)
  }

  out <- cbind(
    x = suppressWarnings(as.numeric(mat[, 1])),
    y = if (ncol(mat) >= 2L) suppressWarnings(as.numeric(mat[, 2])) else rep(0, nrow(mat))
  )
  rownames(out) <- rownames(mat)
  out
}

.calculer_scores_geometrie_vecteurs_auto_chd <- function(vectors) {
  coords <- .extraire_coordonnees_xy_auto_chd(vectors)
  if (is.null(coords) || nrow(coords) < 1L) {
    return(list(
      theta_mean = 0,
      theta_min = 0,
      dist_mean = 0,
      dist_min = 0,
      rad_mean = 0,
      norms = numeric(0)
    ))
  }

  vecs <- coords[, c("x", "y"), drop = FALSE]
  norms <- sqrt(rowSums(vecs^2))
  rad_scores <- norms / (norms + 1)
  rad_scores[!is.finite(rad_scores) | is.na(rad_scores)] <- 0

  out <- list(
    theta_mean = 0,
    theta_min = 0,
    dist_mean = 0,
    dist_min = 0,
    rad_mean = .borner_score_auto_chd(mean(rad_scores)),
    norms = norms
  )

  if (nrow(vecs) < 2L) {
    return(out)
  }

  pair_index <- utils::combn(seq_len(nrow(vecs)), 2L)
  angle_scores <- numeric(ncol(pair_index))
  dist_scores <- numeric(ncol(pair_index))
  max_radius <- suppressWarnings(max(norms, na.rm = TRUE))

  for (j in seq_len(ncol(pair_index))) {
    i1 <- pair_index[1, j]
    i2 <- pair_index[2, j]
    v1 <- vecs[i1, ]
    v2 <- vecs[i2, ]
    n1 <- norms[[i1]]
    n2 <- norms[[i2]]
    cosine <- if (is.finite(n1) && is.finite(n2) && n1 > 0 && n2 > 0) {
      sum(v1 * v2) / (n1 * n2)
    } else {
      1
    }
    cosine <- max(-1, min(1, cosine))
    angle_scores[[j]] <- .borner_score_auto_chd((1 - cosine) / 2)

    dist_raw <- sqrt(sum((v1 - v2)^2))
    dist_scores[[j]] <- if (is.finite(max_radius) && max_radius > 0) {
      .borner_score_auto_chd(dist_raw / (2 * max_radius))
    } else {
      0
    }
  }

  out$theta_mean <- if (length(angle_scores)) .borner_score_auto_chd(mean(angle_scores)) else 0
  out$theta_min <- if (length(angle_scores)) .borner_score_auto_chd(min(angle_scores)) else 0
  out$dist_mean <- if (length(dist_scores)) .borner_score_auto_chd(mean(dist_scores)) else 0
  out$dist_min <- if (length(dist_scores)) .borner_score_auto_chd(min(dist_scores)) else 0
  out
}

.selectionner_lignes_chi2_afc_auto_chd <- function(res_stats_df,
                                                   top_n = NULL,
                                                   p_seuil = 0.05) {
  if (is.null(res_stats_df) || !is.data.frame(res_stats_df) || !nrow(res_stats_df)) {
    return(data.frame())
  }
  if (!all(c("Terme", "Classe", "chi2") %in% names(res_stats_df))) {
    return(data.frame())
  }

  p_col <- if ("p" %in% names(res_stats_df)) "p" else if ("p_value" %in% names(res_stats_df)) "p_value" else NULL

  df <- res_stats_df
  df$Terme <- trimws(as.character(df$Terme))
  df$Classe_num <- suppressWarnings(as.integer(df$Classe))
  df$chi2_num <- suppressWarnings(as.numeric(df$chi2))
  df$p_num <- if (!is.null(p_col)) suppressWarnings(as.numeric(df[[p_col]])) else NA_real_
  df <- df[
    nzchar(df$Terme) &
      is.finite(df$Classe_num) &
      !is.na(df$Classe_num) &
      is.finite(df$chi2_num) &
      !is.na(df$chi2_num) &
      df$chi2_num > 0,
    ,
    drop = FALSE
  ]
  if (!nrow(df)) {
    return(df[0, , drop = FALSE])
  }

  df_sig <- df
  if (!is.null(p_col)) {
    df_sig <- df[is.finite(df$p_num) & !is.na(df$p_num) & df$p_num <= p_seuil, , drop = FALSE]
  }
  if (nrow(df_sig) > 0L) {
    df <- df_sig
  }

  top_n_num <- if (.limite_top_n_active_auto_chd(top_n)) {
    suppressWarnings(as.integer(top_n[[1]]))
  } else {
    NA_integer_
  }

  classes_uniques <- sort(unique(df$Classe_num))
  rows_by_class <- lapply(classes_uniques, function(class_num) {
    df_cl <- df[df$Classe_num == class_num, , drop = FALSE]
    if (!nrow(df_cl)) {
      return(df_cl[0, , drop = FALSE])
    }
    df_cl <- df_cl[order(df_cl$chi2_num, decreasing = TRUE), , drop = FALSE]
    if (nrow(df_cl) > 1L) {
      df_cl <- df_cl[!duplicated(df_cl$Terme), , drop = FALSE]
    }
    if (is.finite(top_n_num) && !is.na(top_n_num) && top_n_num >= 1L) {
      utils::head(df_cl, top_n_num)
    } else {
      df_cl
    }
  })
  rows_by_class <- rows_by_class[vapply(rows_by_class, nrow, integer(1)) > 0L]
  if (!length(rows_by_class)) {
    return(df[0, , drop = FALSE])
  }
  out <- do.call(rbind, rows_by_class)
  rownames(out) <- NULL
  out[order(out$Classe_num, -out$chi2_num), , drop = FALSE]
}

.selectionner_termes_caracteristiques_afc_auto_chd <- function(res_stats_df,
                                                               top_n = NULL,
                                                               p_seuil = 0.05) {
  df <- .selectionner_lignes_chi2_afc_auto_chd(
    res_stats_df = res_stats_df,
    top_n = top_n,
    p_seuil = p_seuil
  )
  if (is.null(df) || !is.data.frame(df) || !nrow(df)) {
    return(character(0))
  }
  unique(as.character(df$Terme[nzchar(df$Terme)]))
}

.selectionner_termes_caracteristiques_par_classe_afc_auto_chd <- function(res_stats_df,
                                                                          top_n = NULL,
                                                                          p_seuil = 0.05) {
  df <- .selectionner_lignes_chi2_afc_auto_chd(
    res_stats_df = res_stats_df,
    top_n = top_n,
    p_seuil = p_seuil
  )
  if (is.null(df) || !is.data.frame(df) || !nrow(df)) {
    return(list())
  }

  classes_uniques <- sort(unique(df$Classe_num))
  out <- lapply(classes_uniques, function(class_num) {
    df_cl <- df[df$Classe_num == class_num, , drop = FALSE]
    unique(as.character(df_cl$Terme[nzchar(df_cl$Terme)]))
  })
  names(out) <- paste("Classe", classes_uniques)
  out
}

.dataframe_row_to_list_auto_chd <- function(df_row) {
  out <- as.list(df_row)
  for (nm in names(out)) {
    if (length(out[[nm]]) == 1L && is.factor(out[[nm]])) {
      out[[nm]] <- as.character(out[[nm]])
    }
  }
  out
}

.write_metrics_csv_auto_chd <- function(df, path) {
  writer <- get0("ecrire_csv_6_decimales", mode = "function", inherits = TRUE)
  if (is.function(writer)) {
    writer(df, path, row.names = FALSE)
  } else {
    utils::write.csv(df, path, row.names = FALSE)
  }
}

.as_bool_auto_chd <- function(value, default = FALSE) {
  if (is.null(value) || !length(value)) return(isTRUE(default))
  if (is.logical(value)) return(isTRUE(value[[1]]))
  value_chr <- tolower(trimws(as.character(value[[1]])))
  if (!nzchar(value_chr)) return(isTRUE(default))
  value_chr %in% c("1", "true", "vrai", "oui", "yes", "on")
}

.as_int_auto_chd <- function(value, default = 0L, min_value = NULL) {
  value_num <- suppressWarnings(as.integer(value[[1]] %||% default))
  if (!length(value_num) || is.na(value_num) || !is.finite(value_num)) {
    value_num <- as.integer(default)
  }
  if (!is.null(min_value) && is.finite(min_value)) {
    value_num <- max(as.integer(min_value), value_num)
  }
  as.integer(value_num)
}

.as_chr_auto_chd <- function(value, default = "") {
  value_chr <- suppressWarnings(as.character(value[[1]] %||% default))
  if (!length(value_chr) || is.na(value_chr[[1]])) return(as.character(default))
  value_chr <- trimws(value_chr[[1]])
  if (!nzchar(value_chr)) return(as.character(default))
  value_chr
}

.as_chr_vec_auto_chd <- function(value) {
  if (is.null(value)) return(character(0))
  vals <- trimws(as.character(unlist(value, use.names = FALSE)))
  vals <- vals[!is.na(vals) & nzchar(vals)]
  unique(vals)
}

.normaliser_profil_exploration_discrimination_simple <- function(value, default = "complet") {
  profile <- tolower(trimws(.as_chr_auto_chd(value, default)))
  if (!profile %in% c("rapide", "equilibre", "complet", "ciblee")) {
    profile <- default
  }
  profile
}

.label_profil_exploration_discrimination_simple <- function(profile) {
  profile <- .normaliser_profil_exploration_discrimination_simple(profile, default = "complet")
  switch(
    profile,
    rapide = "Rapide",
    equilibre = "Equilibree",
    ciblee = "Ciblee",
    complet = "Complete",
    "Complete"
  )
}

.construire_kmax_discrimination_simple <- function(config_base, search_profile = "complet") {
  k_min <- if (identical(search_profile, "ciblee")) {
    3L
  } else {
    .as_int_auto_chd(config_base$iramuteq_auto_k_min, default = 3L, min_value = 2L)
  }
  k_max <- .as_int_auto_chd(config_base$k_iramuteq, default = 10L, min_value = k_min)
  if (k_max < k_min) k_max <- k_min

  values <- if (identical(search_profile, "rapide")) {
    unique(c(k_min, min(k_max, 5L), k_max))
  } else if (identical(search_profile, "ciblee")) {
    k_max
  } else if (identical(search_profile, "equilibre")) {
    unique(c(k_min, min(k_max, 5L), seq.int(k_min, k_max, by = 2L), k_max))
  } else {
    seq.int(k_min, k_max)
  }

  values <- sort(unique(as.integer(values[is.finite(values) & !is.na(values)])))
  values[values >= k_min & values <= k_max]
}

.empreinte_dfm_auto_chd <- function(dfm_obj) {
  mat <- .as_dgc_matrix_auto_chd(dfm_obj, binary = FALSE)
  tmp <- tempfile("autodisc_dfm_", fileext = ".rds")
  on.exit(unlink(tmp), add = TRUE)

  saveRDS(
    object = list(
      i = mat@i,
      p = mat@p,
      x = signif(mat@x, 10),
      dim = mat@Dim,
      dimnames = dimnames(mat)
    ),
    file = tmp,
    compress = FALSE
  )

  unname(tools::md5sum(tmp)[[1]])
}

calculer_equilibre_classes_auto_chd <- function(classes) {
  classes <- suppressWarnings(as.integer(classes))
  ok <- is.finite(classes) & !is.na(classes) & classes > 0L
  counts <- as.numeric(table(classes[ok]))
  if (length(counts) < 2L) return(0)

  probs <- counts / sum(counts)
  probs <- probs[is.finite(probs) & !is.na(probs) & probs > 0]
  if (length(probs) < 2L) return(0)

  entropy <- -sum(probs * log(probs))
  max_entropy <- log(length(probs))
  if (!is.finite(entropy) || !is.finite(max_entropy) || max_entropy <= 0) return(0)
  .borner_score_auto_chd(entropy / max_entropy)
}

.definir_profil_morpho_discrimination_simple <- function(config_base,
                                                         profile_key = c("aucun", "nom", "nom_ver", "nom_adj_ver"),
                                                         keep_unknown = FALSE,
                                                         exclude_etre = FALSE) {
  profile_key <- match.arg(profile_key)
  config_variant <- config_base

  if (identical(profile_key, "aucun")) {
    config_variant$filtrage_morpho <- FALSE
    config_variant$pos_lexique_a_conserver <- character(0)
    config_variant$morpho_conserver_hors_lexique <- .as_bool_auto_chd(config_base$morpho_conserver_hors_lexique, TRUE)
    config_variant$morpho_exclure_etre_verbe <- FALSE
    return(config_variant)
  }

  profile_pos <- switch(
    profile_key,
    nom = c("NOM"),
    nom_ver = c("NOM", "VER"),
    nom_adj_ver = c("NOM", "ADJ", "VER")
  )

  config_variant$filtrage_morpho <- TRUE
  config_variant$pos_lexique_a_conserver <- profile_pos
  config_variant$morpho_conserver_hors_lexique <- isTRUE(keep_unknown)
  config_variant$morpho_exclure_etre_verbe <- isTRUE(exclude_etre && any(profile_pos %in% c("VER", "VERB", "AUX", "VER_SUP")))
  config_variant
}

.label_profil_morpho_discrimination_simple <- function(profile_key, keep_unknown = FALSE, exclude_etre = FALSE) {
  if (identical(profile_key, "aucun")) return("sans morpho")

  base_label <- switch(
    profile_key,
    nom = "NOM",
    nom_ver = "NOM+VER",
    nom_adj_ver = "NOM+ADJ+VER",
    "morpho"
  )

  suffixes <- character(0)
  if (isTRUE(keep_unknown)) suffixes <- c(suffixes, "AUTRE_FORME")
  if (isTRUE(exclude_etre)) suffixes <- c(suffixes, "sans ETRE")
  if (!length(suffixes)) return(base_label)
  paste0(base_label, " (", paste(suffixes, collapse = ", "), ")")
}

construire_grille_discrimination_simple_iramuteq <- function(config_base) {
  if (is.null(config_base) || !is.list(config_base)) {
    stop("Discrimination simple: config_base manquante ou invalide.")
  }

  search_profile <- .normaliser_profil_exploration_discrimination_simple(
    config_base$iramuteq_discrimination_simple_profile,
    default = "complet"
  )
  k_max_values <- .construire_kmax_discrimination_simple(config_base, search_profile = search_profile)
  if (identical(search_profile, "ciblee")) {
    keep_unknown_user <- .as_bool_auto_chd(config_base$morpho_conserver_hors_lexique, TRUE)
    min_docfreq_values <- 2L:5L
    use_lemmes_values <- c(.as_bool_auto_chd(config_base$lexique_utiliser_lemmes, FALSE))
    remove_stopwords_values <- c(.as_bool_auto_chd(config_base$retirer_stopwords, FALSE))
    remove_punctuation_values <- c(.as_bool_auto_chd(config_base$supprimer_ponctuation, FALSE))
    remove_digits_values <- c(.as_bool_auto_chd(config_base$supprimer_chiffres, FALSE))
    morpho_profiles <- list(
      list(key = "nom_ver", keep_unknown = keep_unknown_user, exclude_etre = TRUE)
    )
  } else {
    min_docfreq_values <- sort(unique(c(1L, 2L, 3L, .as_int_auto_chd(config_base$min_docfreq, 1L, 1L))))
    use_lemmes_values <- c(FALSE, TRUE)
    remove_stopwords_values <- c(FALSE, TRUE)
    remove_punctuation_values <- c(FALSE, TRUE)
    remove_digits_values <- c(FALSE, TRUE)

    if (identical(search_profile, "rapide")) {
      use_lemmes_values <- c(.as_bool_auto_chd(config_base$lexique_utiliser_lemmes, TRUE))
      remove_punctuation_values <- c(.as_bool_auto_chd(config_base$supprimer_ponctuation, FALSE))
    } else if (identical(search_profile, "equilibre")) {
      remove_punctuation_values <- c(.as_bool_auto_chd(config_base$supprimer_ponctuation, FALSE))
    }

    morpho_profiles <- list(
      list(key = "aucun", keep_unknown = FALSE, exclude_etre = FALSE),
      list(key = "nom", keep_unknown = FALSE, exclude_etre = FALSE),
      list(key = "nom", keep_unknown = TRUE, exclude_etre = FALSE),
      list(key = "nom_ver", keep_unknown = FALSE, exclude_etre = FALSE),
      list(key = "nom_ver", keep_unknown = FALSE, exclude_etre = TRUE),
      list(key = "nom_ver", keep_unknown = TRUE, exclude_etre = FALSE),
      list(key = "nom_ver", keep_unknown = TRUE, exclude_etre = TRUE),
      list(key = "nom_adj_ver", keep_unknown = FALSE, exclude_etre = FALSE),
      list(key = "nom_adj_ver", keep_unknown = FALSE, exclude_etre = TRUE),
      list(key = "nom_adj_ver", keep_unknown = TRUE, exclude_etre = FALSE),
      list(key = "nom_adj_ver", keep_unknown = TRUE, exclude_etre = TRUE)
    )
  }

  candidates <- list()
  index <- 0L

  for (morpho in morpho_profiles) {
    for (use_lemmes in use_lemmes_values) {
      for (remove_stopwords in remove_stopwords_values) {
        for (remove_punctuation in remove_punctuation_values) {
          for (remove_digits in remove_digits_values) {
            for (min_docfreq in min_docfreq_values) {
              for (k_max_candidate in k_max_values) {
                index <- index + 1L
                config_variant <- .definir_profil_morpho_discrimination_simple(
                  config_base = config_base,
                  profile_key = morpho$key,
                  keep_unknown = morpho$keep_unknown,
                  exclude_etre = morpho$exclude_etre
                )
                config_variant$lexique_utiliser_lemmes <- isTRUE(use_lemmes)
                config_variant$retirer_stopwords <- remove_stopwords
                config_variant$supprimer_ponctuation <- remove_punctuation
                config_variant$supprimer_chiffres <- remove_digits
                config_variant$min_docfreq <- as.integer(min_docfreq)
                config_variant$k_iramuteq <- as.integer(k_max_candidate)
                config_variant$iramuteq_classes_mode <- "discrimination_simple_partition"

                candidates[[index]] <- list(
                  id = sprintf("CFG%03d", index),
                  config = config_variant,
                  profil_morpho = .label_profil_morpho_discrimination_simple(
                    morpho$key,
                    keep_unknown = morpho$keep_unknown,
                    exclude_etre = morpho$exclude_etre
                  ),
                  lexique_utiliser_lemmes = isTRUE(use_lemmes),
                  retirer_stopwords = isTRUE(remove_stopwords),
                  supprimer_ponctuation = isTRUE(remove_punctuation),
                  supprimer_chiffres = isTRUE(remove_digits),
                  min_docfreq = as.integer(min_docfreq),
                  k_max_explore = as.integer(k_max_candidate)
                )
              }
            }
          }
        }
      }
    }
  }

  list(
    profile = search_profile,
    profile_label = .label_profil_exploration_discrimination_simple(search_profile),
    candidates = candidates
  )
}
