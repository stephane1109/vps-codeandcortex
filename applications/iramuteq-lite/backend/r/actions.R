#!/usr/bin/env Rscript

args <- commandArgs(trailingOnly = TRUE)
options(encoding = "UTF-8")

for (candidate in c("C.UTF-8", "en_US.UTF-8", "fr_FR.UTF-8")) {
  ok <- tryCatch(!is.na(suppressWarnings(Sys.setlocale("LC_CTYPE", candidate))), error = function(...) FALSE)
  if (isTRUE(ok)) break
}

read_option <- function(arguments, name, default = NULL) {
  key <- paste0("--", name)
  idx <- match(key, arguments)
  if (is.na(idx)) return(default)
  if (idx >= length(arguments)) return(default)
  arguments[[idx + 1L]]
}

output_json <- function(payload, status = 0L) {
  cat(jsonlite::toJSON(payload, auto_unbox = TRUE, pretty = TRUE, null = "null"))
  quit(save = "no", status = status)
}

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  stop("Le package R jsonlite est requis pour actions.R.")
}

logs <- character(0)
log_info <- function(message) {
  logs <<- c(logs, as.character(message))
}

normalize_class_value <- function(value) {
  raw <- trimws(enc2utf8(as.character(value %||% "")))
  if (!nzchar(raw)) return("Sans classe")
  stripped <- sub("^classe\\s+", "", raw, ignore.case = TRUE)
  stripped <- sub(":$", "", stripped)
  stripped <- trimws(if (nzchar(stripped)) stripped else raw)
  numeric_value <- suppressWarnings(as.numeric(stripped))
  if (!is.na(numeric_value)) {
    if (abs(numeric_value - round(numeric_value)) < .Machine$double.eps^0.5) {
      return(as.character(as.integer(round(numeric_value))))
    }
    return(as.character(numeric_value))
  }
  stripped
}

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0) y else x
}

normalize_text_token <- function(value) {
  tolower(trimws(enc2utf8(as.character(value %||% ""))))
}

segment_contains_term <- function(segment, term) {
  term_norm <- normalize_text_token(term)
  if (!nzchar(term_norm)) return(FALSE)

  segment_norm <- normalize_text_token(gsub("[[:punct:]]+", " ", enc2utf8(as.character(segment)), perl = TRUE))
  tokens <- unlist(strsplit(segment_norm, "\\s+", perl = TRUE), use.names = FALSE)
  any(tokens == term_norm)
}

parse_segments_by_class <- function(path) {
  if (!file.exists(path)) {
    stop("Le fichier segments_par_classe.txt est introuvable.")
  }

  lines <- strsplit(read_utf8_text(path), "\r?\n", perl = TRUE)[[1]]
  groups <- list()
  current_class <- NULL

  for (line in lines) {
    trimmed <- trimws(line)
    header_match <- regexec("^Classe\\s+(.+?)\\s*:\\s*$", trimmed, ignore.case = TRUE)
    header_parts <- regmatches(trimmed, header_match)[[1]]

    if (length(header_parts) > 1L) {
      current_class <- normalize_class_value(header_parts[[2]])
      if (is.null(groups[[current_class]])) groups[[current_class]] <- character(0)
      next
    }

    if (!nzchar(trimmed) || is.null(current_class)) next
    groups[[current_class]] <- c(groups[[current_class]], trimmed)
  }

  groups
}

read_stats_table <- function(path) {
  if (!file.exists(path)) {
    stop("Le fichier stats_par_classe.csv est introuvable.")
  }

  text <- read_utf8_text(path)
  if (!nzchar(trimws(text))) return(data.frame())
  utils::read.csv(
    text = paste0(text, "\n"),
    stringsAsFactors = FALSE,
    check.names = FALSE
  )
}

read_utf8_text <- function(path) {
  con <- file(path, open = "rb")
  on.exit(close(con), add = TRUE)
  bytes <- readBin(con, what = "raw", n = file.info(path)$size)
  text <- rawToChar(bytes)
  Encoding(text) <- "UTF-8"
  enc2utf8(text)
}

safe_numeric <- function(x) {
  value <- suppressWarnings(as.numeric(x))
  if (length(value) == 0L || is.na(value)) return(NULL)
  value
}

sort_class_labels <- function(labels) {
  labels <- unique(as.character(labels))
  numeric_values <- suppressWarnings(as.numeric(labels))
  numeric_idx <- !is.na(numeric_values)
  c(labels[numeric_idx][order(numeric_values[numeric_idx])], sort(labels[!numeric_idx]))
}

action <- enc2utf8(read_option(args, "action"))
output_dir <- enc2utf8(read_option(args, "output-dir"))
term <- trimws(enc2utf8(as.character(read_option(args, "term", ""))))
class_label <- normalize_class_value(read_option(args, "class", ""))
max_segments <- suppressWarnings(as.integer(read_option(args, "max-segments", "300")))
if (is.na(max_segments) || max_segments < 1L) max_segments <- 300L

if (!nzchar(output_dir %||% "")) {
  output_json(list(success = FALSE, message = "Le dossier d'exports est requis.", logs = logs), status = 1L)
}

if (!nzchar(action %||% "")) {
  output_json(list(success = FALSE, message = "L'action demandée est requise.", logs = logs), status = 1L)
}

if (!nzchar(term)) {
  output_json(list(success = FALSE, message = "La forme sélectionnée est requise.", logs = logs), status = 1L)
}

output_dir <- normalizePath(output_dir, winslash = "/", mustWork = FALSE)
stats_path <- file.path(output_dir, "stats_par_classe.csv")
segments_path <- file.path(output_dir, "segments_par_classe.txt")

result <- tryCatch(
  {
    log_info(paste0("Action CHD demandée : ", action, " pour la forme '", term, "'."))

    if (identical(action, "chi2-class")) {
      stats_df <- read_stats_table(stats_path)
      if (!nrow(stats_df)) stop("Le tableau stats_par_classe.csv est vide.")

      class_column <- if ("Classe_brut" %in% names(stats_df)) "Classe_brut" else if ("Classe" %in% names(stats_df)) "Classe" else NULL
      if (is.null(class_column) || !"Terme" %in% names(stats_df)) {
        stop("Le fichier stats_par_classe.csv ne contient pas les colonnes attendues.")
      }

      classes_norm <- vapply(stats_df[[class_column]], normalize_class_value, character(1))
      term_values <- trimws(as.character(stats_df$Terme))
      term_idx <- which(term_values == term)
      if (!length(term_idx)) {
        stop("Aucune statistique n'a été trouvée pour cette forme.")
      }

      df_term <- stats_df[term_idx, , drop = FALSE]
      df_term$classLabel <- classes_norm[term_idx]
      df_term$chi2_numeric <- suppressWarnings(as.numeric(df_term$chi2))
      df_term$p_numeric <- suppressWarnings(as.numeric(df_term$p_value %||% df_term$p))
      df_term$eff_st_numeric <- suppressWarnings(as.numeric(df_term$eff_st))
      df_term$eff_total_numeric <- suppressWarnings(as.numeric(df_term$eff_total))
      df_term$frequency_numeric <- suppressWarnings(as.numeric(df_term$frequency))
      df_term$pourcentage_numeric <- suppressWarnings(as.numeric(df_term$pourcentage))
      df_term$docprop_numeric <- suppressWarnings(as.numeric(df_term$docprop))
      df_term$lr_numeric <- suppressWarnings(as.numeric(df_term$lr))

      if (nzchar(class_label) && !class_label %in% df_term$classLabel) {
        stop("Aucune statistique n'a été trouvée pour cette forme dans la classe sélectionnée.")
      }

      ordered_classes <- sort_class_labels(df_term$classLabel)
      df_term <- df_term[match(ordered_classes, df_term$classLabel), , drop = FALSE]
      classes_payload <- lapply(seq_len(nrow(df_term)), function(i) {
        row <- df_term[i, , drop = FALSE]
        list(
          classLabel = as.character(row$classLabel[[1]]),
          chi2 = safe_numeric(row$chi2_numeric),
          pValue = safe_numeric(row$p_numeric),
          effSt = safe_numeric(row$eff_st_numeric),
          effTotal = safe_numeric(row$eff_total_numeric),
          frequency = safe_numeric(row$frequency_numeric),
          pourcentage = safe_numeric(row$pourcentage_numeric),
          docprop = safe_numeric(row$docprop_numeric),
          lr = safe_numeric(row$lr_numeric),
          isSelected = identical(as.character(row$classLabel[[1]]), class_label)
        )
      })

      selected_row <- NULL
      if (nzchar(class_label)) {
        selected_idx <- match(class_label, df_term$classLabel)
        if (!is.na(selected_idx)) selected_row <- df_term[selected_idx, , drop = FALSE]
      }

      list(
        success = TRUE,
        action = action,
        term = term,
        classLabel = class_label,
        title = paste0("Forme : ", term),
        meta = "χ² par classe : comparaison de la forme entre toutes les classes",
        payload = list(
          term = term,
          selectedClassLabel = if (nzchar(class_label)) class_label else NULL,
          selectedChi2 = if (!is.null(selected_row)) safe_numeric(selected_row$chi2_numeric) else NULL,
          selectedPValue = if (!is.null(selected_row)) safe_numeric(selected_row$p_numeric) else NULL,
          type = trimws(as.character((selected_row %||% df_term[1, , drop = FALSE])$Type %||% "")),
          classes = classes_payload
        ),
        logs = unname(as.list(logs))
      )
    } else if (identical(action, "segments-class")) {
      groups <- parse_segments_by_class(segments_path)
      segments <- groups[[class_label]] %||% character(0)
      segments <- segments[vapply(segments, segment_contains_term, logical(1), term = term)]
      segments <- utils::head(segments, max_segments)

      list(
        success = TRUE,
        action = action,
        term = term,
        classLabel = class_label,
        title = paste0("Classe ", class_label, " - forme : ", term),
        meta = if (length(segments)) {
          paste0("Segments trouvés : ", length(segments))
        } else {
          "Aucun segment trouvé pour cette forme dans la classe sélectionnée."
        },
        payload = list(
          classLabel = class_label,
          count = length(segments),
          segments = unname(as.list(segments))
        ),
        logs = unname(as.list(logs))
      )
    } else if (identical(action, "segments-all-classes")) {
      groups <- parse_segments_by_class(segments_path)
      class_labels <- sort_class_labels(names(groups))
      grouped_results <- lapply(class_labels, function(label) {
        segments <- groups[[label]] %||% character(0)
        segments <- segments[vapply(segments, segment_contains_term, logical(1), term = term)]
        if (!length(segments)) return(NULL)
        list(
          classLabel = label,
          count = length(segments),
          segments = unname(as.list(utils::head(segments, max_segments)))
        )
      })
      grouped_results <- Filter(Negate(is.null), grouped_results)

      total_segments <- sum(vapply(grouped_results, function(entry) entry$count %||% 0L, integer(1)))
      total_classes <- length(grouped_results)

      list(
        success = TRUE,
        action = action,
        term = term,
        classLabel = NULL,
        title = paste0("Forme : ", term),
        meta = if (total_segments > 0L) {
          paste0("Segments trouvés dans ", total_classes, " classe(s) : ", total_segments)
        } else {
          "Aucun segment trouvé pour cette forme dans les classes."
        },
        payload = list(
          totalClasses = total_classes,
          totalSegments = total_segments,
          classes = grouped_results
        ),
        logs = unname(as.list(logs))
      )
    } else {
      stop("Action CHD non reconnue.")
    }
  },
  error = function(error) {
    list(
      success = FALSE,
      action = action,
      term = term,
      classLabel = if (nzchar(class_label)) class_label else NULL,
      message = conditionMessage(error),
      logs = unname(as.list(c(logs, paste0("Erreur : ", conditionMessage(error)))))
    )
  }
)

output_json(result, status = if (isTRUE(result$success)) 0L else 1L)
