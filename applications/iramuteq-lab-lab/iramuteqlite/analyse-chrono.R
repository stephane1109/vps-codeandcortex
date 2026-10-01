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
    available = length(variables) >= 2L,
    variables = variables,
    suggested_time_variable = if (any(suggested)) variables[[which(suggested)[[1L]]]]$id else NULL,
    note = "Sélectionnez une variable temporelle et une autre variable étoilée pour comparer les classes CHD."
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

  data.frame(
    periode = periode[keep],
    modalite_comparaison = comparaison[keep],
    classe = paste0("Classe ", classes[keep]),
    document_id = document_id[keep],
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
    upper <- max(5, max(values, na.rm = TRUE) * 1.15)
    graphics::matplot(
      seq_along(periods), values,
      type = "o", lty = 1, lwd = 2.2, pch = 16,
      col = colors, xaxt = "n", ylim = c(0, upper),
      xlab = "Période", ylab = "% des UCE classées", main = class_label
    )
    graphics::axis(1, at = seq_along(periods), labels = periods, las = 2, cex.axis = 0.85)
    graphics::grid(col = "#e6edf5")
    if (identical(class_label, classes[[1L]])) {
      graphics::legend("topright", legend = comparisons, col = colors, lty = 1, pch = 16, cex = 0.78, bty = "n")
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

ecrire_resultats_chrono <- function(source, time_variable, comparison_variable, output_dir) {
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

  tracer_evolution_chrono(
    tables$percentages, tables$periods, tables$comparisons, tables$classes,
    file.path(output_dir, "chronologie_croisee_evolution.png")
  )
  tracer_residus_chrono(
    tests$residuals, tables$periods, tables$comparisons, tables$classes,
    file.path(output_dir, "chronologie_croisee_residus.png")
  )

  configuration <- list(
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
    n_chi2_tests = nrow(tests$tests)
  ))
  jsonlite::write_json(
    summary, file.path(output_dir, "resume_chronologie.json"),
    auto_unbox = TRUE, pretty = TRUE, null = "null"
  )
  list(summary = summary, percentages = percentages_export, tests = tests$tests, residuals = tests$residuals)
}
