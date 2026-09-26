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

  for (cl in classes_uniques) {
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
