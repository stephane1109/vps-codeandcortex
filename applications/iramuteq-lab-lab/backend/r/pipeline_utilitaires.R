# Utilitaires partages du runner batch IRAMUTEQ Lab.
# Les fonctions sont extraites sans modification de leur comportement.

split_lib_paths <- function(value) {
  if (is.null(value) || !length(value)) return(character(0))
  parts <- trimws(unlist(strsplit(as.character(value[[1]]), .Platform$path.sep, fixed = TRUE), use.names = FALSE))
  parts[nzchar(parts)]
}
configure_runtime_library_paths <- function() {
  lib_target <- Sys.getenv("IRAMUTEQ_R_LIBS_USER", unset = "")
  system_candidates <- unique(c(
    if (nzchar(lib_target)) lib_target else character(0),
    split_lib_paths(Sys.getenv("IRAMUTEQ_R_SYSTEM_LIBS", unset = "")),
    split_lib_paths(Sys.getenv("R_LIBS_SITE", unset = "")),
    "/usr/lib/R/site-library",
    "/usr/lib/R/library",
    "/usr/local/lib/R/site-library",
    "/usr/local/lib/R/library",
    .libPaths()
  ))
  .libPaths(unique(Filter(dir.exists, system_candidates)))
}

configure_runtime_library_paths()

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0) y else x
}

.iramuteq_runtime_cache <- new.env(parent = emptyenv())

parse_args <- function(args) {
  out <- list()
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) {
      stop(paste0("Argument inattendu: ", key))
    }
    if (i == length(args)) {
      stop(paste0("Valeur manquante pour ", key))
    }
    out[[substring(key, 3L)]] <- args[[i + 1L]]
    i <- i + 2L
  }
  out
}

get_simi_terms_choices_batch <- function(dfm_obj) {
  if (is.null(dfm_obj) || quanteda::ndoc(dfm_obj) < 1 || quanteda::nfeat(dfm_obj) < 1) {
    return(list(terms = list(), ordered_terms = character(0)))
  }

  mat_dfm <- as.matrix(dfm_obj)
  mat_bin <- ifelse(mat_dfm > 0, 1, 0)
  freq <- colSums(mat_bin)
  if (!length(freq)) {
    return(list(terms = list(), ordered_terms = character(0)))
  }

  ord <- order(freq, decreasing = TRUE)
  ordered_terms <- names(freq)[ord]
  terms <- lapply(seq_along(ordered_terms), function(i) {
    term <- ordered_terms[[i]]
    frequency <- as.integer(freq[ord][[i]])
    list(
      term = term,
      frequency = frequency,
      label = paste0(term, " (", frequency, ")")
    )
  })

  list(terms = terms, ordered_terms = ordered_terms)
}

scalar_chr <- function(x, default = "") {
  if (is.null(x) || !length(x) || is.na(x[[1]]) || !nzchar(as.character(x[[1]]))) {
    default
  } else {
    as.character(x[[1]])
  }
}

scalar_int <- function(x, default = 0L, min_value = NULL) {
  value <- suppressWarnings(as.integer(x[[1]]))
  if (!length(value) || is.na(value) || !is.finite(value)) value <- as.integer(default)
  if (!is.null(min_value) && value < min_value) value <- as.integer(min_value)
  as.integer(value)
}

scalar_num <- function(x, default = 0) {
  value <- suppressWarnings(as.numeric(x[[1]]))
  if (!length(value) || is.na(value) || !is.finite(value)) value <- as.numeric(default)
  as.numeric(value)
}

scalar_bool <- function(x, default = FALSE) {
  if (is.null(x) || !length(x)) return(isTRUE(default))
  value <- x[[1]]
  if (is.logical(value)) return(isTRUE(value))
  if (is.numeric(value)) return(!is.na(value) && value != 0)
  value_chr <- tolower(trimws(as.character(value)))
  if (!nzchar(value_chr)) return(isTRUE(default))
  value_chr %in% c("1", "true", "vrai", "yes", "oui")
}

normaliser_ngram_range_batch <- function(x, default = c(1L, 1L)) {
  vals <- suppressWarnings(as.integer(as_char_vec(x, as.character(default))))
  vals <- vals[is.finite(vals) & !is.na(vals)]
  if (!length(vals)) vals <- as.integer(default)
  if (length(vals) == 1L) vals <- c(vals[[1]], vals[[1]])
  vals <- vals[seq_len(min(2L, length(vals)))]
  min_ngram <- min(2L, max(1L, as.integer(vals[[1]])))
  max_ngram <- min(2L, max(min_ngram, as.integer(vals[[2]])))
  c(min_ngram, max_ngram)
}

as_char_vec <- function(x, default = character(0)) {
  if (is.null(x) || !length(x)) return(default)
  vals <- as.character(unlist(x, use.names = FALSE))
  vals <- trimws(vals)
  vals[nzchar(vals)]
}

write_json_atomic <- function(payload, path) {
  target_dir <- dirname(path)
  dir.create(target_dir, recursive = TRUE, showWarnings = FALSE)
  temp_path <- tempfile(
    pattern = paste0(".", basename(path), "-"),
    tmpdir = target_dir,
    fileext = ".tmp"
  )
  on.exit(unlink(temp_path, force = TRUE), add = TRUE)

  jsonlite::write_json(payload, temp_path, auto_unbox = TRUE, pretty = TRUE, null = "null")
  if (!file.rename(temp_path, path)) {
    stop(paste0("Impossible de publier atomiquement le fichier JSON : ", path))
  }
}

log_info <- function(message, progress = NULL) {
  line <- paste0("[", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "] ", message)
  job_logs <<- c(job_logs, line)
  cat(line, "\n")
  flush.console()
  if (!is.null(progress)) {
    write_status(progress = progress, message = message)
  }
}

clamp_int <- function(value, min_value, max_value) {
  value <- as.integer(value)
  value <- max(as.integer(min_value), value, na.rm = TRUE)
  value <- min(as.integer(max_value), value, na.rm = TRUE)
  as.integer(value)
}

formater_df_csv_6_decimales <- function(df) {
  if (is.null(df)) return(df)
  out <- df
  for (name in names(out)) {
    if (is.numeric(out[[name]])) {
      out[[name]] <- ifelse(
        is.na(out[[name]]),
        NA_character_,
        formatC(out[[name]], format = "f", digits = 6)
      )
    }
  }
  out
}

formatter_p_affiche_batch <- function(x) {
  vals <- suppressWarnings(as.numeric(x))
  ifelse(
    is.na(vals),
    NA_character_,
    ifelse(vals == 0, "< 1e-323", formatC(vals, format = "f", digits = 6))
  )
}

formatter_p_scientifique_batch <- function(x, log_p = NULL) {
  vals <- suppressWarnings(as.numeric(x))
  logs <- rep(NA_real_, length(vals))
  if (!is.null(log_p)) {
    logs_in <- suppressWarnings(as.numeric(log_p))
    n <- min(length(logs), length(logs_in))
    if (n > 0L) logs[seq_len(n)] <- logs_in[seq_len(n)]
  }

  out <- rep(NA_character_, length(vals))
  has_log <- !is.na(logs) & is.finite(logs)
  if (any(has_log)) {
    log10_vals <- logs[has_log] / log(10)
    exponents <- floor(log10_vals)
    mantissas <- round(10^(log10_vals - exponents), digits = 5L)
    carry <- mantissas >= 10
    if (any(carry)) {
      mantissas[carry] <- mantissas[carry] / 10
      exponents[carry] <- exponents[carry] + 1L
    }
    out[has_log] <- paste0(
      formatC(mantissas, format = "f", digits = 5L),
      sprintf("e%+03d", as.integer(exponents))
    )
  }

  fallback <- !has_log & !is.na(vals)
  if (any(fallback)) {
    out[fallback] <- ifelse(
      vals[fallback] == 0,
      "< 1e-323",
      format(vals[fallback], scientific = TRUE, digits = 6)
    )
  }
  out
}

formatter_p_seuil_01_batch <- function(x) {
  vals <- suppressWarnings(as.numeric(x))
  ifelse(
    is.na(vals),
    NA_character_,
    ifelse(vals <= 0.01, "p ≤ 0.01", "")
  )
}

coords_have_two_axes <- function(coords) {
  !is.null(coords) && (is.matrix(coords) || is.data.frame(coords)) && ncol(coords) >= 2
}

coords_have_at_least_one_axis <- function(coords) {
  if (is.null(coords)) return(FALSE)
  if (is.vector(coords)) return(length(coords) >= 1L)
  (is.matrix(coords) || is.data.frame(coords)) && ncol(coords) >= 1
}

normaliser_id_classe_local <- function(x) {
  x_chr <- trimws(as.character(x))
  x_num <- suppressWarnings(as.numeric(x_chr))
  need_extract <- is.na(x_num) & !is.na(x_chr) & nzchar(x_chr)

  if (any(need_extract)) {
    extrait <- sub("^.*?(\\d+).*$", "\\1", x_chr[need_extract])
    extrait[!grepl("\\d", x_chr[need_extract])] <- NA_character_
    x_num[need_extract] <- suppressWarnings(as.numeric(extrait))
  }

  x_num
}
