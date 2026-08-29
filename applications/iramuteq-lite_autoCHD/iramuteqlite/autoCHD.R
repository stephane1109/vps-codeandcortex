# Role du fichier: autoCHD.R ajoute une couche optionnelle de selection
# automatique du nombre de classes au-dessus de la CHD IRaMuTeQ-lite existante.
# La CHD historique n'est pas modifiee: on reutilise ses partitions successives,
# puis on calcule les scores H, D, L, B et G pour choisir la meilleure partition.

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

extraire_partition_chd_iramuteq <- function(chd_obj, k) {
  n1 <- .normaliser_n1_auto_chd(chd_obj$n1)
  if (is.null(n1)) stop("Auto CHD: objet CHD invalide ou sans matrice n1.")

  k <- suppressWarnings(as.integer(k))
  if (!is.finite(k) || is.na(k) || k < 2L) {
    stop("Auto CHD: k doit etre >= 2.")
  }

  col_index <- k - 1L
  if (col_index > ncol(n1)) {
    stop("Auto CHD: partition demandee indisponible dans n1.")
  }

  classes_raw <- suppressWarnings(as.integer(n1[, col_index]))
  classes <- normaliser_partition_classes_iramuteq(classes_raw)
  terminales <- sort(unique(classes_raw[is.finite(classes_raw) & !is.na(classes_raw) & classes_raw > 0L]))

  list(
    k = as.integer(length(unique(classes[classes > 0L]))),
    requested_k = as.integer(k),
    column_index = as.integer(col_index),
    classes_raw = classes_raw,
    classes = classes,
    terminales = as.integer(terminales)
  )
}

lister_partitions_chd_iramuteq <- function(chd_obj, k_max = NULL) {
  n1 <- .normaliser_n1_auto_chd(chd_obj$n1)
  if (is.null(n1)) stop("Auto CHD: objet CHD invalide ou sans matrice n1.")

  max_available <- ncol(n1) + 1L
  if (is.null(k_max) || !length(k_max) || is.na(k_max[[1]]) || !is.finite(as.numeric(k_max[[1]]))) {
    k_max_use <- max_available
  } else {
    k_max_use <- min(max_available, max(2L, as.integer(k_max[[1]])))
  }

  lapply(2:k_max_use, function(k) extraire_partition_chd_iramuteq(chd_obj, k))
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
    stop("Auto CHD: calculer_chd_fn doit etre une fonction.")
  }
  if (is.null(dfm_obj)) {
    stop("Auto CHD: dfm_obj manquant pour la recherche de la borne maximale.")
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
    "Auto CHD: impossible de calculer une partition exploitable entre 2 et ",
    k_requested,
    " classes."
  )
}

.as_dgc_matrix_auto_chd <- function(dfm_obj, binary = FALSE) {
  if (is.null(dfm_obj)) stop("Auto CHD: dfm_obj manquant.")

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
    stop("Auto CHD: construire_stats_classes_iramuteq() est introuvable.")
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

evaluer_partition_auto_chd <- function(dfm_obj,
                                       partition_obj,
                                       stats_mode = c("vectorise", "classique"),
                                       top_n_diffusion = 20L,
                                       p_seuil = 0.05) {
  stats_mode <- match.arg(stats_mode)
  if (is.null(partition_obj) || is.null(partition_obj$classes)) {
    stop("Auto CHD: partition invalide.")
  }

  classes <- suppressWarnings(as.integer(partition_obj$classes))
  ok <- is.finite(classes) & !is.na(classes) & classes > 0L
  counts <- table(classes[ok])
  total_assigned <- sum(counts)
  pct <- if (total_assigned > 0) 100 * counts / total_assigned else counts

  h_value <- calculer_homogeneite_auto_chd(dfm_obj, classes)
  d_value <- calculer_distinction_auto_chd(dfm_obj, classes)
  diffusion <- calculer_diffusion_auto_chd(
    dfm_obj = dfm_obj,
    classes = classes,
    stats_mode = stats_mode,
    top_n = top_n_diffusion,
    p_seuil = p_seuil
  )
  l_value <- diffusion$value
  b_value <- .borner_score_auto_chd(mean(c(h_value, d_value, l_value)))

  metrics <- data.frame(
    partition = paste0("P", partition_obj$k),
    k = as.integer(partition_obj$k),
    n_segments_assignes = as.integer(total_assigned),
    n_segments_non_assignes = as.integer(sum(!ok)),
    H = .borner_score_auto_chd(h_value),
    D = .borner_score_auto_chd(d_value),
    L = .borner_score_auto_chd(l_value),
    B = .borner_score_auto_chd(b_value),
    classes_effectifs = .formatter_resume_classes_auto_chd(counts, digits = 0L),
    classes_pourcentages = .formatter_resume_classes_auto_chd(pct, digits = 2L, suffix = "%"),
    stringsAsFactors = FALSE
  )

  list(
    partition = partition_obj,
    metrics = metrics,
    stats = diffusion$stats,
    diffusion_by_class = diffusion$by_class
  )
}

selection_automatique_classes_iramuteq <- function(chd_obj,
                                                   dfm_obj,
                                                   k_max = NULL,
                                                   stats_mode = c("vectorise", "classique"),
                                                   top_n_diffusion = 20L,
                                                   p_seuil = 0.05) {
  stats_mode <- match.arg(stats_mode)

  partitions <- lister_partitions_chd_iramuteq(chd_obj, k_max = k_max)
  if (!length(partitions)) {
    stop("Auto CHD: aucune partition exploitable entre 2 classes et la limite demandee.")
  }

  evaluations <- lapply(partitions, function(partition_obj) {
    evaluer_partition_auto_chd(
      dfm_obj = dfm_obj,
      partition_obj = partition_obj,
      stats_mode = stats_mode,
      top_n_diffusion = top_n_diffusion,
      p_seuil = p_seuil
    )
  })

  metrics_df <- do.call(rbind, lapply(evaluations, `[[`, "metrics"))
  metrics_df <- metrics_df[order(metrics_df$k), , drop = FALSE]
  metrics_df$G <- NA_real_

  if (nrow(metrics_df) > 1L) {
    b_values <- suppressWarnings(as.numeric(metrics_df$B))
    gains <- rep(NA_real_, length(b_values))
    gains[-1L] <- b_values[-1L] - b_values[-length(b_values)]
    metrics_df$G <- gains
  }

  b_values <- suppressWarnings(as.numeric(metrics_df$B))
  b_scores <- ifelse(is.finite(b_values) & !is.na(b_values), b_values, -Inf)
  if (!any(is.finite(b_scores) & b_scores > -Inf)) {
    stop("Auto CHD: aucun score B exploitable n'a pu etre calcule.")
  }

  selected_idx <- which.max(b_scores)
  metrics_df$selection <- ifelse(seq_len(nrow(metrics_df)) == selected_idx, "oui", "non")

  selected_partition <- partitions[[selected_idx]]
  selected_evaluation <- evaluations[[selected_idx]]
  k_max_tested <- suppressWarnings(max(as.integer(metrics_df$k), na.rm = TRUE))
  k_max_requested <- suppressWarnings(as.integer(chd_obj$auto_k_requested %||% k_max[[1]] %||% k_max))
  if (!length(k_max_requested) || is.na(k_max_requested) || !is.finite(k_max_requested)) {
    k_max_requested <- as.integer(k_max_tested)
  }
  k_max_requested <- max(2L, k_max_requested)

  list(
    mode = "auto",
    classes = selected_partition$classes,
    classes_raw = selected_partition$classes_raw,
    terminales = selected_partition$terminales,
    k_selected = as.integer(metrics_df$k[[selected_idx]]),
    k_max_requested = as.integer(k_max_requested),
    k_max_tested = as.integer(k_max_tested),
    k_max_reduced = isTRUE(k_max_tested < k_max_requested),
    k_reduction_reason = chd_obj$auto_k_reduction_reason %||% NULL,
    evaluation = metrics_df,
    selected_metrics = metrics_df[selected_idx, , drop = FALSE],
    selected_stats = selected_evaluation$stats,
    selected_diffusion_by_class = selected_evaluation$diffusion_by_class,
    partitions = partitions
  )
}

tracer_scores_auto_chd_iramuteq <- function(metrics_df, selected_k = NULL) {
  if (is.null(metrics_df) || !is.data.frame(metrics_df) || !nrow(metrics_df)) {
    plot.new()
    text(0.5, 0.5, "Aucune partition automatique a afficher.", cex = 1.0)
    return(invisible(NULL))
  }

  x <- suppressWarnings(as.integer(metrics_df$k))
  y <- suppressWarnings(as.numeric(metrics_df$B))
  ok <- is.finite(x) & !is.na(x) & is.finite(y) & !is.na(y)
  x <- x[ok]
  y <- y[ok]

  if (length(x) < 1L) {
    plot.new()
    text(0.5, 0.5, "Les scores B sont indisponibles.", cex = 1.0)
    return(invisible(NULL))
  }

  y_min <- min(0, y)
  y_max <- max(1, y)
  plot(
    x,
    y,
    type = "b",
    pch = 19,
    lwd = 2,
    col = "#8d1b1d",
    xlab = "Nombre de classes k",
    ylab = "Score structurel B",
    ylim = c(y_min, y_max),
    main = "Selection automatique du nombre de classes"
  )
  grid(col = "#d6c8b8", lty = "dotted")

  if (!is.null(selected_k) && length(selected_k)) {
    selected_k <- suppressWarnings(as.integer(selected_k[[1]]))
    idx <- which(x == selected_k)
    if (length(idx)) {
      points(x[idx[1]], y[idx[1]], pch = 21, bg = "#f6c344", col = "#8d1b1d", cex = 1.7, lwd = 1.5)
      text(x[idx[1]], y[idx[1]], labels = paste0("  P", selected_k), pos = 4, col = "#5f1a18")
    }
  }

  invisible(NULL)
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

exporter_auto_chd_iramuteq <- function(selection_obj, output_dir) {
  if (is.null(selection_obj) || !is.list(selection_obj)) {
    stop("Auto CHD: objet de selection automatique manquant.")
  }
  if (is.null(output_dir) || !nzchar(output_dir)) {
    stop("Auto CHD: dossier de sortie manquant.")
  }

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  metrics_df <- selection_obj$evaluation
  selected_df <- selection_obj$selected_metrics

  metrics_csv <- file.path(output_dir, "auto_chd_metrics.csv")
  summary_json <- file.path(output_dir, "auto_chd_summary.json")
  score_png <- file.path(output_dir, "auto_chd_b_score.png")

  .write_metrics_csv_auto_chd(metrics_df, metrics_csv)

  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Auto CHD: le package jsonlite est requis pour exporter le resume JSON.")
  }

  metrics_rows <- lapply(seq_len(nrow(metrics_df)), function(i) {
    .dataframe_row_to_list_auto_chd(metrics_df[i, , drop = FALSE])
  })

  payload <- list(
    mode = "auto",
    selected_k = selection_obj$k_selected %||% NA_integer_,
    k_max_requested = selection_obj$k_max_requested %||% NA_integer_,
    k_max_tested = selection_obj$k_max_tested %||% NA_integer_,
    k_max_reduced = selection_obj$k_max_reduced %||% FALSE,
    k_reduction_reason = selection_obj$k_reduction_reason %||% NULL,
    partition = paste0("P", selection_obj$k_selected %||% ""),
    selected = if (!is.null(selected_df) && nrow(selected_df)) {
      .dataframe_row_to_list_auto_chd(selected_df[1, , drop = FALSE])
    } else {
      NULL
    },
    metrics = metrics_rows
  )
  jsonlite::write_json(payload, summary_json, auto_unbox = TRUE, pretty = TRUE, null = "null")

  grDevices::png(score_png, width = 1800, height = 1100, res = 180)
  tracer_scores_auto_chd_iramuteq(metrics_df, selected_k = selection_obj$k_selected)
  grDevices::dev.off()

  list(
    metrics_csv = metrics_csv,
    summary_json = summary_json,
    score_png = score_png
  )
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

.normaliser_profil_exploration_auto_discriminante <- function(value, default = "complet") {
  profile <- tolower(trimws(.as_chr_auto_chd(value, default)))
  if (!profile %in% c("rapide", "equilibre", "complet")) {
    profile <- default
  }
  profile
}

.label_profil_exploration_auto_discriminante <- function(profile) {
  profile <- .normaliser_profil_exploration_auto_discriminante(profile, default = "complet")
  switch(
    profile,
    rapide = "Rapide",
    equilibre = "Equilibree",
    complet = "Complete",
    "Complete"
  )
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

calculer_score_auto_discriminante <- function(B, D, E) {
  values <- suppressWarnings(as.numeric(c(B, D, E)))
  values[!is.finite(values) | is.na(values)] <- 0
  values <- pmax(values, 0)
  if (any(values <= 0)) return(0)
  .borner_score_auto_chd(exp(mean(log(values))))
}

.definir_profil_morpho_auto_discriminant <- function(config_base,
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

.label_profil_morpho_auto_discriminant <- function(profile_key, keep_unknown = FALSE, exclude_etre = FALSE) {
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

construire_grille_auto_discriminante_iramuteq <- function(config_base) {
  if (is.null(config_base) || !is.list(config_base)) {
    stop("Auto discriminante: config_base manquante ou invalide.")
  }

  search_profile <- .normaliser_profil_exploration_auto_discriminante(
    config_base$iramuteq_auto_discriminante_profile,
    default = "complet"
  )
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

  candidates <- list()
  index <- 0L

  for (morpho in morpho_profiles) {
    for (use_lemmes in use_lemmes_values) {
      for (remove_stopwords in remove_stopwords_values) {
        for (remove_punctuation in remove_punctuation_values) {
          for (remove_digits in remove_digits_values) {
            for (min_docfreq in min_docfreq_values) {
              index <- index + 1L
              config_variant <- .definir_profil_morpho_auto_discriminant(
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
              config_variant$iramuteq_classes_mode <- "auto"

              candidates[[index]] <- list(
                id = sprintf("CFG%03d", index),
                config = config_variant,
                profil_morpho = .label_profil_morpho_auto_discriminant(
                  morpho$key,
                  keep_unknown = morpho$keep_unknown,
                  exclude_etre = morpho$exclude_etre
                ),
                lexique_utiliser_lemmes = isTRUE(use_lemmes),
                retirer_stopwords = isTRUE(remove_stopwords),
                supprimer_ponctuation = isTRUE(remove_punctuation),
                supprimer_chiffres = isTRUE(remove_digits),
                min_docfreq = as.integer(min_docfreq)
              )
            }
          }
        }
      }
    }
  }

  list(
    profile = search_profile,
    profile_label = .label_profil_exploration_auto_discriminante(search_profile),
    candidates = candidates
  )
}

.resume_configuration_auto_discriminante <- function(candidate) {
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
    "]"
  )
}

.ligne_erreur_auto_discriminante <- function(candidate, error_message) {
  data.frame(
    configuration_id = candidate$id %||% NA_character_,
    configuration_label = .resume_configuration_auto_discriminante(candidate),
    profil_morpho = candidate$profil_morpho %||% NA_character_,
    lexique_utiliser_lemmes = ifelse(isTRUE(candidate$lexique_utiliser_lemmes), "oui", "non"),
    retirer_stopwords = ifelse(isTRUE(candidate$retirer_stopwords), "oui", "non"),
    supprimer_ponctuation = ifelse(isTRUE(candidate$supprimer_ponctuation), "oui", "non"),
    supprimer_chiffres = ifelse(isTRUE(candidate$supprimer_chiffres), "oui", "non"),
    min_docfreq = candidate$min_docfreq %||% NA_integer_,
    n_segments = NA_integer_,
    n_formes = NA_integer_,
    k_retenu = NA_integer_,
    H = NA_real_,
    D = NA_real_,
    L = NA_real_,
    B = NA_real_,
    E = NA_real_,
    S = NA_real_,
    classes_effectifs = NA_character_,
    classes_pourcentages = NA_character_,
    selection = "echec",
    erreur = as.character(error_message %||% ""),
    stringsAsFactors = FALSE
  )
}

.ligne_succes_auto_discriminante <- function(candidate, pipeline_obj, res_ira) {
  if (is.null(res_ira$auto_selection) || !is.data.frame(res_ira$auto_selection$selected_metrics) || !nrow(res_ira$auto_selection$selected_metrics)) {
    stop("Auto discriminante: la configuration ne renvoie aucune selection auto exploitable.")
  }

  selected_metrics <- res_ira$auto_selection$selected_metrics[1, , drop = FALSE]
  classes <- suppressWarnings(as.integer(res_ira$auto_selection$classes))
  e_value <- calculer_equilibre_classes_auto_chd(classes)
  s_value <- calculer_score_auto_discriminante(
    B = suppressWarnings(as.numeric(selected_metrics$B[[1]])),
    D = suppressWarnings(as.numeric(selected_metrics$D[[1]])),
    E = e_value
  )

  data.frame(
    configuration_id = candidate$id %||% NA_character_,
    configuration_label = .resume_configuration_auto_discriminante(candidate),
    profil_morpho = candidate$profil_morpho %||% NA_character_,
    lexique_utiliser_lemmes = ifelse(isTRUE(candidate$lexique_utiliser_lemmes), "oui", "non"),
    retirer_stopwords = ifelse(isTRUE(candidate$retirer_stopwords), "oui", "non"),
    supprimer_ponctuation = ifelse(isTRUE(candidate$supprimer_ponctuation), "oui", "non"),
    supprimer_chiffres = ifelse(isTRUE(candidate$supprimer_chiffres), "oui", "non"),
    min_docfreq = candidate$min_docfreq %||% NA_integer_,
    n_segments = suppressWarnings(as.integer(quanteda::ndoc(pipeline_obj$dfm_obj))),
    n_formes = suppressWarnings(as.integer(quanteda::nfeat(pipeline_obj$dfm_obj))),
    k_retenu = suppressWarnings(as.integer(res_ira$auto_selection$k_selected %||% selected_metrics$k[[1]])),
    H = .borner_score_auto_chd(selected_metrics$H[[1]]),
    D = .borner_score_auto_chd(selected_metrics$D[[1]]),
    L = .borner_score_auto_chd(selected_metrics$L[[1]]),
    B = .borner_score_auto_chd(selected_metrics$B[[1]]),
    E = .borner_score_auto_chd(e_value),
    S = .borner_score_auto_chd(s_value),
    classes_effectifs = as.character(selected_metrics$classes_effectifs[[1]] %||% ""),
    classes_pourcentages = as.character(selected_metrics$classes_pourcentages[[1]] %||% ""),
    selection = "testee",
    erreur = "",
    stringsAsFactors = FALSE
  )
}

selection_configuration_discriminante_iramuteq <- function(config_base,
                                                           preparer_pipeline_fn,
                                                           lancer_auto_chd_fn,
                                                           log_fn = NULL) {
  if (!is.list(config_base)) {
    stop("Auto discriminante: config_base doit etre une liste.")
  }
  if (!is.function(preparer_pipeline_fn)) {
    stop("Auto discriminante: preparer_pipeline_fn doit etre une fonction.")
  }
  if (!is.function(lancer_auto_chd_fn)) {
    stop("Auto discriminante: lancer_auto_chd_fn doit etre une fonction.")
  }

  grid_obj <- construire_grille_auto_discriminante_iramuteq(config_base)
  candidates <- grid_obj$candidates %||% list()
  search_profile <- grid_obj$profile %||% "complet"
  search_profile_label <- grid_obj$profile_label %||% .label_profil_exploration_auto_discriminante(search_profile)
  total_candidates <- length(candidates)
  if (!length(candidates)) {
    stop("Auto discriminante: aucune configuration candidate n'a ete construite.")
  }

  if (is.function(log_fn)) {
    log_fn(
      paste0(
        "Auto discriminante : profil ",
        tolower(search_profile_label),
        " - recherche sur ",
        total_candidates,
        " configurations discriminantes."
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

    if (is.function(log_fn) && (i == 1L || i == total_candidates || (i %% 10L) == 0L)) {
      log_fn(
        paste0(
          "Auto discriminante : test ",
          i,
          "/",
          total_candidates,
          " -> ",
          .resume_configuration_auto_discriminante(candidate)
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

        dfm_fingerprint <- .empreinte_dfm_auto_chd(pipeline_obj$dfm_obj)
        cache_hit <- exists(dfm_fingerprint, envir = dfm_cache, inherits = FALSE)
        if (isTRUE(cache_hit)) {
          reused_count <<- reused_count + 1L
          cached_attempt <- get(dfm_fingerprint, envir = dfm_cache, inherits = FALSE)
          if (isTRUE(cached_attempt$ok)) {
            row <- .ligne_succes_auto_discriminante(candidate, pipeline_obj, cached_attempt$res_ira)
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
              row = .ligne_erreur_auto_discriminante(candidate, cached_attempt$error_message %||% "Echec reutilise depuis le cache DFM."),
              error = cached_attempt$error,
              reused = TRUE,
              fingerprint = dfm_fingerprint
            )
          }
        } else {
          res_ira <- lancer_auto_chd_fn(
            dfm_obj = pipeline_obj$dfm_obj,
            config_variant = candidate$config
          )

          if (is.null(res_ira$auto_selection)) {
            stop("La CHD auto n'a retourne aucune selection exploitable.")
          }

          row <- .ligne_succes_auto_discriminante(candidate, pipeline_obj, res_ira)
          cache_entry <- list(ok = TRUE, res_ira = res_ira)
          assign(dfm_fingerprint, cache_entry, envir = dfm_cache)
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
        list(ok = FALSE, row = .ligne_erreur_auto_discriminante(candidate, conditionMessage(err)), error = err, reused = FALSE)
      }
    )

    evaluation_rows[[i]] <- attempt$row
    evaluation_details[[i]] <- attempt

    if (isTRUE(attempt$ok)) {
      current_row <- attempt$row
      current_score <- suppressWarnings(as.numeric(current_row$S[[1]]))
      current_D <- suppressWarnings(as.numeric(current_row$D[[1]]))
      current_B <- suppressWarnings(as.numeric(current_row$B[[1]]))

      if (is.na(best_idx)) {
        best_idx <- i
      } else {
        best_row <- evaluation_rows[[best_idx]]
        best_score <- suppressWarnings(as.numeric(best_row$S[[1]]))
        best_D <- suppressWarnings(as.numeric(best_row$D[[1]]))
        best_B <- suppressWarnings(as.numeric(best_row$B[[1]]))

        if (
          (is.finite(current_score) && !is.na(current_score) && (!is.finite(best_score) || is.na(best_score) || current_score > best_score + 1e-12)) ||
          (is.finite(current_score) && is.finite(best_score) && abs(current_score - best_score) <= 1e-12 && is.finite(current_D) && (!is.finite(best_D) || current_D > best_D + 1e-12)) ||
          (is.finite(current_score) && is.finite(best_score) && abs(current_score - best_score) <= 1e-12 &&
             is.finite(current_D) && is.finite(best_D) && abs(current_D - best_D) <= 1e-12 &&
             is.finite(current_B) && (!is.finite(best_B) || current_B > best_B + 1e-12))
        ) {
          best_idx <- i
        }
      }
    }
  }

  if (is.na(best_idx)) {
    stop("Auto discriminante: aucune configuration n'a produit de CHD exploitable.")
  }

  metrics_df <- do.call(rbind, evaluation_rows)
  metrics_df$selection <- ifelse(seq_len(nrow(metrics_df)) == best_idx, "retenue", metrics_df$selection)

  best_detail <- evaluation_details[[best_idx]]
  best_row <- metrics_df[best_idx, , drop = FALSE]
  if (is.function(log_fn)) {
    log_fn(
      paste0(
        "Auto discriminante : ",
        length(ls(dfm_cache)),
        " DFM uniques calculees, ",
        reused_count,
        " configuration(s) ont reutilise une DFM deja testee."
      ),
      progress = 58
    )
    log_fn(
      paste0(
        "Auto discriminante : configuration retenue -> ",
        best_row$configuration_label[[1]],
        " | k=",
        best_row$k_retenu[[1]],
        " | D=",
        format(round(as.numeric(best_row$D[[1]]), 4), nsmall = 4, trim = TRUE),
        " | B=",
        format(round(as.numeric(best_row$B[[1]]), 4), nsmall = 4, trim = TRUE),
        " | E=",
        format(round(as.numeric(best_row$E[[1]]), 4), nsmall = 4, trim = TRUE),
        " | S=",
        format(round(as.numeric(best_row$S[[1]]), 4), nsmall = 4, trim = TRUE)
      ),
      progress = 59
    )
  }

  list(
    mode = "auto_discriminante",
    search_profile = search_profile,
    search_profile_label = search_profile_label,
    total_configurations = total_candidates,
    successful_configurations = sum(metrics_df$selection != "echec", na.rm = TRUE),
    unique_dfm_tested = length(ls(dfm_cache)),
    reused_configurations = reused_count,
    evaluation = metrics_df,
    selected_index = best_idx,
    selected_metrics = best_row,
    selected_candidate = candidates[[best_idx]],
    selected_pipeline = best_detail$pipeline,
    selected_result = best_detail$res_ira
  )
}

tracer_scores_auto_discriminante_iramuteq <- function(metrics_df, selected_id = NULL, top_n = 12L) {
  if (is.null(metrics_df) || !is.data.frame(metrics_df) || !nrow(metrics_df)) {
    plot.new()
    text(0.5, 0.5, "Aucune configuration discriminante a afficher.", cex = 1.0)
    return(invisible(NULL))
  }

  df <- metrics_df
  df$S_num <- suppressWarnings(as.numeric(df$S))
  df <- df[is.finite(df$S_num) & !is.na(df$S_num), , drop = FALSE]
  if (!nrow(df)) {
    plot.new()
    text(0.5, 0.5, "Les scores discriminants sont indisponibles.", cex = 1.0)
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
    xlab = "Score discriminant S",
    main = "Configurations les plus discriminantes"
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

exporter_auto_discriminante_iramuteq <- function(selection_obj, output_dir) {
  if (is.null(selection_obj) || !is.list(selection_obj)) {
    stop("Auto discriminante: objet de selection manquant.")
  }
  if (is.null(output_dir) || !nzchar(output_dir)) {
    stop("Auto discriminante: dossier de sortie manquant.")
  }

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  metrics_df <- selection_obj$evaluation
  selected_df <- selection_obj$selected_metrics
  summary_json <- file.path(output_dir, "auto_discriminante_summary.json")
  metrics_csv <- file.path(output_dir, "auto_discriminante_metrics.csv")
  score_png <- file.path(output_dir, "auto_discriminante_score.png")

  .write_metrics_csv_auto_chd(metrics_df, metrics_csv)

  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Auto discriminante: le package jsonlite est requis pour exporter le resume JSON.")
  }

  payload <- list(
    mode = "auto_discriminante",
    search_profile = selection_obj$search_profile %||% "complet",
    search_profile_label = selection_obj$search_profile_label %||% .label_profil_exploration_auto_discriminante(selection_obj$search_profile %||% "complet"),
    total_configurations = selection_obj$total_configurations %||% NA_integer_,
    successful_configurations = selection_obj$successful_configurations %||% NA_integer_,
    unique_dfm_tested = selection_obj$unique_dfm_tested %||% NA_integer_,
    reused_configurations = selection_obj$reused_configurations %||% NA_integer_,
    selected = if (!is.null(selected_df) && nrow(selected_df)) {
      .dataframe_row_to_list_auto_chd(selected_df[1, , drop = FALSE])
    } else {
      NULL
    },
    metrics = lapply(seq_len(nrow(metrics_df)), function(i) {
      .dataframe_row_to_list_auto_chd(metrics_df[i, , drop = FALSE])
    })
  )
  jsonlite::write_json(payload, summary_json, auto_unbox = TRUE, pretty = TRUE, null = "null")

  grDevices::png(score_png, width = 1800, height = 1200, res = 180)
  tracer_scores_auto_discriminante_iramuteq(metrics_df, selected_id = selected_df$configuration_id %||% NULL)
  grDevices::dev.off()

  list(
    metrics_csv = metrics_csv,
    summary_json = summary_json,
    score_png = score_png
  )
}
