#!/usr/bin/env Rscript

suppressWarnings(options(stringsAsFactors = FALSE))
invisible(suppressWarnings(try(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"), silent = TRUE)))

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0) y else x
}

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

normaliser_add_expression_df_batch <- function(df) {
  if (is.list(df) && !is.data.frame(df)) {
    if (!length(df)) return(NULL)
    if (all(vapply(df, is.list, logical(1)))) {
      rows <- lapply(df, function(entry) {
        data.frame(
          dic_mot = as.character(entry$dic_mot %||% ""),
          dic_norm = as.character(entry$dic_norm %||% ""),
          dic_morpho = as.character(entry$dic_morpho %||% ""),
          stringsAsFactors = FALSE
        )
      })
      df <- do.call(rbind, rows)
    } else {
      df <- tryCatch(as.data.frame(df, stringsAsFactors = FALSE), error = function(e) NULL)
    }
  }
  if (is.null(df) || !is.data.frame(df)) return(NULL)
  noms <- names(df)
  noms <- gsub("^\ufeff", "", noms, perl = TRUE)
  names(df) <- noms
  if (!all(c("dic_mot", "dic_norm") %in% names(df))) return(NULL)
  if (!"dic_morpho" %in% names(df)) df$dic_morpho <- ""
  df <- df[, c("dic_mot", "dic_norm", "dic_morpho"), drop = FALSE]
  df$dic_mot[is.na(df$dic_mot)] <- ""
  df$dic_norm[is.na(df$dic_norm)] <- ""
  df$dic_morpho[is.na(df$dic_morpho)] <- ""
  df$dic_mot <- tolower(trimws(as.character(df$dic_mot)))
  df$dic_mot <- gsub("[’`´ʼʹ]", "'", df$dic_mot, perl = TRUE)
  df$dic_norm <- tolower(trimws(as.character(df$dic_norm)))
  df$dic_norm <- gsub("[’`´ʼʹ]", "'", df$dic_norm, perl = TRUE)
  df$dic_morpho <- trimws(as.character(df$dic_morpho))
  df <- df[nzchar(df$dic_mot) & nzchar(df$dic_norm), , drop = FALSE]
  df <- df[!duplicated(df$dic_mot), , drop = FALSE]
  df
}

lire_add_expression_depuis_fichier_batch <- function(path_in) {
  if (is.null(path_in) || !nzchar(path_in) || !file.exists(path_in)) return(NULL)

  lecteurs <- list(
    function() utils::read.csv2(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character()),
    function() utils::read.csv(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character(), sep = ","),
    function() utils::read.csv(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character(), sep = ";"),
    function() utils::read.delim(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character(), sep = "\t")
  )

  for (lecteur in lecteurs) {
    df <- tryCatch(lecteur(), error = function(e) NULL)
    df_norm <- normaliser_add_expression_df_batch(df)
    if (!is.null(df_norm)) return(df_norm)
  }

  NULL
}

script_path <- local({
  args_all <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("^--file=", args_all, value = TRUE)
  if (!length(file_arg)) return("")
  sub("^--file=", "", file_arg[[1]])
})

repo_root <- normalizePath(file.path(dirname(script_path %||% ""), "..", ".."), winslash = "/", mustWork = FALSE)
if (!dir.exists(file.path(repo_root, "iramuteqlite"))) {
  repo_root <- normalizePath(getwd(), winslash = "/", mustWork = TRUE)
}

required_packages <- c(
  "jsonlite", "quanteda", "Matrix", "dplyr", "wordcloud", "RColorBrewer",
  "FactoMineR", "igraph", "proxy", "htmltools", "topicmodels", "factoextra"
)
missing_packages <- required_packages[!vapply(required_packages, requireNamespace, quietly = TRUE, logical(1))]
if (length(missing_packages)) {
  stop(paste("Packages R manquants:", paste(missing_packages, collapse = ", ")))
}

source(file.path(repo_root, "iramuteqlite", "nettoyage_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "chd_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "chd_engine_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "iramuteq_bars.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "dendrogramme_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "afc_helpers_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "afc_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "wordcloud_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "concordancier-iramuteq.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "simi.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "simi_graph.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "simi_igraph.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "stats_chd.R"), local = TRUE)
source(file.path(repo_root, "iramuteqlite", "ui_chd_stats_mode_iramuteq.R"), local = TRUE)
source(file.path(repo_root, "sante", "suivi_longitudinal_chd.R"), local = TRUE)
args <- parse_args(commandArgs(trailingOnly = TRUE))
input_path <- normalizePath(scalar_chr(args$input), winslash = "/", mustWork = TRUE)
config_path <- normalizePath(scalar_chr(args$config), winslash = "/", mustWork = TRUE)
output_dir <- normalizePath(scalar_chr(args[["output-dir"]]), winslash = "/", mustWork = FALSE)
status_file <- normalizePath(scalar_chr(args[["status-file"]]), winslash = "/", mustWork = FALSE)
results_file <- normalizePath(scalar_chr(args[["results-file"]]), winslash = "/", mustWork = FALSE)

dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(dirname(status_file), recursive = TRUE, showWarnings = FALSE)
dir.create(dirname(results_file), recursive = TRUE, showWarnings = FALSE)

job_logs <- character(0)

relative_to_output <- function(path) {
  if (is.null(path) || !nzchar(path) || !file.exists(path)) return(NULL)
  rel <- sub(paste0("^", normalizePath(output_dir, winslash = "/", mustWork = FALSE), "/?"), "", normalizePath(path, winslash = "/", mustWork = FALSE))
  rel
}

write_status <- function(state = "running", progress = 0, message = "", extra = list()) {
  payload <- c(
    list(
      state = state,
      progress = progress,
      message = message,
      updated_at = format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z"),
      logs = job_logs
    ),
    extra
  )
  jsonlite::write_json(payload, status_file, auto_unbox = TRUE, pretty = TRUE, null = "null")
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

formatter_p_scientifique_batch <- function(x) {
  vals <- suppressWarnings(as.numeric(x))
  ifelse(
    is.na(vals),
    NA_character_,
    ifelse(vals == 0, "0", format(vals, scientific = TRUE, digits = 6))
  )
}

formatter_p_seuil_01_batch <- function(x) {
  vals <- suppressWarnings(as.numeric(x))
  ifelse(
    is.na(vals),
    NA_character_,
    ifelse(vals <= 0.01, "p <= 0.01", "")
  )
}

ecrire_csv_6_decimales <- function(df, path, row.names = FALSE) {
  utils::write.csv(formater_df_csv_6_decimales(df), path, row.names = row.names)
}

coords_have_two_axes <- function(coords) {
  !is.null(coords) && is.matrix(coords) && ncol(coords) >= 2
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

import_corpus_iramuteq <- function(chemin_fichier) {
  lignes <- readLines(chemin_fichier, encoding = "UTF-8", warn = FALSE)
  if (length(lignes) == 0) stop("Corpus vide : aucun contenu lisible.")

  headers <- grepl("^\\*\\*\\*\\*", lignes)
  textes <- character(0)
  ids <- character(0)
  etoiles_par_doc <- vector("list", 0)

  if (any(headers)) {
    idx <- which(headers)
    bornes <- c(idx, length(lignes) + 1L)
    for (i in seq_along(idx)) {
      entete <- as.character(lignes[idx[[i]]])
      tokens_entete <- unlist(regmatches(entete, gregexpr("\\*[[:alnum:]_\\-]+", entete, perl = TRUE)), use.names = FALSE)
      tokens_entete <- unique(tokens_entete[grepl("^\\*[[:alnum:]_\\-]+$", tokens_entete)])
      debut <- idx[[i]] + 1L
      fin <- bornes[[i + 1L]] - 1L
      contenu <- if (debut <= fin) lignes[debut:fin] else character(0)
      contenu <- trimws(contenu)
      contenu <- contenu[nzchar(contenu)]
      if (!length(contenu)) next
      textes <- c(textes, paste(contenu, collapse = " "))
      ids <- c(ids, paste0("doc_", i))
      etoiles_par_doc[[length(etoiles_par_doc) + 1L]] <- tokens_entete
    }
  } else {
    lignes2 <- trimws(lignes)
    lignes2 <- lignes2[nzchar(lignes2)]
    textes <- lignes2
    ids <- paste0("doc_", seq_along(textes))
    etoiles_par_doc <- rep(list(character(0)), length(textes))
  }

  if (!length(textes)) stop("Corpus vide : aucune unite de texte detectee.")

  base_df <- data.frame(doc_id = ids, text = textes, stringsAsFactors = FALSE)
  noms_etoiles <- unique(unlist(lapply(etoiles_par_doc, function(tok) {
    tok <- tok[!is.na(tok) & nzchar(tok)]
    if (!length(tok)) return(character(0))
    sous <- sub("^\\*", "", tok)
    sous <- sub("_.*$", "", sous)
    sous <- sous[nzchar(sous)]
    paste0("*", sous)
  }), use.names = FALSE))

  if (length(noms_etoiles)) {
    for (cn in noms_etoiles) base_df[[cn]] <- NA_character_
    for (i in seq_along(etoiles_par_doc)) {
      toks <- etoiles_par_doc[[i]]
      if (!length(toks)) next
      for (tk in toks) {
        corps <- sub("^\\*", "", tk)
        if (!nzchar(corps)) next
        var <- sub("_.*$", "", corps)
        val <- sub("^[^_]*_?", "", corps)
        if (!nzchar(var)) next
        if (!nzchar(val) || identical(val, var)) val <- "1"
        cn <- paste0("*", var)
        if (cn %in% names(base_df)) base_df[i, cn] <- val
      }
    }
  }

  quanteda::corpus(base_df, text_field = "text")
}

split_segments <- function(corpus,
                           segment_size = 40,
                           remove_punct = FALSE,
                           remove_numbers = FALSE,
                           force_split_on_strong_punct = FALSE) {
  segment_size <- suppressWarnings(as.integer(segment_size))
  if (!is.finite(segment_size) || is.na(segment_size) || segment_size < 1) segment_size <- 40L

  docs <- as.character(corpus)
  dn <- as.character(quanteda::docnames(corpus))
  if (!length(dn) || any(!nzchar(dn))) dn <- paste0("doc_", seq_along(docs))

  out_text <- character(0)
  out_id <- character(0)
  out_src <- character(0)
  out_docvars <- list()
  dv_in <- tryCatch(quanteda::docvars(corpus), error = function(e) NULL)

  for (i in seq_along(docs)) {
    if (isTRUE(force_split_on_strong_punct)) {
      doc_with_newlines <- gsub("\r\n|\r|\n", " __NL_SEG_BREAK__ ", docs[[i]], perl = TRUE)
      tok_doc <- quanteda::tokens(
        doc_with_newlines,
        remove_punct = FALSE,
        remove_numbers = isTRUE(remove_numbers),
        remove_symbols = TRUE,
        remove_separators = TRUE,
        split_hyphens = FALSE
      )
      tok <- as.character(tok_doc[[1]])
      tok <- tok[nzchar(tok)]
      if (!length(tok)) next

      seg_tokens <- character(0)
      seg_idx <- 0L

      append_segment <- function(tokens_to_write) {
        seg <- paste(tokens_to_write, collapse = " ")
        if (!nzchar(seg)) return(invisible(NULL))
        seg_idx <<- seg_idx + 1L
        out_text <<- c(out_text, seg)
        out_id <<- c(out_id, paste0(dn[[i]], "_seg", seg_idx))
        out_src <<- c(out_src, dn[[i]])
        if (!is.null(dv_in) && nrow(dv_in) >= i) {
          out_docvars[[length(out_docvars) + 1L]] <<- dv_in[i, , drop = FALSE]
        } else {
          out_docvars[[length(out_docvars) + 1L]] <<- NULL
        }
      }

      rank_boundary <- function(token) {
        if (!nzchar(token)) return(4L)
        if (grepl("^[.!?…]+$", token)) return(1L)
        if (grepl("^[;:]+$", token)) return(2L)
        if (grepl("^[,]+$", token)) return(3L)
        4L
      }

      compute_state <- function(tokens_vec) {
        candidates <- list()
        non_punct_count <- 0L
        for (idx_tok in seq_along(tokens_vec)) {
          tk2 <- tokens_vec[[idx_tok]]
          if (identical(tk2, "__NL_SEG_BREAK__")) next
          is_punct2 <- grepl("^[[:punct:]]+$", tk2)
          if (!isTRUE(is_punct2)) non_punct_count <- non_punct_count + 1L
          boundary_rank <- if (isTRUE(is_punct2)) rank_boundary(tk2) else 4L
          candidates[[length(candidates) + 1L]] <- list(pos = idx_tok, count = non_punct_count, rank = boundary_rank)
        }
        list(candidates = candidates, non_punct_count = non_punct_count)
      }

      choose_boundary <- function(candidates, target_size) {
        if (!length(candidates)) return(NULL)
        min_count <- max(1L, floor(target_size * 0.5))
        cand_ok <- Filter(function(x) x$count >= min_count, candidates)
        if (!length(cand_ok)) cand_ok <- candidates
        ord <- order(
          vapply(cand_ok, function(x) x$rank, integer(1)),
          vapply(cand_ok, function(x) abs(x$count - target_size), integer(1)),
          -vapply(cand_ok, function(x) x$pos, integer(1))
        )
        cand_ok[[ord[[1]]]]
      }

      flush_by_policy <- function() {
        state <- compute_state(seg_tokens)
        while (state$non_punct_count >= segment_size && length(state$candidates) > 0) {
          best <- choose_boundary(state$candidates, segment_size)
          if (is.null(best)) break
          write_tokens <- seg_tokens[seq_len(best$pos)]
          write_tokens <- write_tokens[write_tokens != "__NL_SEG_BREAK__"]
          if (isTRUE(remove_punct)) {
            write_tokens <- write_tokens[!grepl("^[[:punct:]]+$", write_tokens)]
          }
          append_segment(write_tokens)
          if (best$pos < length(seg_tokens)) {
            seg_tokens <<- seg_tokens[(best$pos + 1L):length(seg_tokens)]
          } else {
            seg_tokens <<- character(0)
          }
          state <- compute_state(seg_tokens)
        }
      }

      for (k in seq_along(tok)) {
        tk <- tok[[k]]
        if (identical(tk, "__NL_SEG_BREAK__")) {
          flush_by_policy()
          if (length(seg_tokens) > 0) {
            remain_tokens <- seg_tokens[seg_tokens != "__NL_SEG_BREAK__"]
            if (isTRUE(remove_punct)) {
              remain_tokens <- remain_tokens[!grepl("^[[:punct:]]+$", remain_tokens)]
            }
            append_segment(remain_tokens)
            seg_tokens <- character(0)
          }
          next
        }
        seg_tokens <- c(seg_tokens, tk)
        flush_by_policy()
      }

      if (length(seg_tokens) > 0) {
        remain_tokens <- seg_tokens[seg_tokens != "__NL_SEG_BREAK__"]
        if (isTRUE(remove_punct)) {
          remain_tokens <- remain_tokens[!grepl("^[[:punct:]]+$", remain_tokens)]
        }
        append_segment(remain_tokens)
      }
    } else {
      tok_doc <- quanteda::tokens(
        docs[[i]],
        remove_punct = isTRUE(remove_punct),
        remove_numbers = isTRUE(remove_numbers),
        remove_symbols = TRUE,
        remove_separators = TRUE,
        split_hyphens = FALSE
      )
      tok <- as.character(tok_doc[[1]])
      tok <- tok[nzchar(tok)]
      if (!length(tok)) next
      nseg <- ceiling(length(tok) / segment_size)
      for (j in seq_len(nseg)) {
        deb <- ((j - 1L) * segment_size) + 1L
        fin <- min(j * segment_size, length(tok))
        seg <- paste(tok[deb:fin], collapse = " ")
        out_text <- c(out_text, seg)
        out_id <- c(out_id, paste0(dn[[i]], "_seg", j))
        out_src <- c(out_src, dn[[i]])
        if (!is.null(dv_in) && nrow(dv_in) >= i) {
          out_docvars[[length(out_docvars) + 1L]] <- dv_in[i, , drop = FALSE]
        } else {
          out_docvars[[length(out_docvars) + 1L]] <- NULL
        }
      }
    }
  }

  if (!length(out_text)) stop("Segmentation impossible : aucun segment généré.")

  corp <- quanteda::corpus(
    data.frame(doc_id = out_id, text = out_text, segment_source = out_src, stringsAsFactors = FALSE),
    text_field = "text"
  )
  quanteda::docvars(corp, "segment_source") <- out_src

  if (length(out_docvars) > 0 && any(vapply(out_docvars, Negate(is.null), logical(1)))) {
    idx_valid <- which(vapply(out_docvars, Negate(is.null), logical(1)))
    dv_seg <- do.call(rbind, out_docvars[idx_valid])
    if (!is.null(dv_seg) && nrow(dv_seg) == length(idx_valid)) {
      cn_copy <- setdiff(colnames(dv_seg), "segment_source")
      for (cn in cn_copy) {
        vals <- rep(NA, quanteda::ndoc(corp))
        vals[idx_valid] <- dv_seg[[cn]]
        quanteda::docvars(corp, cn) <- vals
      }
    }
  }
  corp
}

split_segments_double_rst <- function(corpus,
                                      rst1 = 12,
                                      rst2 = 14,
                                      remove_punct = FALSE,
                                      remove_numbers = FALSE,
                                      force_split_on_strong_punct = FALSE) {
  corpus_rst1 <- split_segments(
    corpus,
    segment_size = rst1,
    remove_punct = isTRUE(remove_punct),
    remove_numbers = isTRUE(remove_numbers),
    force_split_on_strong_punct = isTRUE(force_split_on_strong_punct)
  )
  corpus_rst2 <- split_segments(
    corpus,
    segment_size = rst2,
    remove_punct = isTRUE(remove_punct),
    remove_numbers = isTRUE(remove_numbers),
    force_split_on_strong_punct = isTRUE(force_split_on_strong_punct)
  )
  txt1 <- as.character(corpus_rst1)
  txt2 <- as.character(corpus_rst2)
  id1 <- paste0(as.character(quanteda::docnames(corpus_rst1)), "_rst1")
  id2 <- paste0(as.character(quanteda::docnames(corpus_rst2)), "_rst2")
  corp_out <- quanteda::corpus(
    data.frame(doc_id = c(id1, id2), text = c(txt1, txt2), stringsAsFactors = FALSE),
    text_field = "text"
  )
  dv1 <- tryCatch(quanteda::docvars(corpus_rst1), error = function(e) NULL)
  dv2 <- tryCatch(quanteda::docvars(corpus_rst2), error = function(e) NULL)
  if (!is.null(dv1) && !is.null(dv2)) {
    cols <- union(colnames(dv1), colnames(dv2))
    for (cn in cols) {
      v1 <- if (cn %in% colnames(dv1)) as.character(dv1[[cn]]) else rep(NA_character_, nrow(dv1))
      v2 <- if (cn %in% colnames(dv2)) as.character(dv2[[cn]]) else rep(NA_character_, nrow(dv2))
      quanteda::docvars(corp_out, cn) <- c(v1, v2)
    }
  }
  quanteda::docvars(corp_out, "rst_source") <- c(rep("rst1", length(txt1)), rep("rst2", length(txt2)))
  corp_out
}

charger_lexique_fr <- function(repo_root) {
  path <- file.path(repo_root, "dictionnaires", "lexique_fr.csv")
  if (!file.exists(path)) {
    stop(paste0("Fichier lexique introuvable: ", path))
  }

  lexique <- utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8")
  colonnes_requises <- c("c_mot", "c_lemme", "c_morpho")
  if (!all(colonnes_requises %in% names(lexique))) {
    stop("Le fichier lexique_fr.csv doit contenir les colonnes c_mot, c_lemme et c_morpho.")
  }

  lexique$c_mot <- tolower(trimws(as.character(lexique$c_mot)))
  lexique$c_lemme <- tolower(trimws(as.character(lexique$c_lemme)))
  lexique$c_morpho <- trimws(as.character(lexique$c_morpho))
  lexique <- lexique[nzchar(lexique$c_mot) & nzchar(lexique$c_lemme), c("c_mot", "c_lemme", "c_morpho"), drop = FALSE]
  lexique[!duplicated(lexique$c_mot), , drop = FALSE]
}

charger_expression_fr <- function(repo_root) {
  chemins_candidats <- c(
    file.path(repo_root, "dictionnaires", "expression_fr.csv"),
    file.path(repo_root, "dictionnaires", "expressions.csv")
  )
  path <- chemins_candidats[file.exists(chemins_candidats)][1]
  if (is.na(path) || !nzchar(path)) {
    stop(
      paste0(
        "Fichier dictionnaire d'expressions introuvable. Chemins testés: ",
        paste(chemins_candidats, collapse = " | ")
      )
    )
  }

  expressions <- utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8")
  colonnes_requises <- c("dic_mot", "dic_norm")
  if (!all(colonnes_requises %in% names(expressions))) {
    stop("Le fichier expression_fr.csv (ou expressions.csv) doit contenir les colonnes dic_mot et dic_norm.")
  }

  expressions$dic_mot <- tolower(trimws(as.character(expressions$dic_mot)))
  expressions$dic_mot <- gsub("[’`´ʼʹ]", "'", expressions$dic_mot, perl = TRUE)
  expressions$dic_norm <- tolower(trimws(as.character(expressions$dic_norm)))
  expressions <- expressions[nzchar(expressions$dic_mot) & nzchar(expressions$dic_norm), c("dic_mot", "dic_norm"), drop = FALSE]
  expressions <- expressions[!duplicated(expressions$dic_mot), , drop = FALSE]
  attr(expressions, "source_file") <- path
  expressions
}

appliquer_dictionnaire_expressions <- function(textes, expressions_df) {
  if (is.null(textes) || length(textes) == 0 ||
      is.null(expressions_df) || !is.data.frame(expressions_df) || nrow(expressions_df) == 0) {
    return(list(textes = as.character(textes), n_patterns = 0L, n_occurrences = 0L))
  }
  textes_out <- as.character(textes)
  textes_out <- gsub("[’`´ʼʹ]", "'", textes_out, perl = TRUE)
  dic <- expressions_df
  ord <- order(nchar(dic$dic_mot), decreasing = TRUE)
  dic <- dic[ord, , drop = FALSE]
  n_occurrences <- 0L

  construire_motif_regex_expression <- function(motif) {
    accent_map <- list(
      a = "aàáâäãå",
      e = "eèéêë",
      i = "iìíîï",
      o = "oòóôöõø",
      u = "uùúûü",
      y = "yÿ",
      c = "cç",
      n = "nñ"
    )
    chars <- strsplit(motif, "", fixed = TRUE)[[1]]
    out <- character(length(chars))
    for (k in seq_along(chars)) {
      ch <- chars[[k]]
      ch_l <- tolower(ch)
      if (ch == "'") {
        out[[k]] <- "['’`´ʼʹ]"
      } else if (ch_l %in% names(accent_map)) {
        out[[k]] <- paste0("[", accent_map[[ch_l]], "]")
      } else if (ch_l == "œ") {
        out[[k]] <- "(?:œ|oe)"
      } else {
        regex_chars <- c("\\", "^", "$", ".", "|", "?", "*", "+", "(", ")", "[", "]", "{", "}")
        out[[k]] <- if (ch %in% regex_chars) paste0("\\", ch) else ch
      }
    }
    paste0(out, collapse = "")
  }

  for (i in seq_len(nrow(dic))) {
    motif <- dic$dic_mot[[i]]
    remplacement <- dic$dic_norm[[i]]
    motif_echappe <- construire_motif_regex_expression(motif)
    regex <- paste0("(?i)(?<![[:alnum:]_])", motif_echappe, "(?![[:alnum:]_])")
    matches <- gregexpr(regex, textes_out, perl = TRUE)
    captures <- regmatches(textes_out, matches)
    captures_count <- sum(lengths(captures), na.rm = TRUE)
    if (captures_count > 0L) {
      remplacements <- lapply(captures, function(vals) {
        if (!length(vals)) return(character(0))
        rep(remplacement, length(vals))
      })
      regmatches(textes_out, matches) <- remplacements
      n_occurrences <- n_occurrences + as.integer(captures_count)
    }
    if (i < nrow(dic) && (i %% 250L) == 0L) {
      progress_pct <- 24L + as.integer(floor((i / nrow(dic)) * 3))
      log_info(
        paste0(
          "Application du dictionnaire d'expressions : ",
          i,
          "/",
          nrow(dic),
          " entrées traitées (",
          n_occurrences,
          " remplacement(s) détecté(s))."
        ),
        progress = progress_pct
      )
    }
  }
  list(textes = textes_out, n_patterns = nrow(dic), n_occurrences = as.integer(n_occurrences))
}

preparer_pipeline_chd <- function(segmented_corpus, config) {
  ids_docs <- as.character(quanteda::docnames(segmented_corpus))
  textes_orig <- as.character(segmented_corpus)
  source_dictionnaire <- scalar_chr(config$source_dictionnaire, "lexique_fr")
  if (!nzchar(source_dictionnaire)) source_dictionnaire <- "lexique_fr"
  expressions_actives_df <- NULL

  if (scalar_bool(config$expression_utiliser_dictionnaire, FALSE)) {
    expression_fr_df <- charger_expression_fr(repo_root)
    expression_fr_df$source_expr <- "base"
    expressions_actives_df <- expression_fr_df
    log_info(
      paste0(
        "Expression (fr) chargé : ",
        nrow(expression_fr_df),
        " entrées (source=",
        attr(expression_fr_df, "source_file") %||% "inconnue",
        ")."
      ),
      progress = 24
    )

    add_expression_actif <- scalar_bool(config$utiliser_add_expression, FALSE)
    expr_session_df <- NULL
    if (isTRUE(add_expression_actif) && !is.null(config$expression_annotations)) {
      expr_session_df <- normaliser_add_expression_df_batch(config$expression_annotations)
    }

    if (isTRUE(add_expression_actif) && (is.null(expr_session_df) || !nrow(expr_session_df))) {
      add_expression_path <- Sys.getenv("IRAMUTEQ_ADD_EXPRESSION_PATH", unset = "")
      if (!nzchar(add_expression_path)) {
        add_expression_path <- file.path(repo_root, "dictionnaires", "add_expression_fr.csv")
      }
      expr_session_df <- lire_add_expression_depuis_fichier_batch(add_expression_path)
      if (!is.null(expr_session_df) && nrow(expr_session_df) > 0) {
        log_info(
          paste0(
            "add_expression_fr.csv rechargé depuis le disque : ",
            nrow(expr_session_df),
            " entrées (",
            add_expression_path,
            ")."
          ),
          progress = 25
        )
      }
    }

    if (isTRUE(add_expression_actif) && !is.null(expr_session_df) && nrow(expr_session_df) > 0) {
      log_info(paste0("add_expression_fr.csv chargé : ", nrow(expr_session_df), " entrées utilisateur."), progress = 25)
      expr_session_df$source_expr <- "user"
      deja_base <- expr_session_df$dic_mot %in% expression_fr_df$dic_mot
      expr_session_ajouts <- expr_session_df[!deja_base, c("dic_mot", "dic_norm", "source_expr"), drop = FALSE]
      expressions_actives_df <- rbind(
        expression_fr_df[, c("dic_mot", "dic_norm", "source_expr"), drop = FALSE],
        expr_session_ajouts
      )
      expressions_actives_df <- expressions_actives_df[!duplicated(expressions_actives_df$dic_mot), , drop = FALSE]
      log_info(
        paste0(
          "Dictionnaire utilisateur ajouté au dictionnaire de base : +",
          nrow(expr_session_ajouts),
          " nouvelle(s) entrée(s) (",
          sum(deja_base),
          " déjà présentes ignorées)."
        ),
        progress = 26
      )
    } else if (isTRUE(add_expression_actif)) {
      log_info("add_expression_fr.csv active mais vide/invalide ; utilisation du dictionnaire de base uniquement.", progress = 25)
    } else {
      log_info("add_expression_fr.csv non activé ; utilisation du dictionnaire de base uniquement.", progress = 25)
    }

    log_info(
      paste0(
        "Dictionnaire d'expressions chargé : ",
        nrow(expressions_actives_df),
        " entrées actives."
      ),
      progress = 27
    )

    remplacements_expr <- appliquer_dictionnaire_expressions(textes_orig, expressions_actives_df)
    textes_orig <- remplacements_expr$textes
    log_info(
      paste0(
        "Dictionnaire d'expressions appliqué avant analyse : ",
        remplacements_expr$n_occurrences,
        " occurrence(s) remplacée(s) via ",
        remplacements_expr$n_patterns,
        " entrée(s) du dictionnaire (base + add_expression_fr.csv si activé)."
      ),
      progress = 28
    )
  } else {
    log_info("Dictionnaire d'expressions désactivé (expression_utiliser_dictionnaire=0).", progress = 24)
  }

  log_info("Préparation du texte (nettoyage / minuscules).", progress = 30)
  textes_nettoyes <- appliquer_nettoyage_iramuteq(
    textes = textes_orig,
    activer_nettoyage = scalar_bool(config$nettoyage_caracteres, TRUE),
    forcer_minuscules = TRUE,
    supprimer_chiffres = scalar_bool(config$supprimer_chiffres, FALSE),
    supprimer_apostrophes = scalar_bool(config$supprimer_apostrophes, TRUE),
    remplacer_tirets_espaces = scalar_bool(config$remplacer_tirets_espaces, FALSE)
  )
  textes_chd <- textes_nettoyes
  names(textes_chd) <- ids_docs

  textes_tok <- textes_chd
  if (scalar_bool(config$retirer_stopwords, FALSE)) {
    textes_tok <- gsub(
      pattern = "(?i)\\b(?:[cdjlmnst]|qu)['’`´ʼʹ](?=[[:alpha:]])",
      replacement = "",
      x = textes_tok,
      perl = TRUE
    )
  }

  log_info("IRaMuTeQ-lite : préparation du texte exécutée via iramuteqlite/nettoyage_iramuteq.R", progress = 32)
  log_info(
    paste0(
      "Diagnostic du pipeline : dictionnaire=",
      source_dictionnaire,
      " | langue UI=fr",
      " | filtrage_morpho=",
      ifelse(scalar_bool(config$filtrage_morpho, FALSE), "1", "0"),
      " | inclure_autre_forme=",
      ifelse(
        scalar_bool(config$morpho_conserver_hors_lexique, TRUE) ||
          ("AUTRE_FORME" %in% toupper(trimws(as.character(unlist(config$pos_lexique_a_conserver, use.names = FALSE))))),
        "1",
        "0"
      ),
      " | retirer_stopwords=",
      ifelse(scalar_bool(config$retirer_stopwords, FALSE), "1", "0"),
      " | supprimer_ponctuation=",
      ifelse(scalar_bool(config$supprimer_ponctuation, FALSE), "1", "0"),
      " | segmenter_sur_ponctuation_forte=",
      ifelse(scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE), "1", "0"),
      " | supprimer_chiffres=",
      ifelse(scalar_bool(config$supprimer_chiffres, FALSE), "1", "0"),
      " | supprimer_apostrophes=",
      ifelse(scalar_bool(config$supprimer_apostrophes, TRUE), "1", "0"),
      " | remplacer_tirets_espaces=",
      ifelse(scalar_bool(config$remplacer_tirets_espaces, FALSE), "1", "0"),
      " | nettoyage_caracteres=",
      ifelse(scalar_bool(config$nettoyage_caracteres, TRUE), "1", "0")
    ),
    progress = 33
  )

  tok <- quanteda::tokens(
    textes_tok,
    remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
    remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE)
  )
  quanteda::docnames(tok) <- ids_docs
  tok <- quanteda::tokens_tolower(tok)

  lexique_fr_df <- NULL
  if (scalar_bool(config$lexique_utiliser_lemmes, TRUE) || scalar_bool(config$filtrage_morpho, FALSE)) {
    lexique_fr_df <- charger_lexique_fr(repo_root)
  log_info(paste0("Lexique (fr) chargé : ", nrow(lexique_fr_df), " entrées."), progress = 34)
  }

  if (scalar_bool(config$lexique_utiliser_lemmes, TRUE) && !is.null(lexique_fr_df)) {
    vocabulaire <- quanteda::featnames(quanteda::dfm(tok))
    idx <- match(vocabulaire, lexique_fr_df$c_mot)
    a_remplacer <- !is.na(idx)
    if (any(a_remplacer)) {
      motifs <- vocabulaire[a_remplacer]
      remplacements <- lexique_fr_df$c_lemme[idx[a_remplacer]]
      tok <- quanteda::tokens_replace(
        tok,
        pattern = motifs,
        replacement = remplacements,
        valuetype = "fixed",
        case_insensitive = FALSE
      )
      log_info(paste0("Lemmatisation lexique_fr appliquée sur ", length(motifs), " formes du vocabulaire."), progress = 34)
    }
  }

  if (scalar_bool(config$retirer_stopwords, FALSE)) {
    stop_fr <- quanteda::stopwords("fr")
    n_feat_avant_stop <- quanteda::nfeat(quanteda::dfm(tok))
    tok <- quanteda::tokens_remove(tok, pattern = stop_fr, valuetype = "fixed", case_insensitive = TRUE)
    n_feat_apres_stop <- quanteda::nfeat(quanteda::dfm(tok))
    log_info(
      paste0(
        "Filtrage des stopwords quanteda(fr) appliqué : ",
        n_feat_avant_stop,
        " -> ",
        n_feat_apres_stop,
        " termes uniques."
      ),
      progress = 36
    )
  }

  dfm_obj <- quanteda::dfm(tok)
  quanteda::docnames(dfm_obj) <- ids_docs

  source_dict_chd <- "lexique_fr"
  if (scalar_bool(config$filtrage_morpho, FALSE) && identical(source_dict_chd, "lexique_fr")) {
    morpho_selection <- unique(toupper(trimws(as.character(unlist(config$pos_lexique_a_conserver, use.names = FALSE)))))
    inclure_autre_forme <- scalar_bool(config$morpho_conserver_hors_lexique, TRUE) || ("AUTRE_FORME" %in% morpho_selection)
    if (isTRUE(inclure_autre_forme) && !("AUTRE_FORME" %in% morpho_selection)) {
      morpho_selection <- c(morpho_selection, "AUTRE_FORME")
    }
    morpho_selection_lexique <- setdiff(morpho_selection, "AUTRE_FORME")

    if (length(morpho_selection_lexique) > 0 || isTRUE(inclure_autre_forme)) {
      lex <- lexique_fr_df
      lex_morpho <- toupper(trimws(as.character(lex$c_morpho)))
      exclure_etre_verbe <- scalar_bool(config$morpho_exclure_etre_verbe, FALSE)
      categorie_verbe_selectionnee <- any(morpho_selection_lexique %in% c("VER", "VERB", "AUX", "VER_SUP"))

      idx <- nzchar(lex_morpho) & lex_morpho %in% morpho_selection_lexique
      termes_autorises <- unique(c(
        tolower(trimws(as.character(lex$c_mot[idx]))),
        tolower(trimws(as.character(lex$c_lemme[idx])))
      ))
      termes_autorises <- termes_autorises[nzchar(termes_autorises)]
      if (isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee)) {
        termes_autorises <- setdiff(termes_autorises, c("être", "etre"))
      }

      toutes_formes_lexique <- unique(c(
        tolower(trimws(as.character(lex$c_mot))),
        tolower(trimws(as.character(lex$c_lemme)))
      ))
      toutes_formes_lexique <- toutes_formes_lexique[nzchar(toutes_formes_lexique)]

      featnames_dfm <- quanteda::featnames(dfm_obj)
      featnames_norm <- tolower(trimws(as.character(featnames_dfm)))
      featnames_core <- gsub("^[[:punct:]]+|[[:punct:]]+$", "", featnames_norm, perl = TRUE)
      is_punct_feature <- !nzchar(featnames_core)

      in_selection <- (featnames_norm %in% termes_autorises) | (featnames_core %in% termes_autorises)
      in_lexique <- (featnames_norm %in% toutes_formes_lexique) | (featnames_core %in% toutes_formes_lexique)

      keep_mask <- in_selection
      if (isTRUE(inclure_autre_forme)) {
        keep_mask <- keep_mask | (!in_lexique & !is_punct_feature)
      }

      pattern_keep <- featnames_dfm[keep_mask]
      dfm_obj <- quanteda::dfm_select(
        dfm_obj,
        pattern = pattern_keep,
        selection = "keep",
        valuetype = "fixed",
        case_insensitive = FALSE
      )
      log_info("Filtrage morphosyntaxique appliqué.", progress = 38)
    } else {
      log_info("Filtrage morphosyntaxique activé sans catégorie c_morpho sélectionnée : étape ignorée.", progress = 38)
    }
  }

  dfm_stats <- dfm_obj
  freq_termes <- sort(as.numeric(Matrix::colSums(dfm_stats)), decreasing = TRUE)
  freq_termes <- freq_termes[is.finite(freq_termes) & !is.na(freq_termes) & freq_termes > 0]
  zipf_df <- if (length(freq_termes) >= 2) {
    rang <- seq_along(freq_termes)
    fit <- tryCatch(stats::lm(log(freq_termes) ~ log(rang)), error = function(e) NULL)
    pred <- if (is.null(fit)) rep(NA_real_, length(freq_termes)) else as.numeric(exp(stats::predict(fit)))
    data.frame(
      rang = rang,
      frequence = freq_termes,
      pred = pred,
      log_rang = log(rang),
      log_frequence = log(freq_termes),
      log_pred = ifelse(is.na(pred), NA_real_, log(pred)),
      stringsAsFactors = FALSE
    )
  } else {
    NULL
  }

  dfm_obj <- quanteda::dfm_trim(dfm_obj, min_docfreq = scalar_int(config$min_docfreq, 3L, 1L))
  log_info(
    paste0(
      "min_docfreq appliqué (IRaMuTeQ-lite) = ",
      scalar_int(config$min_docfreq, 3L, 1L),
      " (manuel)."
    ),
    progress = 40
  )
  included_segments <- as.character(quanteda::docnames(dfm_obj))
  included_segments <- included_segments[!is.na(included_segments) & nzchar(included_segments)]
  included_segments <- unique(included_segments)
  filtered_corpus <- segmented_corpus[included_segments]
  tok <- tok[included_segments]

  segment_source <- as.character(quanteda::docnames(dfm_obj))
  if ("segment_source" %in% names(quanteda::docvars(filtered_corpus))) {
    ss <- as.character(quanteda::docvars(filtered_corpus)$segment_source)
    idx_ss <- match(as.character(quanteda::docnames(dfm_obj)), as.character(quanteda::docnames(filtered_corpus)))
    ss_aligne <- ss[idx_ss]
    ok_ss <- !is.na(ss_aligne) & nzchar(trimws(ss_aligne))
    segment_source[ok_ss] <- ss_aligne[ok_ss]
  }
  quanteda::docvars(dfm_obj, "segment_source") <- segment_source

  cleaned <- supprimer_docs_vides_dfm(dfm_obj, filtered_corpus = filtered_corpus, tok = tok)
  if (cleaned$nb_vides > 0) {
    log_info(paste0("Segments vides supprimés du DFM : ", cleaned$nb_vides, "."))
  }
  textes_indexation <- vapply(as.list(cleaned$tok), function(x) paste(x, collapse = " "), FUN.VALUE = character(1))
  names(textes_indexation) <- as.character(quanteda::docnames(cleaned$dfm_obj))
  log_info(
    paste0(
      "Après suppression des segments vides : ",
      quanteda::ndoc(cleaned$dfm_obj),
      " docs ; ",
      quanteda::nfeat(cleaned$dfm_obj),
      " termes."
    ),
    progress = 41
  )

  list(
    filtered_corpus = cleaned$filtered_corpus,
    tok = cleaned$tok,
    dfm_obj = cleaned$dfm_obj,
    textes_indexation = textes_indexation,
    lexique_fr_df = lexique_fr_df,
    expressions_actives_df = expressions_actives_df,
    corpus_stats = list(
      n_tokens = sum(freq_termes),
      n_formes = length(freq_termes),
      n_hapax = if (length(freq_termes)) sum(freq_termes == 1) else 0L,
      zipf = if (is.null(zipf_df)) NULL else utils::head(zipf_df, 160L)
    )
  )
}

generer_wordclouds_lda_batch <- function(topic_term_matrix, lda_dir, max_words = 50L) {
  files <- character(0)
  if (is.null(topic_term_matrix) || !nrow(topic_term_matrix)) return(files)
  dir.create(file.path(lda_dir, "wordclouds"), recursive = TRUE, showWarnings = FALSE)
  for (i in seq_len(nrow(topic_term_matrix))) {
    weights <- as.numeric(topic_term_matrix[i, ])
    words <- colnames(topic_term_matrix)
    ord <- order(weights, decreasing = TRUE)
    ord <- ord[weights[ord] > 0]
    ord <- ord[seq_len(min(length(ord), max_words))]
    if (!length(ord)) next
    scale_use <- if (length(ord) <= 10L) c(4.8, 1.1) else if (length(ord) <= 15L) c(4.2, 0.9) else c(3.8, 0.8)
    out_file <- file.path(lda_dir, "wordclouds", paste0("wordcloud_lda_topic_", i, ".png"))
    grDevices::png(out_file, width = 900, height = 650, res = 160)
    suppressWarnings(wordcloud::wordcloud(
      words = words[ord],
      freq = weights[ord],
      scale = scale_use,
      min.freq = 0,
      random.order = FALSE,
      rot.per = 0,
      max.words = length(ord),
      colors = RColorBrewer::brewer.pal(8, "Dark2")
    ))
    grDevices::dev.off()
    files <- c(files, out_file)
  }
  files
}

trouver_python_lda_batch <- function() {
  candidats <- c(
    Sys.getenv("IRAMUTEQ_PYTHON", unset = ""),
    Sys.which("python3"),
    Sys.which("python")
  )
  candidats <- unique(candidats[nzchar(candidats)])
  if (!length(candidats)) stop("Aucun interpreteur Python trouve (python3/python).")
  candidats[[1]]
}

executer_commande_python_batch <- function(python_exec, args, etiquette, env = character(0)) {
  args_quoted <- vapply(as.character(args), shQuote, character(1))
  logs <- suppressWarnings(system2(python_exec, args = args_quoted, stdout = TRUE, stderr = TRUE, env = env))
  statut <- as.integer(attr(logs, "status") %||% 0L)
  if (!identical(statut, 0L)) {
    stop(
      paste0(
        etiquette,
        " a echoue (code ",
        statut,
        ").\nLogs Python:\n",
        paste(logs, collapse = "\n")
      )
    )
  }
  logs
}

construire_stopwords_fr_quanteda_batch <- function(activer) {
  if (!isTRUE(activer)) return(character(0))
  unique(quanteda::stopwords(language = "fr", source = "snowball"))
}

convertir_resultat_python_lda_batch <- function(res_lda_json, res_wc_json) {
  topics <- res_lda_json$topics
  unites <- res_lda_json$unites

  mat <- NULL
  termes_complets <- unlist(res_lda_json$terms %||% list(), use.names = FALSE)
  topic_term_matrix <- res_lda_json$topic_term_matrix %||% list()
  if (length(topic_term_matrix) > 0 && length(termes_complets) > 0) {
    mat_values <- suppressWarnings(as.numeric(unlist(topic_term_matrix, use.names = FALSE)))
    n_topics <- length(topic_term_matrix)
    n_terms <- length(termes_complets)
    if (length(mat_values) == (n_topics * n_terms)) {
      mat <- matrix(mat_values, nrow = n_topics, ncol = n_terms, byrow = TRUE)
      rownames(mat) <- paste0("Topic_", seq_len(n_topics))
      colnames(mat) <- as.character(termes_complets)
    }
  }

  top_terms <- data.frame(topic = character(0), term = character(0), prob = numeric(0), stringsAsFactors = FALSE)
  for (t in topics) {
    if (is.null(t$mots) || !length(t$mots)) next
    topic_name <- paste0("Topic_", t$topic)
    termes_topic <- vapply(t$mots, function(m) as.character(m$mot %||% ""), character(1))
    if (!is.null(mat) && topic_name %in% rownames(mat)) {
      prob <- vapply(termes_topic, function(term_name) {
        if (nzchar(term_name) && term_name %in% colnames(mat)) {
          as.numeric(mat[topic_name, term_name])
        } else {
          NA_real_
        }
      }, numeric(1))
      if (all(!is.finite(prob))) {
        poids <- vapply(t$mots, function(m) as.numeric(m$poids %||% 0), numeric(1))
        somme <- sum(poids)
        prob <- if (somme > 0) poids / somme else poids
      }
    } else {
      poids <- vapply(t$mots, function(m) as.numeric(m$poids %||% 0), numeric(1))
      somme <- sum(poids)
      prob <- if (somme > 0) poids / somme else poids
    }
    df_t <- data.frame(
      topic = topic_name,
      term = termes_topic,
      prob = prob,
      stringsAsFactors = FALSE
    )
    top_terms <- rbind(top_terms, df_t)
  }

  if (is.null(mat)) {
    termes_uniques <- unique(top_terms$term)
    topics_uniques <- unique(top_terms$topic)
    mat <- matrix(0, nrow = length(topics_uniques), ncol = length(termes_uniques))
    rownames(mat) <- topics_uniques
    colnames(mat) <- termes_uniques
    if (nrow(top_terms) > 0) {
      for (i in seq_len(nrow(top_terms))) {
        mat[top_terms$topic[i], top_terms$term[i]] <- as.numeric(top_terms$prob[i])
      }
    }
  }

  topic_term_matrix_df <- data.frame(term = colnames(mat), t(mat), check.names = FALSE, stringsAsFactors = FALSE)

  doc_topics <- data.frame(doc_id = character(0), stringsAsFactors = FALSE)
  doc_topics_segments <- data.frame(
    doc_id = character(0),
    type_unite = character(0),
    topic_dominant = integer(0),
    prob_topic_dominant = numeric(0),
    nb_termes_retenus = integer(0),
    segment_exploitable = logical(0),
    texte = character(0),
    stringsAsFactors = FALSE
  )
  if (!is.null(unites) && length(unites) > 0) {
    if (is.data.frame(unites)) {
      ids <- as.character(unites$identifiant %||% character(0))
      types <- as.character(unites$type_unite %||% rep("", length(ids)))
      textes <- as.character(unites$texte %||% rep("", length(ids)))
      topics_dom <- suppressWarnings(as.integer(unites$topic_dominant %||% rep(NA_integer_, length(ids))))
      probs_dom <- suppressWarnings(as.numeric(unites$prob_topic_dominant %||% rep(NA_real_, length(ids))))
      termes_retenus <- suppressWarnings(as.integer(unites$nb_termes_retenus %||% rep(0L, length(ids))))
      segments_exploitables <- as.logical(unites$segment_exploitable %||% rep(TRUE, length(ids)))
      dists <- if ("distribution_topics" %in% names(unites)) unites$distribution_topics else list()
    } else {
      ids <- vapply(unites, function(unit) as.character(unit$identifiant %||% ""), character(1))
      types <- vapply(unites, function(unit) as.character(unit$type_unite %||% ""), character(1))
      textes <- vapply(unites, function(unit) as.character(unit$texte %||% ""), character(1))
      topics_dom <- suppressWarnings(vapply(unites, function(unit) as.integer(unit$topic_dominant %||% NA_integer_), integer(1)))
      probs_dom <- suppressWarnings(vapply(unites, function(unit) as.numeric(unit$prob_topic_dominant %||% NA_real_), numeric(1)))
      termes_retenus <- suppressWarnings(vapply(unites, function(unit) as.integer(unit$nb_termes_retenus %||% 0L), integer(1)))
      segments_exploitables <- vapply(unites, function(unit) isTRUE(unit$segment_exploitable %||% TRUE), logical(1))
      dists <- lapply(unites, function(unit) as.numeric(unlist(unit$distribution_topics %||% list(), use.names = FALSE)))
    }

    keep_ids <- nzchar(ids)
    ids <- ids[keep_ids]
    types <- types[keep_ids]
    textes <- textes[keep_ids]
    topics_dom <- topics_dom[keep_ids]
    probs_dom <- probs_dom[keep_ids]
    termes_retenus <- termes_retenus[keep_ids]
    segments_exploitables <- segments_exploitables[keep_ids]
    if (length(dists)) {
      dists <- dists[keep_ids]
    }
    if (length(ids)) {
      doc_topics <- data.frame(doc_id = ids, stringsAsFactors = FALSE)
      doc_topics_segments <- data.frame(
        doc_id = ids,
        type_unite = types,
        topic_dominant = topics_dom,
        prob_topic_dominant = probs_dom,
        nb_termes_retenus = termes_retenus,
        segment_exploitable = segments_exploitables,
        texte = textes,
        stringsAsFactors = FALSE
      )
      if (length(dists)) {
        max_k <- max(vapply(dists, length, integer(1)))
        for (k in seq_len(max_k)) {
          colk <- vapply(dists, function(x) as.numeric(x[[k]] %||% NA_real_), numeric(1))
          doc_topics[[paste0("Topic_", k)]] <- colk[seq_len(nrow(doc_topics))]
          doc_topics_segments[[paste0("Topic_", k)]] <- colk[seq_len(nrow(doc_topics_segments))]
        }

        topic_dom_from_dist <- vapply(dists, function(x) {
          values <- as.numeric(x)
          if (!length(values) || all(!is.finite(values))) return(NA_integer_)
          which.max(replace(values, !is.finite(values), -Inf))
        }, integer(1))
        prob_dom_from_dist <- vapply(dists, function(x) {
          values <- as.numeric(x)
          if (!length(values) || all(!is.finite(values))) return(NA_real_)
          max(replace(values, !is.finite(values), -Inf))
        }, numeric(1))

        segments_exploitables_fill <- rep(TRUE, nrow(doc_topics_segments))
        if ("segment_exploitable" %in% names(doc_topics_segments)) {
          segments_exploitables_fill <- isTRUE(doc_topics_segments$segment_exploitable) |
            (!is.na(doc_topics_segments$segment_exploitable) & as.logical(doc_topics_segments$segment_exploitable))
        }

        if (!length(doc_topics_segments$topic_dominant) || all(!is.finite(doc_topics_segments$topic_dominant))) {
          doc_topics_segments$topic_dominant <- rep(NA_integer_, length(topic_dom_from_dist))
          doc_topics_segments$topic_dominant[segments_exploitables_fill] <- topic_dom_from_dist[segments_exploitables_fill]
        } else {
          needs_fill <- segments_exploitables_fill & !is.finite(doc_topics_segments$topic_dominant)
          doc_topics_segments$topic_dominant[needs_fill] <- topic_dom_from_dist[needs_fill]
          doc_topics_segments$topic_dominant[!segments_exploitables_fill] <- NA_integer_
        }

        needs_prob_fill <- segments_exploitables_fill & !is.finite(doc_topics_segments$prob_topic_dominant)
        doc_topics_segments$prob_topic_dominant[needs_prob_fill] <- prob_dom_from_dist[needs_prob_fill]
        doc_topics_segments$prob_topic_dominant[!segments_exploitables_fill] <- NA_real_
      }
    }
  }

  wordcloud_images <- character(0)
  if (!is.null(res_wc_json$fichiers) && length(res_wc_json$fichiers) > 0) {
    fichiers_df <- as.data.frame(res_wc_json$fichiers, stringsAsFactors = FALSE)
    if ("image" %in% names(fichiers_df)) {
      wordcloud_images <- as.character(fichiers_df$image)
    }
  }

  list(
    top_terms = top_terms,
    topic_term_matrix = mat,
    topic_term_matrix_df = topic_term_matrix_df,
    doc_topics = doc_topics,
    doc_topics_segments = doc_topics_segments,
    wordcloud_images = wordcloud_images,
    meta = res_lda_json$meta %||% list(),
    brut = res_lda_json
  )
}

executer_lda_python_batch <- function(corpus_texte, config, lda_dir) {
  python_exec <- trouver_python_lda_batch()
  script_lda <- normalizePath(file.path(repo_root, "lda", "lda.py"), mustWork = TRUE)
  script_heatmap <- normalizePath(file.path(repo_root, "lda", "heatmap_lda.py"), mustWork = TRUE)
  script_wc <- normalizePath(file.path(repo_root, "lda", "wordcloud_lda.py"), mustWork = TRUE)
  input_json <- file.path(lda_dir, "lda_python_input.json")
  output_json <- file.path(lda_dir, "lda_python_output.json")
  pyldavis_html <- file.path(lda_dir, "pyldavis.html")
  heatmap_png <- file.path(lda_dir, "heatmap_lda.png")
  wordcloud_json <- file.path(lda_dir, "wordclouds_manifest.json")
  wordcloud_dir <- file.path(lda_dir, "wordclouds")
  matplotlib_cache <- file.path(tempdir(), "iramuteq-lite-matplotlib")
  dir.create(matplotlib_cache, recursive = TRUE, showWarnings = FALSE)
  python_env <- c(
    paste0("MPLCONFIGDIR=", matplotlib_cache),
    paste0("XDG_CACHE_HOME=", tempdir())
  )

  stopwords_fr <- construire_stopwords_fr_quanteda_batch(scalar_bool(config$lda_retirer_stopwords, FALSE))
  categories <- if (scalar_bool(config$lda_filtrage_morpho, TRUE)) {
    as.list(tolower(as.character(as_char_vec(config$lda_pos_keep, c("NOM", "VER", "ADJ")))))
  } else {
    list()
  }
  lda_ngram_range <- normaliser_ngram_range_batch(config$lda_ngram_range, c(1L, 1L))
  lda_max_df <- scalar_num(config$lda_max_df, 0.95)
  if (!is.finite(lda_max_df) || is.na(lda_max_df)) lda_max_df <- 0.95
  lda_max_df <- min(1, max(0.01, lda_max_df))

  payload <- list(
    corpus_texte = corpus_texte,
    mode_unite = scalar_chr(config$lda_mode_unite, "segment"),
    longueur_min_segment = max(10L, scalar_int(config$lda_segment_size, 40L, 5L) * 4L),
    nb_topics = scalar_int(config$lda_k, 6L, 2L),
    nb_mots_par_topic = scalar_int(config$lda_n_terms, 8L, 3L),
    min_df = scalar_int(config$lda_min_df, 1L, 1L),
    max_df = lda_max_df,
    max_iter = scalar_int(config$lda_max_iter, 100L, 1L),
    ngram_range = as.list(lda_ngram_range),
    random_state = 42L,
    stopwords_personnalises = as.list(stopwords_fr),
    categories_morpho = categories,
    chemin_lexique_fr = normalizePath(file.path(repo_root, "dictionnaires", "lexique_fr.csv"), mustWork = FALSE)
  )

  jsonlite::write_json(payload, input_json, auto_unbox = TRUE, pretty = TRUE)

  logs_lda <- executer_commande_python_batch(
    python_exec,
    args = c(script_lda, "--input", input_json, "--output", output_json, "--vis-output", pyldavis_html),
    etiquette = "lda.py",
    env = python_env
  )
  if (!file.exists(output_json)) {
    stop(paste0("lda.py n'a pas produit de sortie JSON.\nLogs Python:\n", paste(logs_lda, collapse = "\n")))
  }
  res_lda <- jsonlite::fromJSON(output_json, simplifyVector = FALSE)
  if (!isTRUE(res_lda$succes)) {
    stop(as.character(res_lda$erreur %||% "Erreur inconnue dans lda.py"))
  }

  logs_heatmap <- character(0)
  heatmap_error <- NULL
  tryCatch({
    heatmap_terms <- max(8L, scalar_int(config$lda_n_terms, 8L, 3L))
    max_total_terms <- max(30L, min(160L, heatmap_terms * scalar_int(config$lda_k, 4L, 2L)))
    logs_heatmap <- executer_commande_python_batch(
      python_exec,
      args = c(
        script_heatmap,
        "--input", output_json,
        "--output", heatmap_png,
        "--top-n-per-topic", as.character(heatmap_terms),
        "--max-total-terms", as.character(max_total_terms)
      ),
      etiquette = "heatmap_lda.py",
      env = python_env
    )
  }, error = function(e) {
    heatmap_error <<- conditionMessage(e)
  })

  res_wc <- list(succes = FALSE, fichiers = list())
  logs_wc <- character(0)
  wc_error <- NULL
  tryCatch({
    logs_wc <- executer_commande_python_batch(
      python_exec,
      args = c(script_wc, "--input", output_json, "--output", wordcloud_json, "--output-dir", wordcloud_dir, "--prefix", "wordcloud_lda"),
      etiquette = "wordcloud_lda.py",
      env = python_env
    )
    if (file.exists(wordcloud_json)) {
      res_wc <- jsonlite::fromJSON(wordcloud_json, simplifyVector = FALSE)
    }
  }, error = function(e) {
    wc_error <<- conditionMessage(e)
  })

  conv <- convertir_resultat_python_lda_batch(res_lda, res_wc)

  list(
    top_terms = conv$top_terms,
    topic_term_matrix_df = conv$topic_term_matrix_df,
    doc_topics = conv$doc_topics,
    doc_topics_segments = conv$doc_topics_segments,
    topic_term_matrix = conv$topic_term_matrix,
    wordcloud_images = conv$wordcloud_images,
    pyldavis_html = if (file.exists(pyldavis_html)) pyldavis_html else NULL,
    heatmap_png = if (file.exists(heatmap_png)) heatmap_png else NULL,
    logs_lda = logs_lda,
    logs_heatmap = logs_heatmap,
    logs_wordcloud = logs_wc,
    heatmap_error = heatmap_error,
    wordcloud_error = wc_error,
    meta = conv$meta
  )
}

run_batch <- function() {
  config <- jsonlite::fromJSON(config_path, simplifyVector = FALSE)
  analyses <- config$analyses %||% list(chd = TRUE, afc = TRUE, simi = TRUE, lda = TRUE, suivi = FALSE)
  run_chd <- scalar_bool(analyses$chd, TRUE) || scalar_bool(analyses$afc, TRUE)
  run_afc <- scalar_bool(analyses$afc, TRUE)
  run_simi <- scalar_bool(analyses$simi, TRUE)
  run_lda <- scalar_bool(analyses$lda, TRUE)
  run_suivi <- scalar_bool(analyses$suivi, FALSE)

  artifacts <- list()

  write_status(state = "running", progress = 3, message = "Initialisation du runner batch.")
  log_info(paste0("output_dir = ", output_dir), progress = 4)
  log_info("Import du corpus.", progress = 8)
  log_info(paste0("MD5 fichier = ", unname(tools::md5sum(input_path))), progress = 9)
  corpus_importe <- import_corpus_iramuteq(input_path)
  log_info(paste0("Nombre de documents importés : ", quanteda::ndoc(corpus_importe)), progress = 10)

  classif_mode <- scalar_chr(config$iramuteq_classif_mode, "simple")
  if (!classif_mode %in% c("simple", "double")) classif_mode <- "simple"
  if (identical(classif_mode, "double")) {
    segmented_corpus <- split_segments_double_rst(
      corpus_importe,
      rst1 = scalar_int(config$iramuteq_rst1, 12L, 2L),
      rst2 = scalar_int(config$iramuteq_rst2, 14L, 2L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
    log_info(
      paste0(
        "Segmentation CHD double (RST): rst1=",
        scalar_int(config$iramuteq_rst1, 12L, 2L),
        " | rst2=",
        scalar_int(config$iramuteq_rst2, 14L, 2L),
        "."
      ),
      progress = 16
    )
  } else {
    segmented_corpus <- split_segments(
      corpus_importe,
      segment_size = scalar_int(config$segment_size, 40L, 1L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
  }
  log_info(paste0("Corpus segmenté en ", quanteda::ndoc(segmented_corpus), " segments."), progress = 18)
  log_info(paste0("Nombre de segments analysés : ", quanteda::ndoc(segmented_corpus)), progress = 19)
  log_info(paste0("Nombre de segments après découpage : ", quanteda::ndoc(segmented_corpus)), progress = 20)

  pipeline <- preparer_pipeline_chd(segmented_corpus, config)
  filtered_corpus <- pipeline$filtered_corpus
  dfm_obj <- pipeline$dfm_obj
  filtered_corpus_suivi <- filtered_corpus
  dfm_suivi <- dfm_obj
  tok <- pipeline$tok
  textes_indexation <- pipeline$textes_indexation
  lexique_fr_df <- pipeline$lexique_fr_df
  corpus_stats <- pipeline$corpus_stats
  log_info(paste0("DFM préparé : ", quanteda::ndoc(dfm_obj), " segments / ", quanteda::nfeat(dfm_obj), " termes."), progress = 42)
  log_info(
    "IRaMuTeQ-lite : paramètres de prétraitement / DFM (min_docfreq, stopwords, ponctuation, dictionnaire) appliqués dans backend/r/run_iramuteq_batch.R",
    progress = 43
  )
  log_info(
    paste0("Nombre de mots conservés pour l'analyse après prétraitements : ", length(unlist(tok, use.names = FALSE))),
    progress = 44
  )

  chd <- NULL
  classes_info <- NULL
  classes <- NULL
  res_stats_df <- NULL
  filtered_corpus_ok <- NULL
  dfm_ok <- NULL
  classes_ok <- NULL

  if (run_chd) {
    log_info("Calcul CHD.", progress = 52)
    log_info("Mode : classification IRaMuTeQ-lite.", progress = 52)
    log_info(
      paste0(
        "Paramètres IRaMuTeQ-lite : k=",
        scalar_int(config$k_iramuteq, 10L, 2L),
        " | mincl_mode=",
        scalar_chr(config$iramuteq_mincl_mode, "auto"),
        if (identical(scalar_chr(config$iramuteq_mincl_mode, "auto"), "manuel")) {
          paste0(" | mincl=", scalar_int(config$iramuteq_mincl, 5L, 1L))
        } else {
          ""
        },
        " | classif_mode=",
        classif_mode,
        if (identical(classif_mode, "double")) {
          paste0(
            " | rst1=",
            scalar_int(config$iramuteq_rst1, 12L, 2L),
            " | rst2=",
            scalar_int(config$iramuteq_rst2, 14L, 2L)
          )
        } else {
          ""
        },
        " | segmenter_sur_ponctuation_forte=",
        ifelse(scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE), "1", "0"),
        " | svd_method=",
        scalar_chr(config$iramuteq_svd_method, "irlba"),
        " | max_formes=",
        scalar_int(config$iramuteq_max_formes, 20000L, 1L),
        " | stats_mode=",
        scalar_chr(config$iramuteq_stats_mode, "vectorise")
      ),
      progress = 53
    )
    res_ira <- lancer_moteur_chd_iramuteq(
      dfm_obj = dfm_obj,
      k = scalar_int(config$k_iramuteq, 10L, 2L),
      mincl_mode = scalar_chr(config$iramuteq_mincl_mode, "auto"),
      mincl = scalar_int(config$iramuteq_mincl, 5L, 1L),
      classif_mode = classif_mode,
      svd_method = scalar_chr(config$iramuteq_svd_method, "irlba"),
      mode_patate = FALSE,
      binariser = TRUE,
      rscripts_dir = file.path(repo_root, "iramuteqlite"),
      max_formes = scalar_int(config$iramuteq_max_formes, 20000L, 1L)
    )
    chd <- res_ira$chd
    if (!is.null(res_ira$dfm_utilise)) {
      dfm_obj <- res_ira$dfm_utilise
    }
    if (is.list(res_ira$max_formes_info) &&
        all(c("max_formes", "n_feat_avant", "n_feat_apres") %in% names(res_ira$max_formes_info))) {
      log_info(
        paste0(
          "Nombre maximum de formes analysées appliqué (chd_iramuteq.R) = ",
          res_ira$max_formes_info$max_formes,
          " (",
          res_ira$max_formes_info$n_feat_avant,
          " -> ",
          res_ira$max_formes_info$n_feat_apres,
          ")."
        ),
        progress = 56
      )
    }
    if (isTRUE(res_ira$fallback_mincl1)) {
      log_info("Ajustement automatique : reconstruction des classes avec mincl=1 pour éviter une fusion excessive des classes terminales.")
    }

    classes <- as.integer(res_ira$classes)
    if (all(is.na(classes)) || length(unique(classes[classes > 0])) < 2) {
      stop("IRaMuTeQ-lite n'a pas pu produire au moins 2 classes exploitables.")
    }
    classes_info <- list(terminales = res_ira$terminales, mincl = res_ira$mincl)
    quanteda::docvars(filtered_corpus, "Classes") <- classes

    idx_ok <- !is.na(classes) & classes > 0
    nb_non_assignes <- sum(!idx_ok)
    if (nb_non_assignes > 0) {
      log_info(
        paste0(
          "Segments non assignés à une classe terminale (Classe 0 / NA) : ",
          nb_non_assignes,
          ". Exclusion des calculs CHD/AFC."
        )
      )
    }

    filtered_corpus_ok <- filtered_corpus[idx_ok]
    dfm_ok <- dfm_obj[idx_ok, ]
    classes_ok <- as.integer(quanteda::docvars(filtered_corpus_ok)$Classes)

    if (quanteda::ndoc(dfm_ok) < 2) stop("Apres classification, il reste moins de 2 segments classes (hors NA).")
    if (quanteda::nfeat(dfm_ok) < 2) stop("Apres classification, le DFM classe est trop pauvre (moins de 2 termes).")

    if (scalar_bool(config$expression_utiliser_dictionnaire, FALSE)) {
      expression_df_log <- pipeline$expressions_actives_df
      if (!is.null(expression_df_log) &&
          is.data.frame(expression_df_log) &&
          nrow(expression_df_log) > 0 &&
          "dic_norm" %in% names(expression_df_log)) {
        expr_norm <- unique(tolower(trimws(as.character(expression_df_log$dic_norm))))
        expr_norm <- expr_norm[nzchar(expr_norm)]
        if (length(expr_norm) > 0) {
          feats_ok <- tolower(trimws(as.character(quanteda::featnames(dfm_ok))))
          expr_dans_dfm_ok <- intersect(expr_norm, feats_ok)
          log_info(
            paste0(
              "Expressions (dic_norm) conservées dans le DFM final CHD/AFC : ",
              length(expr_dans_dfm_ok),
              "/",
              length(expr_norm),
              "."
            )
          )
          if ("source_expr" %in% names(expression_df_log)) {
            expr_norm_user <- unique(tolower(trimws(as.character(expression_df_log$dic_norm[expression_df_log$source_expr == "user"]))))
            expr_norm_user <- expr_norm_user[nzchar(expr_norm_user)]
            if (length(expr_norm_user) > 0) {
              expr_user_dans_dfm_ok <- intersect(expr_norm_user, feats_ok)
              log_info(
                paste0(
                  "Expressions utilisateur conservées dans le DFM final CHD/AFC : ",
                  length(expr_user_dans_dfm_ok),
                  "/",
                  length(expr_norm_user),
                  "."
                )
              )
            }
          }
        }
      }
    }

    log_info("Statistiques CHD : calcul IRaMuTeQ-lite (contingence classe x terme).", progress = 58)
    res_stats_df <- construire_stats_classes_iramuteq(
      dfm_obj = dfm_ok,
      classes = classes_ok,
      max_p = 1,
      stats_mode = scalar_chr(config$iramuteq_stats_mode, "vectorise")
    )
    res_stats_df$Classe <- normaliser_id_classe_local(res_stats_df$Classe)
    ord_stats <- with(
      res_stats_df,
      order(
        suppressWarnings(as.integer(Classe)),
        -suppressWarnings(as.numeric(chi2)),
        na.last = TRUE
      )
    )
    res_stats_df <- res_stats_df[ord_stats, , drop = FALSE]

    if (!is.null(lexique_fr_df) &&
        "Terme" %in% names(res_stats_df) &&
        exists("construire_type_lexique_fr", mode = "function", inherits = TRUE)) {
      res_stats_df$Type <- construire_type_lexique_fr(res_stats_df$Terme, lexique_fr_df)
      log_info(paste0("Lexique (fr) chargé pour typer les termes CHD : ", nrow(lexique_fr_df), " entrées."))
    }
    if (scalar_bool(config$expression_utiliser_dictionnaire, FALSE) &&
        !is.null(pipeline$expressions_actives_df) &&
        "dic_norm" %in% names(pipeline$expressions_actives_df) &&
        "Terme" %in% names(res_stats_df)) {
      expr_stats_norm <- unique(tolower(trimws(as.character(pipeline$expressions_actives_df$dic_norm))))
      expr_stats_norm <- expr_stats_norm[nzchar(expr_stats_norm)]
      stats_terms <- unique(tolower(trimws(as.character(res_stats_df$Terme))))
      stats_terms <- stats_terms[nzchar(stats_terms)]
      expr_visibles_stats <- intersect(expr_stats_norm, stats_terms)
      log_info(
        paste0(
          "Expressions visibles dans les stats CHD exportées : ",
          length(expr_visibles_stats),
          "/",
          length(expr_stats_norm),
          "."
        )
      )
      if ("source_expr" %in% names(pipeline$expressions_actives_df)) {
        expr_user_stats_norm <- unique(tolower(trimws(as.character(
          pipeline$expressions_actives_df$dic_norm[pipeline$expressions_actives_df$source_expr == "user"]
        ))))
        expr_user_stats_norm <- expr_user_stats_norm[nzchar(expr_user_stats_norm)]
        if (length(expr_user_stats_norm) > 0) {
          expr_user_visibles_stats <- intersect(expr_user_stats_norm, stats_terms)
          log_info(
            paste0(
              "Expressions utilisateur visibles dans les stats CHD exportées : ",
              length(expr_user_visibles_stats),
              "/",
              length(expr_user_stats_norm),
              "."
            )
          )
        }
      }
    }
    stats_file <- file.path(output_dir, "stats_par_classe.csv")
    res_stats_df$p_scientifique <- formatter_p_scientifique_batch(res_stats_df$p)
    res_stats_df$p_seuil_01 <- formatter_p_seuil_01_batch(res_stats_df$p)
    ecrire_csv_6_decimales(res_stats_df, stats_file, row.names = FALSE)
    artifacts$stats_par_classe <- relative_to_output(stats_file)

    segments_vec <- as.character(filtered_corpus_ok)
    ids_segments <- as.character(quanteda::docnames(filtered_corpus_ok))
    names(segments_vec) <- ids_segments
    idx_chd <- match(ids_segments, names(textes_indexation))
    ok_chd <- !is.na(idx_chd)
    if (any(ok_chd)) {
      segments_vec[ok_chd] <- as.character(textes_indexation[idx_chd[ok_chd]])
    }
    segments_by_class <- split(segments_vec, classes_ok)
    segments_file <- file.path(output_dir, "segments_par_classe.txt")
    writeLines(unlist(lapply(names(segments_by_class), function(cl) c(paste0("Classe ", cl, ":"), unname(segments_by_class[[cl]]), ""))), segments_file)
    artifacts$segments_par_classe <- relative_to_output(segments_file)

    dendrogram_width <- clamp_int(
      scalar_int(config$chd_dendrogram_width_px, 1400L, 1200L),
      1200L,
      2400L
    )
    dendrogram_height <- clamp_int(
      scalar_int(config$chd_dendrogram_height_px, as.integer(round(dendrogram_width * 0.52)), 620L),
      620L,
      1400L
    )

    chd_png <- file.path(output_dir, "dendrogramme_chd.png")
    grDevices::png(chd_png, width = dendrogram_width, height = dendrogram_height, res = 180)
    tracer_dendrogramme_iramuteq_ui(
      rv = list(
        res = list(
          chd = chd,
          terminales = classes_info$terminales,
          classes = classes
        ),
        filtered_corpus = filtered_corpus_ok,
        res_stats_df = res_stats_df
      ),
      top_n_terms = 4,
      orientation = "horizontal",
      style_affichage = "iramuteq_bars"
    )
    grDevices::dev.off()
    artifacts$dendrogramme_chd <- relative_to_output(chd_png)
    log_info("Export du dendrogramme IRaMuTeQ terminé.", progress = 63)

    chd_factoextra_png <- file.path(output_dir, "dendrogramme_chd_factoextra.png")
    grDevices::png(chd_factoextra_png, width = dendrogram_width, height = dendrogram_height, res = 180)
    tracer_dendrogramme_iramuteq_ui(
      rv = list(
        res = list(
          chd = chd,
          terminales = classes_info$terminales,
          classes = classes
        ),
        filtered_corpus = filtered_corpus_ok,
        res_stats_df = res_stats_df
      ),
      top_n_terms = 4,
      orientation = "horizontal",
      style_affichage = "factoextra"
    )
    grDevices::dev.off()
    artifacts$dendrogramme_chd_factoextra <- relative_to_output(chd_factoextra_png)
    log_info("Export du dendrogramme factoextra terminé.", progress = 64)

    html_file <- file.path(output_dir, "segments_par_classe.html")
    textes_index_ok <- textes_indexation[quanteda::docnames(dfm_ok)]
    names(textes_index_ok) <- quanteda::docnames(dfm_ok)
    args_concordancier <- list(
      chemin_sortie = html_file,
      segments_by_class = segments_by_class,
      res_stats_df = res_stats_df,
      max_p = if (scalar_bool(config$filtrer_affichage_pvalue, TRUE)) scalar_num(config$max_p, 0.05) else 1,
      filtrer_pvalue = scalar_bool(config$filtrer_affichage_pvalue, TRUE),
      textes_indexation = textes_index_ok,
      rv = list(lexique_fr_df = lexique_fr_df)
    )

    html_genere <- tryCatch(
      do.call(generer_concordancier_iramuteq_html, args_concordancier),
      error = function(e) {
        log_info(paste0("Concordancier HTML : échec de la première génération - ", e$message))
        NA_character_
      }
    )

    candidats_html <- unique(c(
      html_genere,
      html_file,
      file.path(output_dir, "concordancier.html")
    ))
    candidats_html <- candidats_html[is.character(candidats_html) & !is.na(candidats_html) & nzchar(candidats_html)]
    html_existants <- candidats_html[file.exists(candidats_html)]

    if (length(html_existants) == 0) {
      html_fallback <- file.path(output_dir, "concordancier.html")
      args_concordancier$chemin_sortie <- html_fallback
      log_info("Concordancier HTML introuvable après la première génération. Nouvelle tentative vers exports/concordancier.html.")
      html_retry <- tryCatch(
        do.call(generer_concordancier_iramuteq_html, args_concordancier),
        error = function(e) {
          log_info(paste0("Concordancier HTML : échec de la relance - ", e$message))
          NA_character_
        }
      )

      candidats_retry <- unique(c(html_retry, html_fallback, html_genere, html_file))
      candidats_retry <- candidats_retry[is.character(candidats_retry) & !is.na(candidats_retry) & nzchar(candidats_retry)]
      html_existants <- candidats_retry[file.exists(candidats_retry)]
    }

    if (length(html_existants) > 0) {
      artifacts$concordancier_html <- relative_to_output(html_existants[[1]])
      log_info(paste0("Concordancier HTML valide : ", html_existants[[1]]), progress = 66)
    } else {
      html_diag <- file.path(output_dir, "concordancier.html")
      diag_lines <- c(
        "<html><head><meta charset='utf-8'/>",
        "<style>body{font-family:Arial,sans-serif;line-height:1.5;padding:1rem 1.2rem;} code{background:#f7f7f7;padding:.1rem .3rem;border-radius:3px;}</style>",
        "</head><body>",
        "<h2>Concordancier indisponible</h2>",
        "<p>Le concordancier HTML n'a pas pu être généré automatiquement pour cette analyse.</p>",
        "<p>Vérifiez le journal de l'analyse puis relancez si nécessaire.</p>",
        paste0("<p><strong>Dossier d'exports :</strong> <code>", htmltools::htmlEscape(output_dir), "</code></p>"),
        "</body></html>"
      )
      ok_diag <- tryCatch({
        writeLines(diag_lines, html_diag, useBytes = TRUE)
        file.exists(html_diag)
      }, error = function(e) {
        log_info(paste0("Concordancier HTML : impossible d'écrire le fichier de diagnostic - ", e$message))
        FALSE
      })

      if (isTRUE(ok_diag)) {
        artifacts$concordancier_html <- relative_to_output(html_diag)
        log_info(paste0("Concordancier HTML de diagnostic généré : ", html_diag), progress = 66)
      } else {
        log_info("Concordancier HTML indisponible après toutes les tentatives.", progress = 66)
      }
    }

    wordcloud_dir <- file.path(output_dir, "wordclouds")
    dir.create(wordcloud_dir, recursive = TRUE, showWarnings = FALSE)
    classes_uniques <- sort(unique(classes_ok))
    generer_wordclouds_iramuteq(
      res_stats_df = res_stats_df,
      classes_uniques = classes_uniques,
      wordcloud_dir = wordcloud_dir,
      top_n = scalar_int(config$top_n, 20L, 5L),
      filtrer_pvalue = scalar_bool(config$filtrer_affichage_pvalue, TRUE),
      max_p = scalar_num(config$max_p, 0.05)
    )
    artifacts$wordclouds <- unname(vapply(list.files(wordcloud_dir, pattern = "\\.png$", full.names = TRUE), relative_to_output, character(1)))
    log_info("Mode IRaMuTeQ-lite : nuages de mots générés via wordcloud_iramuteq.R.", progress = 67)

    log_info("Exports CHD générés.", progress = 68)
  }

  if (run_suivi) {
    suivi_progress <- 54
    suivi_longitudinal <- tryCatch(
      generer_exports_suivi_longitudinal_chd(
        filtered_corpus_ok = filtered_corpus_suivi,
        dfm_ok = dfm_suivi,
        tok_ok = tok,
        classes_ok = classes_ok,
        output_dir = output_dir,
        textes_indexation = textes_indexation,
        variable_suivi = scalar_chr(config$suivi_variable_etoilee, ""),
        variable_filtre = scalar_chr(config$suivi_filtre_variable_etoilee, ""),
        modalite_filtre = scalar_chr(config$suivi_filtre_modalite, ""),
        modalites_selectionnees = as_char_vec(config$suivi_modalites_selectionnees, character(0)),
        ordre_chronologique = scalar_chr(config$suivi_ordre_chronologique, "asc"),
        unite_lexicale = scalar_chr(config$suivi_unite_lexicale, "unigramme"),
        couche_analyse = scalar_chr(config$suivi_couche_analyse, "lexicale_brute"),
        lexique_emotionnel = scalar_chr(config$suivi_lexique_emotionnel, "feel"),
        top_n_terms = scalar_int(config$suivi_top_terms, 12L, 3L),
        amplification_signal = scalar_num(config$suivi_amplification_signal, 1),
        pretraitement_label = if (scalar_bool(config$lexique_utiliser_lemmes, TRUE)) "lemmes" else "formes",
        source_dictionnaire = scalar_chr(config$source_dictionnaire, "lexique_fr"),
        filtrage_morpho = scalar_bool(config$filtrage_morpho, FALSE),
        pos_lexique_a_conserver = as_char_vec(config$pos_lexique_a_conserver, character(0)),
        morpho_exclure_etre = scalar_bool(config$morpho_exclure_etre, FALSE),
        morpho_conserver_hors_lexique = scalar_bool(config$morpho_conserver_hors_lexique, TRUE),
        logger = function(message) log_info(message, progress = suivi_progress)
      ),
      error = function(e) {
        log_info(paste0("Suivi longitudinal : calcul ignoré (", e$message, ")."), progress = suivi_progress)
        NULL
      }
    )

    if (!is.null(suivi_longitudinal) && is.list(suivi_longitudinal$files)) {
      artifacts$sante <- list(
        suivi_meta_csv = relative_to_output(suivi_longitudinal$files$meta),
        indicateurs_entretiens_csv = relative_to_output(suivi_longitudinal$files$indicators),
        divergence_jensen_shannon_successive_csv = relative_to_output(suivi_longitudinal$files$jsd_successive),
        divergence_jensen_shannon_reference_csv = relative_to_output(suivi_longitudinal$files$jsd_reference),
        detection_ruptures_discursives_csv = relative_to_output(suivi_longitudinal$files$ruptures),
        termes_evolution_csv = relative_to_output(suivi_longitudinal$files$terms),
        contributions_divergence_jensen_shannon_csv = relative_to_output(suivi_longitudinal$files$contributions),
        matrice_divergence_jensen_shannon_csv = relative_to_output(suivi_longitudinal$files$matrix),
        concordancier_jsd_csv = relative_to_output(suivi_longitudinal$files$concordancier),
        profils_emotionnels_csv = relative_to_output(suivi_longitudinal$files$emotion_profiles),
        profils_valence_csv = relative_to_output(suivi_longitudinal$files$valence_profiles),
        entropie_lexicale_png = if (!is.null(suivi_longitudinal$files$entropy_plot) &&
          nzchar(as.character(suivi_longitudinal$files$entropy_plot)) &&
          file.exists(suivi_longitudinal$files$entropy_plot)) {
          relative_to_output(suivi_longitudinal$files$entropy_plot)
        } else {
          NULL
        },
        redondance_relative_png = if (!is.null(suivi_longitudinal$files$redundancy_plot) &&
          nzchar(as.character(suivi_longitudinal$files$redundancy_plot)) &&
          file.exists(suivi_longitudinal$files$redundancy_plot)) {
          relative_to_output(suivi_longitudinal$files$redundancy_plot)
        } else {
          NULL
        },
        divergence_jensen_shannon_successive_png = if (!is.null(suivi_longitudinal$files$jsd_successive_plot) &&
          nzchar(as.character(suivi_longitudinal$files$jsd_successive_plot)) &&
          file.exists(suivi_longitudinal$files$jsd_successive_plot)) {
          relative_to_output(suivi_longitudinal$files$jsd_successive_plot)
        } else {
          NULL
        },
        divergence_jensen_shannon_reference_png = if (!is.null(suivi_longitudinal$files$jsd_reference_plot) &&
          nzchar(as.character(suivi_longitudinal$files$jsd_reference_plot)) &&
          file.exists(suivi_longitudinal$files$jsd_reference_plot)) {
          relative_to_output(suivi_longitudinal$files$jsd_reference_plot)
        } else {
          NULL
        },
        detection_ruptures_discursives_png = if (!is.null(suivi_longitudinal$files$ruptures_plot) &&
          nzchar(as.character(suivi_longitudinal$files$ruptures_plot)) &&
          file.exists(suivi_longitudinal$files$ruptures_plot)) {
          relative_to_output(suivi_longitudinal$files$ruptures_plot)
        } else {
          NULL
        },
        matrice_divergence_jensen_shannon_png = if (!is.null(suivi_longitudinal$files$matrix_plot) &&
          nzchar(as.character(suivi_longitudinal$files$matrix_plot)) &&
          file.exists(suivi_longitudinal$files$matrix_plot)) {
          relative_to_output(suivi_longitudinal$files$matrix_plot)
        } else {
          NULL
        },
        profils_emotionnels_png = if (!is.null(suivi_longitudinal$files$emotion_profiles_plot) &&
          nzchar(as.character(suivi_longitudinal$files$emotion_profiles_plot)) &&
          file.exists(suivi_longitudinal$files$emotion_profiles_plot)) {
          relative_to_output(suivi_longitudinal$files$emotion_profiles_plot)
        } else {
          NULL
        },
        profils_valence_png = if (!is.null(suivi_longitudinal$files$valence_profiles_plot) &&
          nzchar(as.character(suivi_longitudinal$files$valence_profiles_plot)) &&
          file.exists(suivi_longitudinal$files$valence_profiles_plot)) {
          relative_to_output(suivi_longitudinal$files$valence_profiles_plot)
        } else {
          NULL
        },
        frises_emergences = if (!is.null(suivi_longitudinal$files$frises_emergences) &&
          length(suivi_longitudinal$files$frises_emergences)) {
          unname(vapply(suivi_longitudinal$files$frises_emergences, relative_to_output, character(1)))
        } else {
          NULL
        },
        barres_divergentes = if (!is.null(suivi_longitudinal$files$divergent_bars) &&
          length(suivi_longitudinal$files$divergent_bars)) {
          unname(vapply(suivi_longitudinal$files$divergent_bars, relative_to_output, character(1)))
        } else {
          NULL
        },
        waterfalls = if (!is.null(suivi_longitudinal$files$waterfalls) &&
          length(suivi_longitudinal$files$waterfalls)) {
          unname(vapply(suivi_longitudinal$files$waterfalls, relative_to_output, character(1)))
        } else {
          NULL
        },
        wordclouds = if (!is.null(suivi_longitudinal$files$wordclouds) &&
          length(suivi_longitudinal$files$wordclouds)) {
          unname(vapply(suivi_longitudinal$files$wordclouds, relative_to_output, character(1)))
        } else {
          NULL
        }
      )
    }
  }

  if (run_afc && !is.null(classes)) {
    log_info("Calcul AFC.", progress = 74)
    afc_dir <- file.path(output_dir, "afc")
    dir.create(afc_dir, recursive = TRUE, showWarnings = FALSE)
    termes_signif <- NULL
    if (scalar_bool(config$filtrer_affichage_pvalue, TRUE) && !is.null(res_stats_df)) {
      termes_signif <- unique(subset(res_stats_df, p <= scalar_num(config$max_p, 0.05))$Terme)
      termes_signif <- termes_signif[!is.na(termes_signif) & nzchar(termes_signif)]
      if (length(termes_signif) < 2) termes_signif <- NULL
    }

    groupes_docs <- quanteda::docvars(filtered_corpus_ok)$Classes

    afc_obj <- executer_afc_classes(
      dfm_obj = dfm_ok,
      groupes = groupes_docs,
      termes_cibles = termes_signif,
      max_termes = 400,
      seuil_p = if (scalar_bool(config$filtrer_affichage_pvalue, TRUE)) scalar_num(config$max_p, 0.05) else 1,
      rv = NULL
    )

    if (!is.null(afc_obj$termes_stats) && !is.null(res_stats_df)) {
      df_m <- afc_obj$termes_stats
      df_m$Classe_num <- suppressWarnings(as.numeric(gsub("^Classe\\s+", "", as.character(df_m$Classe_max))))
      rs <- res_stats_df

      rs2 <- rs[, intersect(c("Terme", "Classe", "chi2", "p", "frequency", "docprop", "lr"), names(rs)), drop = FALSE]
      rs2$Classe <- as.numeric(rs2$Classe)

      m <- merge(
        df_m,
        rs2,
        by.x = c("Terme", "Classe_num"),
        by.y = c("Terme", "Classe"),
        all.x = TRUE,
        suffixes = c("_global", "_stats")
      )

      if ("chi2" %in% names(m)) {
        df_m$chi2 <- ifelse(is.na(m$chi2), df_m$chi2, m$chi2)
      }
      if ("p" %in% names(m)) {
        df_m$p_value <- ifelse(is.na(m$p), df_m$p_value, m$p)
      }

      df_m$Classe_num <- NULL
      afc_obj$termes_stats <- df_m
    }

    afc_obj$termes_stats <- tryCatch(
      construire_segments_exemples_afc(afc_obj$termes_stats, dfm_obj = dfm_ok, corpus_obj = filtered_corpus_ok),
      error = function(e_seg) {
        log_info(paste0("AFC classes x termes : enrichissement des segments ignoré (", e_seg$message, ")."))
        afc_obj$termes_stats
      }
    )

    afc_classes_png <- NULL
    afc_termes_png <- NULL
    if (coords_have_two_axes(afc_obj$rowcoord) && coords_have_two_axes(afc_obj$colcoord)) {
      activer_repel <- scalar_bool(config$afc_reduire_chevauchement, TRUE)
      taille_sel <- scalar_chr(config$afc_taille_mots, "frequency")
      if (!taille_sel %in% c("frequency", "chi2")) taille_sel <- "frequency"
      top_termes <- 120L

      afc_classes_png <- file.path(afc_dir, "afc_classes.png")
      afc_termes_png <- file.path(afc_dir, "afc_termes.png")
      grDevices::png(afc_classes_png, width = 1800, height = 1400, res = 180)
      tracer_afc_classes_seules(afc_obj, axes = c(1, 2), cex_labels = 1.05)
      grDevices::dev.off()
      grDevices::png(afc_termes_png, width = 2000, height = 1600, res = 180)
      tracer_afc_classes_termes(
        afc_obj,
        axes = c(1, 2),
        top_termes = top_termes,
        taille_sel = taille_sel,
        activer_repel = activer_repel
      )
      grDevices::dev.off()
      log_info("AFC classes x termes : calcul terminé.", progress = 78)
    } else {
      log_info("AFC classes/termes : moins de deux axes disponibles, graphiques PNG ignorés.")
    }

    ecrire_csv_6_decimales(afc_obj$table, file.path(afc_dir, "table_classes_termes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(afc_obj$rowcoord, file.path(afc_dir, "coords_classes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(afc_obj$colcoord, file.path(afc_dir, "coords_termes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(afc_obj$termes_stats, file.path(afc_dir, "stats_termes.csv"), row.names = FALSE)
    if (!is.null(afc_obj$ca$eig)) {
      ecrire_csv_6_decimales(as.data.frame(afc_obj$ca$eig), file.path(afc_dir, "valeurs_propres.csv"), row.names = TRUE)
    }

    artifacts$afc <- list(
      afc_classes_png = relative_to_output(afc_classes_png),
      afc_termes_png = relative_to_output(afc_termes_png),
      stats_termes_csv = relative_to_output(file.path(afc_dir, "stats_termes.csv")),
      valeurs_propres_csv = relative_to_output(file.path(afc_dir, "valeurs_propres.csv"))
    )

    afc_vars_obj <- tryCatch(
      executer_afc_variables_etoilees(
        corpus_aligne = filtered_corpus_ok,
        groupes = classes_ok,
        max_modalites = 400,
        seuil_p = if (scalar_bool(config$filtrer_affichage_pvalue, TRUE)) scalar_num(config$max_p, 0.05) else 1,
        variables_etoilees = as_char_vec(config$afc_variables_etoilees, character(0)),
        modalites_etoilees = as_char_vec(config$afc_modalites_etoilees, character(0)),
        rv = NULL
      ),
      error = function(e) NULL
    )
    if (!is.null(afc_vars_obj) && !is.null(afc_vars_obj$ca)) {
      afc_vars_png <- NULL
      if (coords_have_two_axes(afc_vars_obj$rowcoord) && coords_have_two_axes(afc_vars_obj$colcoord)) {
        activer_repel2 <- scalar_bool(config$afc_reduire_chevauchement, TRUE)
        top_mod <- 120L
        afc_vars_png <- file.path(afc_dir, "afc_variables_etoilees.png")
        grDevices::png(afc_vars_png, width = 2000, height = 1600, res = 180)
        tracer_afc_variables_etoilees(
          afc_vars_obj,
          axes = c(1, 2),
          top_modalites = top_mod,
          activer_repel = activer_repel2
        )
        grDevices::dev.off()
      } else {
        log_info("AFC variables étoilées : moins de deux axes disponibles, graphique PNG ignoré.")
      }
      log_info("AFC variables étoilées : calcul terminé.", progress = 80)
      ecrire_csv_6_decimales(afc_vars_obj$modalites_stats, file.path(afc_dir, "stats_modalites.csv"), row.names = FALSE)
      if (!is.null(afc_vars_obj$ca$eig)) {
        ecrire_csv_6_decimales(as.data.frame(afc_vars_obj$ca$eig), file.path(afc_dir, "valeurs_propres_vars.csv"), row.names = TRUE)
      }
      artifacts$afc$afc_variables_png <- relative_to_output(afc_vars_png)
      artifacts$afc$stats_modalites_csv <- relative_to_output(file.path(afc_dir, "stats_modalites.csv"))
      artifacts$afc$valeurs_propres_vars_csv <- relative_to_output(file.path(afc_dir, "valeurs_propres_vars.csv"))
    }
  }

  if (run_simi) {
    log_info("Calcul similitudes.", progress = 84)
    simi <- construire_graphe_similitudes(
      dfm_obj = dfm_obj,
      method = scalar_chr(config$simi_method, "cooc"),
      seuil = if (is.null(config$simi_seuil) || !length(config$simi_seuil) || is.na(config$simi_seuil[[1]])) NA_real_ else scalar_num(config$simi_seuil, NA_real_),
      max_tree = scalar_bool(config$simi_max_tree, TRUE),
      top_terms = scalar_int(config$simi_top_terms, 100L, 5L),
      selected_terms = as_char_vec(config$simi_terms_selected, character(0)),
      layout_type = scalar_chr(config$simi_layout, "frutch"),
      communities = scalar_bool(config$simi_communities, TRUE),
      community_method = scalar_chr(config$simi_community_method, "edge_betweenness")
    )
    simi_png <- file.path(output_dir, "simi_graph.png")
    grDevices::png(simi_png, width = 1800, height = 1400, res = 180)
    tracer_graphe_similitudes_igraph(
      g = simi$graph,
      layout = simi$layout,
      edge_labels = scalar_bool(config$simi_edge_labels, TRUE),
      edge_width_by_index = scalar_bool(config$simi_edge_width_by_index, TRUE),
      vertex_text_by_freq = scalar_bool(config$simi_vertex_text_by_freq, TRUE),
      vertex_freq = simi$vertex_freq,
      communities = simi$communities,
      halo = scalar_bool(config$simi_halo, TRUE)
    )
    grDevices::dev.off()
    artifacts$simi <- list(graph_png = relative_to_output(simi_png))
    log_info("Graphe de similitudes généré.", progress = 86)
  }

  if (run_lda) {
    log_info("Calcul LDA.", progress = 90)
    lda_dir <- file.path(output_dir, "lda")
    dir.create(lda_dir, recursive = TRUE, showWarnings = FALSE)
    log_info("LDA Python : préparation du corpus brut et exécution de lda.py.", progress = 91)
    corpus_lda_brut <- paste(readLines(input_path, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
    lda_result <- executer_lda_python_batch(corpus_texte = corpus_lda_brut, config = config, lda_dir = lda_dir)
    top_terms_csv <- file.path(lda_dir, "top_terms.csv")
    topic_term_matrix_csv <- file.path(lda_dir, "topic_term_matrix.csv")
    doc_topics_csv <- file.path(lda_dir, "doc_topics.csv")
    segments_topics_csv <- file.path(lda_dir, "segments_topics.csv")
    ecrire_csv_6_decimales(lda_result$top_terms, top_terms_csv, row.names = FALSE)
    ecrire_csv_6_decimales(lda_result$topic_term_matrix_df, topic_term_matrix_csv, row.names = FALSE)
    ecrire_csv_6_decimales(lda_result$doc_topics, doc_topics_csv, row.names = FALSE)
    ecrire_csv_6_decimales(lda_result$doc_topics_segments, segments_topics_csv, row.names = FALSE)
    if (is.character(lda_result$pyldavis_html) && nzchar(lda_result$pyldavis_html) && file.exists(lda_result$pyldavis_html)) {
      log_info("Visualisation pyLDAvis générée.", progress = 93)
    } else {
      log_info("Visualisation pyLDAvis indisponible.", progress = 93)
    }
    if (is.character(lda_result$heatmap_png) && nzchar(lda_result$heatmap_png) && file.exists(lda_result$heatmap_png)) {
      log_info("Heatmap LDA mots × topics générée.", progress = 94)
    } else {
      log_info("Heatmap LDA indisponible.", progress = 94)
    }
    lda_wordclouds <- lda_result$wordcloud_images
    if (!length(lda_wordclouds) && !is.null(lda_result$topic_term_matrix) && nrow(lda_result$topic_term_matrix) > 0) {
      requested_lda_terms <- scalar_int(config$lda_n_terms, 8L, 3L)
      lda_wordclouds <- generer_wordclouds_lda_batch(
        lda_result$topic_term_matrix,
        lda_dir,
        max_words = requested_lda_terms
      )
      if (length(lda_wordclouds)) {
        log_info(paste0("Nuages de mots LDA générés via le fallback R (", requested_lda_terms, " termes par topic)."), progress = 94)
      }
    }
    if (length(lda_result$logs_lda)) {
      log_info(paste0("lda.py: ", paste(lda_result$logs_lda, collapse = " | ")))
    }
    if (length(lda_result$logs_heatmap)) {
      log_info(paste0("heatmap_lda.py: ", paste(lda_result$logs_heatmap, collapse = " | ")))
    }
    if (length(lda_result$logs_wordcloud)) {
      log_info(paste0("wordcloud_lda.py: ", paste(lda_result$logs_wordcloud, collapse = " | ")))
    }
    if (!is.null(lda_result$heatmap_error) && nzchar(lda_result$heatmap_error)) {
      log_info(paste0("heatmap_lda.py indisponible: ", lda_result$heatmap_error))
    }
    if (!is.null(lda_result$wordcloud_error) && nzchar(lda_result$wordcloud_error)) {
      log_info(paste0("wordcloud_lda.py indisponible: ", lda_result$wordcloud_error))
    }
    artifacts$lda <- list(
      top_terms_csv = relative_to_output(top_terms_csv),
      topic_term_matrix_csv = relative_to_output(topic_term_matrix_csv),
      doc_topics_csv = relative_to_output(doc_topics_csv),
      segments_topics_csv = relative_to_output(segments_topics_csv),
      pyldavis_html = if (is.character(lda_result$pyldavis_html) && nzchar(lda_result$pyldavis_html) && file.exists(lda_result$pyldavis_html)) {
        relative_to_output(lda_result$pyldavis_html)
      } else {
        NULL
      },
      heatmap_png = if (is.character(lda_result$heatmap_png) && nzchar(lda_result$heatmap_png) && file.exists(lda_result$heatmap_png)) {
        relative_to_output(lda_result$heatmap_png)
      } else {
        NULL
      },
      wordclouds = unname(vapply(lda_wordclouds, relative_to_output, character(1)))
    )
    log_info("Exports LDA générés.", progress = 94)
  }

  summary <- list(
    corpus = basename(input_path),
    n_texts = quanteda::ndoc(corpus_importe),
    n_segments = quanteda::ndoc(filtered_corpus),
    n_tokens = corpus_stats$n_tokens %||% 0,
    n_hapax = corpus_stats$n_hapax %||% 0,
    n_formes = corpus_stats$n_formes %||% 0,
    n_features = quanteda::nfeat(dfm_obj),
    n_classes = if (is.null(classes_ok)) 0L else length(unique(classes_ok)),
    zipf = corpus_stats$zipf,
    output_dir = output_dir
  )

  log_info("Analyse terminée.", progress = 100)
  payload <- list(
    success = TRUE,
    output_dir = output_dir,
    artifacts = artifacts,
    summary = summary,
    logs = job_logs
  )
  jsonlite::write_json(payload, results_file, auto_unbox = TRUE, pretty = TRUE, null = "null")
  write_status(state = "completed", progress = 100, message = "Analyse terminée.", extra = list(summary = summary, artifacts = artifacts))
  invisible(payload)
}

preview_simi_terms_batch <- function() {
  config <- jsonlite::fromJSON(config_path, simplifyVector = FALSE)

  write_status(state = "running", progress = 3, message = "Initialisation du preview similitudes.")
  log_info(paste0("output_dir = ", output_dir), progress = 4)
  log_info("Import du corpus.", progress = 8)
  corpus_importe <- import_corpus_iramuteq(input_path)
  log_info(paste0("Nombre de documents importés : ", quanteda::ndoc(corpus_importe)), progress = 10)

  classif_mode <- scalar_chr(config$iramuteq_classif_mode, "simple")
  if (!classif_mode %in% c("simple", "double")) classif_mode <- "simple"
  if (identical(classif_mode, "double")) {
    segmented_corpus <- split_segments_double_rst(
      corpus_importe,
      rst1 = scalar_int(config$iramuteq_rst1, 12L, 2L),
      rst2 = scalar_int(config$iramuteq_rst2, 14L, 2L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
  } else {
    segmented_corpus <- split_segments(
      corpus_importe,
      segment_size = scalar_int(config$segment_size, 40L, 1L),
      remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
      remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE),
      force_split_on_strong_punct = scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE)
    )
  }

  pipeline <- preparer_pipeline_chd(segmented_corpus, config)
  simi_terms <- get_simi_terms_choices_batch(pipeline$dfm_obj)
  payload <- list(
    success = TRUE,
    terms = simi_terms$terms,
    ordered_terms = unname(as.character(simi_terms$ordered_terms)),
    logs = job_logs
  )
  jsonlite::write_json(payload, results_file, auto_unbox = TRUE, pretty = TRUE, null = "null")
  write_status(state = "completed", progress = 100, message = "Prévisualisation des similitudes terminée.")
  invisible(payload)
}

mode <- scalar_chr(args$mode, "run")
if (identical(mode, "preview_simi_terms")) {
  tryCatch(
    preview_simi_terms_batch(),
    error = function(e) {
      message <- conditionMessage(e)
      log_info(paste0("ERREUR: ", message))
      write_status(state = "failed", progress = 100, message = message)
      payload <- list(success = FALSE, message = message, logs = job_logs)
      jsonlite::write_json(payload, results_file, auto_unbox = TRUE, pretty = TRUE, null = "null")
      quit(save = "no", status = 1)
    }
  )
  quit(save = "no", status = 0)
}

tryCatch(
  run_batch(),
  error = function(e) {
    log_info(paste0("ERREUR: ", conditionMessage(e)))
    write_status(state = "failed", progress = 100, message = conditionMessage(e))
    jsonlite::write_json(
      list(
        success = FALSE,
        output_dir = output_dir,
        message = conditionMessage(e),
        logs = job_logs
      ),
      results_file,
      auto_unbox = TRUE,
      pretty = TRUE,
      null = "null"
    )
    quit(status = 1)
  }
)
