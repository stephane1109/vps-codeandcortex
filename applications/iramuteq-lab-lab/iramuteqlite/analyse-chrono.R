# Analyse chronologique croisee des classes issues d'une CHD.

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0L) y else x
}

normaliser_modalite_chrono <- function(x) {
  value <- trimws(as.character(x))
  value[is.na(value) | !nzchar(value)] <- NA_character_
  enc2utf8(value)
}

nom_variable_chrono <- function(variable) {
  sub("^\\*", "", trimws(as.character(variable)))
}

est_variable_temporelle_chrono <- function(variable) {
  label <- iconv(nom_variable_chrono(variable), to = "ASCII//TRANSLIT", sub = "")
  grepl(
    "annee|year|date|mois|month|periode|period|temps|time|trimestre|quarter|semaine|week",
    tolower(label),
    perl = TRUE
  )
}

ordonner_modalites_chrono <- function(values) {
  values <- unique(normaliser_modalite_chrono(values))
  values <- values[!is.na(values)]
  if (!length(values)) return(character(0))

  numeric_values <- suppressWarnings(as.numeric(gsub(",", ".", values, fixed = TRUE)))
  if (all(is.finite(numeric_values))) {
    return(values[order(numeric_values, values)])
  }

  parsed_dates <- as.Date(rep(NA_character_, length(values)))
  for (format in c("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m", "%Y/%m")) {
    missing <- is.na(parsed_dates)
    if (!any(missing)) break
    parsed_dates[missing] <- suppressWarnings(as.Date(values[missing], format = format))
  }
  if (all(!is.na(parsed_dates))) {
    return(values[order(parsed_dates, values)])
  }

  values[order(tolower(values), values)]
}

variables_chrono_disponibles <- function(source) {
  docvars <- source$docvars
  if (is.null(docvars) || !is.data.frame(docvars)) return(list())

  reserved <- c("Classes", "doc_id", "segment_source", "rst_source")
  candidates <- setdiff(names(docvars), reserved)
  candidates <- candidates[startsWith(candidates, "*")]
  variables <- list()

  for (variable in candidates) {
    modalities <- ordonner_modalites_chrono(docvars[[variable]])
    if (length(modalities) < 2L) next
    variables[[length(variables) + 1L]] <- list(
      id = variable,
      label = nom_variable_chrono(variable),
      modalities = modalities,
      n_modalities = length(modalities),
      suggested_time = est_variable_temporelle_chrono(variable)
    )
  }
  variables
}

decrire_analyse_chrono <- function(source) {
  variables <- variables_chrono_disponibles(source)
  suggested <- vapply(variables, function(variable) isTRUE(variable$suggested_time), logical(1))
  list(
    available = length(variables) >= 1L,
    iramuteq_available = length(variables) >= 1L,
    crossed_available = length(variables) >= 2L,
    variables = variables,
    suggested_time_variable = if (any(suggested)) variables[[which(suggested)[[1L]]]]$id else NULL,
    note = paste(
      "La vue chronologique IRaMuTeQ utilise une variable étoilée.",
      "L'analyse chronologique croisée en utilise deux."
    )
  )
}

ecrire_csv_utf8_chrono <- function(data, path) {
  normalized <- as.data.frame(data, stringsAsFactors = FALSE)
  character_columns <- vapply(normalized, is.character, logical(1))
  normalized[character_columns] <- lapply(normalized[character_columns], enc2utf8)
  connection <- file(path, open = "wt", encoding = "UTF-8")
  on.exit(close(connection), add = TRUE)
  utils::write.csv(normalized, connection, row.names = FALSE, fileEncoding = "")
}

preparer_donnees_chrono <- function(source, time_variable, comparison_variable) {
  docvars <- source$docvars
  classes <- suppressWarnings(as.integer(source$classes))
  if (is.null(docvars) || !is.data.frame(docvars)) {
    stop("Les variables étoilées de cette CHD sont indisponibles.")
  }
  if (!time_variable %in% names(docvars)) {
    stop("La variable temporelle sélectionnée n'est pas disponible.")
  }
  if (!comparison_variable %in% names(docvars)) {
    stop("La variable de comparaison sélectionnée n'est pas disponible.")
  }
  if (identical(time_variable, comparison_variable)) {
    stop("La variable temporelle et la variable de comparaison doivent être différentes.")
  }
  if (length(classes) != nrow(docvars)) {
    stop("Les classes CHD et les variables étoilées ne sont pas alignées.")
  }

  periode <- normaliser_modalite_chrono(docvars[[time_variable]])
  comparaison <- normaliser_modalite_chrono(docvars[[comparison_variable]])
  keep <- !is.na(periode) & !is.na(comparaison) & !is.na(classes) & classes > 0L
  if (sum(keep) < 2L) stop("Pas assez d'UCE classées possèdent les deux variables sélectionnées.")

  document_id <- NULL
  for (candidate in c("segment_source", "doc_id")) {
    if (candidate %in% names(docvars)) {
      document_id <- normaliser_modalite_chrono(docvars[[candidate]])
      break
    }
  }
  if (is.null(document_id)) document_id <- paste0("UCE_", seq_len(nrow(docvars)))
  segment_ids <- as.character(source$segment_ids %||% paste0("UCE_", seq_len(nrow(docvars))))
  if (length(segment_ids) != nrow(docvars)) segment_ids <- paste0("UCE_", seq_len(nrow(docvars)))
  segments <- as.character(source$segments %||% rep(NA_character_, nrow(docvars)))
  if (length(segments) != nrow(docvars)) segments <- rep(NA_character_, nrow(docvars))

  data.frame(
    segment_id = segment_ids[keep],
    periode = periode[keep],
    modalite_comparaison = comparaison[keep],
    classe = paste0("Classe ", classes[keep]),
    document_id = document_id[keep],
    segment = enc2utf8(segments[keep]),
    stringsAsFactors = FALSE
  )
}

construire_tableaux_chrono <- function(data) {
  periods <- ordonner_modalites_chrono(data$periode)
  comparisons <- sort(unique(data$modalite_comparaison), na.last = NA)
  class_ids <- suppressWarnings(as.integer(sub("^Classe\\s+", "", unique(data$classe))))
  classes <- paste0("Classe ", sort(unique(class_ids[is.finite(class_ids)])))

  counts_array <- table(
    factor(data$periode, levels = periods),
    factor(data$modalite_comparaison, levels = comparisons),
    factor(data$classe, levels = classes)
  )
  counts <- as.data.frame(counts_array, responseName = "effectif_uce", stringsAsFactors = FALSE)
  names(counts)[1:3] <- c("periode", "modalite_comparaison", "classe")
  counts$effectif_uce <- as.integer(counts$effectif_uce)

  totals <- stats::aggregate(
    effectif_uce ~ periode + modalite_comparaison,
    data = counts,
    FUN = sum
  )
  names(totals)[[3L]] <- "total_uce_groupe"

  document_rows <- unique(data[c("periode", "modalite_comparaison", "document_id")])
  document_totals <- stats::aggregate(
    document_id ~ periode + modalite_comparaison,
    data = document_rows,
    FUN = length
  )
  names(document_totals)[[3L]] <- "documents_groupe"

  percentages <- merge(counts, totals, by = c("periode", "modalite_comparaison"), all.x = TRUE, sort = FALSE)
  percentages <- merge(percentages, document_totals, by = c("periode", "modalite_comparaison"), all.x = TRUE, sort = FALSE)
  percentages$pourcentage <- ifelse(
    percentages$total_uce_groupe > 0,
    100 * percentages$effectif_uce / percentages$total_uce_groupe,
    NA_real_
  )
  percentages$pourcentage <- round(percentages$pourcentage, 2)
  percentages <- percentages[order(
    match(percentages$periode, periods),
    match(percentages$modalite_comparaison, comparisons),
    match(percentages$classe, classes)
  ), ]
  rownames(percentages) <- NULL

  list(
    counts = counts,
    percentages = percentages,
    periods = periods,
    comparisons = comparisons,
    classes = classes
  )
}

calculer_tests_chrono <- function(data, periods, classes, comparisons) {
  tests <- list()
  residuals <- list()

  for (comparison in comparisons) {
    subset_data <- data[data$modalite_comparaison == comparison, , drop = FALSE]
    contingency <- table(
      factor(subset_data$periode, levels = periods),
      factor(subset_data$classe, levels = classes)
    )
    contingency <- contingency[rowSums(contingency) > 0, colSums(contingency) > 0, drop = FALSE]
    if (nrow(contingency) < 2L || ncol(contingency) < 2L) next

    test <- suppressWarnings(stats::chisq.test(contingency, correct = FALSE))
    n_total <- sum(contingency)
    denominator <- min(nrow(contingency) - 1L, ncol(contingency) - 1L)
    cramer_v <- if (n_total > 0 && denominator > 0) {
      sqrt(as.numeric(test$statistic) / (n_total * denominator))
    } else {
      NA_real_
    }
    tests[[length(tests) + 1L]] <- data.frame(
      modalite_comparaison = comparison,
      chi2 = round(as.numeric(test$statistic), 4),
      ddl = as.integer(test$parameter),
      p_value = as.numeric(test$p.value),
      cramer_v = round(cramer_v, 4),
      n_uce = as.integer(n_total),
      effectifs_attendus_inferieurs_5 = sum(test$expected < 5),
      stringsAsFactors = FALSE
    )

    observed <- as.matrix(contingency)
    expected <- as.matrix(test$expected)
    standardized <- as.matrix(test$stdres)
    for (i in seq_len(nrow(observed))) {
      for (j in seq_len(ncol(observed))) {
        current_residual <- standardized[i, j]
        residuals[[length(residuals) + 1L]] <- data.frame(
          periode = rownames(observed)[[i]],
          modalite_comparaison = comparison,
          classe = colnames(observed)[[j]],
          observe = as.integer(observed[i, j]),
          attendu = round(expected[i, j], 4),
          residu_standardise = round(current_residual, 4),
          p_value_approx = 2 * stats::pnorm(-abs(current_residual)),
          interpretation = if (
            current_residual >= 1.96
          ) "surreprésentée" else if (
            current_residual <= -1.96
          ) "sous-représentée" else "proche de l'attendu",
          stringsAsFactors = FALSE
        )
      }
    }
  }

  tests_df <- if (length(tests)) do.call(rbind, tests) else data.frame(
    modalite_comparaison = character(0), chi2 = numeric(0), ddl = integer(0),
    p_value = numeric(0), cramer_v = numeric(0), n_uce = integer(0),
    effectifs_attendus_inferieurs_5 = integer(0), stringsAsFactors = FALSE
  )
  residuals_df <- if (length(residuals)) do.call(rbind, residuals) else data.frame(
    periode = character(0), modalite_comparaison = character(0), classe = character(0),
    observe = integer(0), attendu = numeric(0), residu_standardise = numeric(0),
    p_value_approx = numeric(0), interpretation = character(0), stringsAsFactors = FALSE
  )
  residuals_df$p_value_ajustee_bh <- if (nrow(residuals_df)) {
    stats::p.adjust(residuals_df$p_value_approx, method = "BH")
  } else {
    numeric(0)
  }
  list(tests = tests_df, residuals = residuals_df)
}

tracer_evolution_chrono <- function(percentages, periods, comparisons, classes, path) {
  panel_rows <- max(1L, length(classes))
  grDevices::png(path, width = 1800, height = max(950, 620 * panel_rows), res = 170)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mfrow = c(panel_rows, 1L), mar = c(7, 5, 4, 2) + 0.1)
  colors <- grDevices::hcl.colors(max(3L, length(comparisons)), "Dark 3")[seq_along(comparisons)]
  finite_percentages <- percentages$pourcentage[is.finite(percentages$pourcentage)]
  common_upper <- max(5, if (length(finite_percentages)) max(finite_percentages) * 1.2 else 5)

  for (class_label in classes) {
    values <- matrix(NA_real_, nrow = length(periods), ncol = length(comparisons))
    for (i in seq_along(periods)) {
      for (j in seq_along(comparisons)) {
        row <- percentages[
          percentages$periode == periods[[i]] &
            percentages$modalite_comparaison == comparisons[[j]] &
            percentages$classe == class_label,
          ,
          drop = FALSE
        ]
        if (nrow(row)) values[i, j] <- row$pourcentage[[1L]]
      }
    }
    values[!is.finite(values)] <- 0
    graphics::barplot(
      t(values),
      beside = TRUE,
      col = colors,
      border = NA,
      names.arg = periods,
      las = 2,
      ylim = c(0, common_upper),
      space = c(0.15, 0.9),
      xlab = "Période",
      ylab = "% des UCE classées",
      main = class_label
    )
    if (identical(class_label, classes[[1L]])) {
      graphics::legend(
        "topright",
        legend = comparisons,
        fill = colors,
        border = NA,
        ncol = min(3L, length(comparisons)),
        cex = 0.75,
        bty = "n"
      )
    }
  }
  grDevices::dev.off()
  on.exit(NULL, add = FALSE)
}

tracer_residus_chrono <- function(residuals, periods, comparisons, classes, path) {
  panels_per_row <- min(2L, max(1L, length(classes)))
  panel_rows <- ceiling(length(classes) / panels_per_row)
  grDevices::png(path, width = 1800, height = max(950, 620 * panel_rows), res = 170)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mfrow = c(panel_rows, panels_per_row), mar = c(7, 10, 4, 2) + 0.1)
  palette <- grDevices::colorRampPalette(c("#e05a47", "#ffffff", "#217ce7"))(201)

  for (class_label in classes) {
    graphics::plot(
      NA, xlim = c(0, length(periods)), ylim = c(0, length(comparisons)),
      xaxs = "i", yaxs = "i", xaxt = "n", yaxt = "n",
      xlab = "Période", ylab = "", main = class_label
    )
    graphics::axis(1, at = seq_along(periods) - 0.5, labels = periods, las = 2, cex.axis = 0.85)
    graphics::axis(2, at = seq_along(comparisons) - 0.5, labels = comparisons, las = 2, cex.axis = 0.8)
    for (i in seq_along(periods)) {
      for (j in seq_along(comparisons)) {
        row <- residuals[
          residuals$periode == periods[[i]] &
            residuals$modalite_comparaison == comparisons[[j]] &
            residuals$classe == class_label,
          ,
          drop = FALSE
        ]
        value <- if (nrow(row)) row$residu_standardise[[1L]] else NA_real_
        color <- "#f0f2f5"
        if (is.finite(value)) {
          index <- round((max(-4, min(4, value)) + 4) / 8 * 200) + 1L
          color <- palette[[index]]
        }
        graphics::rect(i - 1, j - 1, i, j, col = color, border = "#d9e1ea")
        graphics::text(i - 0.5, j - 0.5, if (is.finite(value)) sprintf("%.2f", value) else "—", cex = 0.78)
      }
    }
  }
  grDevices::dev.off()
  on.exit(NULL, add = FALSE)
}

calculer_vue_chronologique_iramuteq <- function(source, time_variable) {
  data <- preparer_donnees_chrono_simple(source, time_variable)
  periods <- ordonner_modalites_chrono(data$periode)
  class_ids <- suppressWarnings(as.integer(sub("^Classe\\s+", "", unique(data$classe))))
  classes <- paste0("Classe ", sort(unique(class_ids[is.finite(class_ids)])))
  contingency <- table(
    factor(data$periode, levels = periods),
    factor(data$classe, levels = classes)
  )
  contingency <- contingency[rowSums(contingency) > 0, colSums(contingency) > 0, drop = FALSE]
  if (nrow(contingency) < 2L || ncol(contingency) < 2L) {
    stop("La variable et la CHD doivent comporter au moins deux modalités et deux classes renseignées.")
  }

  periods <- rownames(contingency)
  classes <- colnames(contingency)
  total <- sum(contingency)
  row_totals <- rowSums(contingency)
  class_totals <- colSums(contingency)
  proportions <- prop.table(contingency, margin = 1L) * 100
  long_proportions <- list()
  long_chi2 <- list()

  for (i in seq_along(periods)) {
    for (j in seq_along(classes)) {
      observed <- as.numeric(contingency[i, j])
      table_2x2 <- matrix(c(
        observed,
        row_totals[[i]] - observed,
        class_totals[[j]] - observed,
        total - row_totals[[i]] - class_totals[[j]] + observed
      ), nrow = 2L, byrow = TRUE)
      test <- suppressWarnings(stats::chisq.test(table_2x2, correct = FALSE))
      expected <- as.numeric(test$expected[1L, 1L])
      chi2_value <- as.numeric(test$statistic)
      if (!is.finite(chi2_value)) chi2_value <- 0
      if (observed < expected) chi2_value <- -chi2_value

      long_proportions[[length(long_proportions) + 1L]] <- data.frame(
        periode = periods[[i]],
        classe = classes[[j]],
        effectif_uce = as.integer(observed),
        total_uce_periode = as.integer(row_totals[[i]]),
        pourcentage = round(as.numeric(proportions[i, j]), 2),
        stringsAsFactors = FALSE
      )
      long_chi2[[length(long_chi2) + 1L]] <- data.frame(
        periode = periods[[i]],
        classe = classes[[j]],
        observe = as.integer(observed),
        attendu = round(expected, 4),
        chi2 = round(chi2_value, 4),
        p_value = as.numeric(test$p.value),
        interpretation = if (
          chi2_value > 0
        ) "surreprésentée" else if (
          chi2_value < 0
        ) "sous-représentée" else "proche de l'attendu",
        stringsAsFactors = FALSE
      )
    }
  }

  global_test <- suppressWarnings(stats::chisq.test(contingency, correct = FALSE))
  denominator <- min(nrow(contingency) - 1L, ncol(contingency) - 1L)
  cramer_v <- if (total > 0 && denominator > 0) {
    sqrt(as.numeric(global_test$statistic) / (total * denominator))
  } else {
    NA_real_
  }
  global <- data.frame(
    variable = nom_variable_chrono(time_variable),
    chi2 = round(as.numeric(global_test$statistic), 4),
    ddl = as.integer(global_test$parameter),
    p_value = as.numeric(global_test$p.value),
    cramer_v = round(cramer_v, 4),
    n_uce = as.integer(total),
    effectifs_attendus_inferieurs_5 = sum(global_test$expected < 5),
    stringsAsFactors = FALSE
  )

  list(
    data = data,
    contingency = contingency,
    proportions = do.call(rbind, long_proportions),
    chi2 = do.call(rbind, long_chi2),
    global = global,
    periods = periods,
    classes = classes
  )
}

preparer_donnees_chrono_simple <- function(source, time_variable) {
  docvars <- source$docvars
  classes <- suppressWarnings(as.integer(source$classes))
  if (is.null(docvars) || !is.data.frame(docvars) || !time_variable %in% names(docvars)) {
    stop("La variable chronologique sélectionnée n'est pas disponible.")
  }
  if (length(classes) != nrow(docvars)) {
    stop("Les classes CHD et la variable chronologique ne sont pas alignées.")
  }
  periode <- normaliser_modalite_chrono(docvars[[time_variable]])
  keep <- !is.na(periode) & !is.na(classes) & classes > 0L
  if (sum(keep) < 2L) stop("Pas assez d'UCE classées possèdent la variable sélectionnée.")

  document_id <- NULL
  for (candidate in c("segment_source", "doc_id")) {
    if (candidate %in% names(docvars)) {
      document_id <- normaliser_modalite_chrono(docvars[[candidate]])
      break
    }
  }
  if (is.null(document_id)) document_id <- paste0("UCE_", seq_len(nrow(docvars)))
  data.frame(
    periode = periode[keep],
    classe = paste0("Classe ", classes[keep]),
    document_id = document_id[keep],
    stringsAsFactors = FALSE
  )
}

tracer_proportions_iramuteq <- function(view, path) {
  matrix_values <- t(prop.table(view$contingency, margin = 1L) * 100)
  colors <- grDevices::hcl.colors(max(3L, nrow(matrix_values)), "Dark 3")[seq_len(nrow(matrix_values))]
  grDevices::png(path, width = 1800, height = 1050, res = 170)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mar = c(8, 6, 4, 2) + 0.1)
  graphics::barplot(
    matrix_values,
    col = colors,
    border = NA,
    names.arg = view$periods,
    las = 2,
    ylab = "% des UCE classées",
    main = "Vue chronologique IRaMuTeQ - Proportions"
  )
  graphics::legend("topright", legend = view$classes, fill = colors, bty = "n", cex = 0.85)
  grDevices::dev.off()
  on.exit(NULL, add = FALSE)
}

tracer_chi2_iramuteq <- function(view, path) {
  values <- matrix(
    view$chi2$chi2,
    nrow = length(view$periods),
    ncol = length(view$classes),
    byrow = TRUE,
    dimnames = list(view$periods, view$classes)
  )
  palette <- grDevices::colorRampPalette(c("#e05a47", "#ffffff", "#217ce7"))(201)
  limit <- max(3.84, max(abs(values), na.rm = TRUE))
  grDevices::png(path, width = 1800, height = max(950, 150 + 125 * length(view$classes)), res = 170)
  old_par <- graphics::par(no.readonly = TRUE)
  on.exit({ graphics::par(old_par); grDevices::dev.off() }, add = TRUE)
  graphics::par(mar = c(8, 10, 4, 2) + 0.1)
  graphics::plot(
    NA,
    xlim = c(0, length(view$periods)), ylim = c(0, length(view$classes)),
    xaxs = "i", yaxs = "i", xaxt = "n", yaxt = "n",
    xlab = "Modalité chronologique", ylab = "",
    main = "Vue chronologique IRaMuTeQ - χ²"
  )
  graphics::axis(1, at = seq_along(view$periods) - 0.5, labels = view$periods, las = 2, cex.axis = 0.85)
  graphics::axis(2, at = seq_along(view$classes) - 0.5, labels = view$classes, las = 2, cex.axis = 0.85)
  for (i in seq_along(view$periods)) {
    for (j in seq_along(view$classes)) {
      value <- values[i, j]
      index <- round((max(-limit, min(limit, value)) + limit) / (2 * limit) * 200) + 1L
      graphics::rect(i - 1, j - 1, i, j, col = palette[[index]], border = "#d9e1ea")
      graphics::text(i - 0.5, j - 0.5, sprintf("%.2f", value), cex = 0.78)
    }
  }
  grDevices::dev.off()
  on.exit(NULL, add = FALSE)
}

ecrire_resultats_chrono_iramuteq <- function(source, time_variable, output_dir) {
  available <- vapply(variables_chrono_disponibles(source), `[[`, character(1), "id")
  if (!time_variable %in% available) {
    stop("La variable sélectionnée doit comporter au moins deux modalités.")
  }
  view <- calculer_vue_chronologique_iramuteq(source, time_variable)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  ecrire_csv_utf8_chrono(view$proportions, file.path(output_dir, "vue_chronologique_proportions.csv"))
  ecrire_csv_utf8_chrono(view$chi2, file.path(output_dir, "vue_chronologique_chi2.csv"))
  ecrire_csv_utf8_chrono(view$global, file.path(output_dir, "vue_chronologique_test_global.csv"))
  tracer_proportions_iramuteq(view, file.path(output_dir, "vue_chronologique_proportions.png"))
  tracer_chi2_iramuteq(view, file.path(output_dir, "vue_chronologique_chi2.png"))

  configuration <- list(
    analysis_mode = "iramuteq",
    analysis_mode_label = "Vue chronologique IRaMuTeQ",
    time_variable = time_variable,
    time_variable_label = nom_variable_chrono(time_variable),
    comparison_variable = NULL,
    comparison_variable_label = NULL,
    periods = view$periods,
    classes = view$classes,
    unit = "UCE classées",
    normalization = "Pourcentage des classes calculé dans chaque modalité de la variable sélectionnée.",
    method = paste(
      "Reproduction fonctionnelle de la Chronological view d'IRaMuTeQ :",
      "proportions par modalité et χ² 2 × 2 entre chaque modalité et chaque classe."
    )
  )
  jsonlite::write_json(
    configuration, file.path(output_dir, "configuration_chronologie.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null"
  )
  summary <- c(configuration, list(
    n_periods = length(view$periods),
    n_comparison_modalities = 0L,
    n_classes = length(view$classes),
    n_uce = nrow(view$data),
    n_documents = length(unique(view$data$document_id)),
    n_chi2_tests = nrow(view$chi2)
  ))
  jsonlite::write_json(
    summary, file.path(output_dir, "resume_chronologie.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null"
  )
  list(summary = summary, proportions = view$proportions, chi2 = view$chi2, global = view$global)
}

ecrire_resultats_chrono_croisee <- function(source, time_variable, comparison_variable, output_dir) {
  available <- vapply(variables_chrono_disponibles(source), `[[`, character(1), "id")
  if (!time_variable %in% available || !comparison_variable %in% available) {
    stop("Les deux variables sélectionnées doivent comporter au moins deux modalités.")
  }

  data <- preparer_donnees_chrono(source, time_variable, comparison_variable)
  tables <- construire_tableaux_chrono(data)
  tests <- calculer_tests_chrono(data, tables$periods, tables$classes, tables$comparisons)
  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

  counts_export <- tables$percentages[c(
    "periode", "modalite_comparaison", "classe", "effectif_uce", "total_uce_groupe", "documents_groupe"
  )]
  percentages_export <- tables$percentages[c(
    "periode", "modalite_comparaison", "classe", "effectif_uce", "total_uce_groupe", "pourcentage", "documents_groupe"
  )]
  ecrire_csv_utf8_chrono(counts_export, file.path(output_dir, "chronologie_croisee_effectifs.csv"))
  ecrire_csv_utf8_chrono(percentages_export, file.path(output_dir, "chronologie_croisee_pourcentages.csv"))
  ecrire_csv_utf8_chrono(tests$tests, file.path(output_dir, "chronologie_croisee_chi2.csv"))
  ecrire_csv_utf8_chrono(tests$residuals, file.path(output_dir, "chronologie_croisee_residus.csv"))
  segments_export <- data[c(
    "segment_id", "periode", "modalite_comparaison", "classe", "document_id", "segment"
  )]
  segments_export <- segments_export[
    !is.na(segments_export$segment) & nzchar(trimws(segments_export$segment)),
    ,
    drop = FALSE
  ]
  ecrire_csv_utf8_chrono(segments_export, file.path(output_dir, "chronologie_croisee_segments.csv"))

  tracer_evolution_chrono(
    tables$percentages, tables$periods, tables$comparisons, tables$classes,
    file.path(output_dir, "chronologie_croisee_evolution.png")
  )
  tracer_residus_chrono(
    tests$residuals, tables$periods, tables$comparisons, tables$classes,
    file.path(output_dir, "chronologie_croisee_residus.png")
  )

  configuration <- list(
    analysis_mode = "crossed",
    analysis_mode_label = "Analyse chronologique croisée",
    time_variable = time_variable,
    time_variable_label = nom_variable_chrono(time_variable),
    comparison_variable = comparison_variable,
    comparison_variable_label = nom_variable_chrono(comparison_variable),
    periods = tables$periods,
    comparison_modalities = tables$comparisons,
    classes = tables$classes,
    unit = "UCE classées",
    normalization = "Pourcentage calculé dans chaque couple période × modalité de comparaison.",
    method = "Croisement descriptif des classes CHD et test χ² classe × période séparé pour chaque modalité de comparaison."
  )
  jsonlite::write_json(
    configuration, file.path(output_dir, "configuration_chronologie.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null"
  )
  summary <- c(configuration, list(
    n_periods = length(tables$periods),
    n_comparison_modalities = length(tables$comparisons),
    n_classes = length(tables$classes),
    n_uce = nrow(data),
    n_documents = length(unique(data$document_id)),
    n_segments_exported = nrow(segments_export),
    n_chi2_tests = nrow(tests$tests)
  ))
  jsonlite::write_json(
    summary, file.path(output_dir, "resume_chronologie.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null"
  )
  list(summary = summary, percentages = percentages_export, tests = tests$tests, residuals = tests$residuals)
}

ecrire_resultats_chrono <- function(
  source,
  time_variable,
  comparison_variable = NULL,
  output_dir,
  analysis_mode = "crossed"
) {
  mode <- trimws(tolower(as.character(analysis_mode %||% "crossed")))
  if (identical(mode, "iramuteq")) {
    return(ecrire_resultats_chrono_iramuteq(source, time_variable, output_dir))
  }
  if (!identical(mode, "crossed")) stop("Mode d'analyse chronologique non reconnu.")
  ecrire_resultats_chrono_croisee(source, time_variable, comparison_variable, output_dir)
}
