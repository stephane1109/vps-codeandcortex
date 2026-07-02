#!/usr/bin/env Rscript

options(stringsAsFactors = FALSE)

suppressPackageStartupMessages({
  library(jsonlite)
  library(rainette)
  library(quanteda)
  library(wordcloud)
  library(RColorBrewer)
  library(dplyr)
  library(htmltools)
  library(igraph)
  library(Matrix)
})

log_info <- function(message) cat(sprintf("[info] %s\n", message))

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) return(right)
  left
}

script_arg <- grep("^--file=", commandArgs(), value = TRUE)
script_path <- if (length(script_arg)) {
  normalizePath(sub("^--file=", "", script_arg[[1]]), winslash = "/", mustWork = TRUE)
} else {
  normalizePath(sys.frames()[[1]]$ofile, winslash = "/", mustWork = TRUE)
}
project_root <- dirname(dirname(script_path))

source_project <- function(relative_path) {
  source(
    normalizePath(file.path(project_root, relative_path), winslash = "/", mustWork = TRUE),
    local = globalenv(),
    chdir = TRUE
  )
}

source_project("afc.R")
source_project("concordancier.R")
source_project("nettoyage.R")
source_project("R/utils_general.R")
source_project("R/utils_text.R")
source_project("R/chd_afc_pipeline.R")
source_project("R/nlp_language.R")
source_project("R/nlp_spacy.R")
source_project("R/afc_helpers.R")

ajouter_log_internal <- ajouter_log
ajouter_log <- function(rv, texte) {
  ajouter_log_internal(rv, texte)
  log_info(texte)
}

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 3) {
  stop("Usage: Rscript run_chdrainette.R <config.json> <input.txt> <output_dir>")
}

config_path <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
input_path <- normalizePath(args[[2]], winslash = "/", mustWork = TRUE)
output_dir <- normalizePath(args[[3]], winslash = "/", mustWork = FALSE)
dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)

config <- fromJSON(config_path, simplifyVector = TRUE)

config_value <- function(keys, default = NULL) {
  for (key in keys) {
    value <- config[[key]]
    if (!is.null(value) && length(value)) return(value)
  }
  default
}

config_int <- function(keys, default, minimum = NULL, maximum = NULL) {
  value <- suppressWarnings(as.integer(config_value(keys, default)))
  if (is.na(value)) value <- as.integer(default)
  if (!is.null(minimum)) value <- max(value, as.integer(minimum))
  if (!is.null(maximum)) value <- min(value, as.integer(maximum))
  value
}

config_num <- function(keys, default, minimum = NULL, maximum = NULL) {
  value <- suppressWarnings(as.numeric(config_value(keys, default)))
  if (is.na(value)) value <- as.numeric(default)
  if (!is.null(minimum)) value <- max(value, as.numeric(minimum))
  if (!is.null(maximum)) value <- min(value, as.numeric(maximum))
  value
}

config_bool <- function(keys, default = FALSE) {
  value <- config_value(keys, default)
  if (is.null(value) || !length(value)) return(isTRUE(default))
  if (is.logical(value)) return(isTRUE(value[[1]]))
  if (is.numeric(value)) return(!is.na(value[[1]]) && value[[1]] != 0)
  normalized <- tolower(trimws(as.character(value[[1]])))
  normalized %in% c("1", "true", "vrai", "yes", "oui", "on")
}

config_chr <- function(keys, default = "") {
  value <- config_value(keys, default)
  out <- trimws(as.character(value[[1]] %||% default))
  if (!nzchar(out)) out <- default
  out
}

config_chr_vec <- function(keys, default = character(0)) {
  value <- config_value(keys, default)
  out <- trimws(as.character(value))
  out[nzchar(out)]
}

parse_iramuteq_header <- function(header_line) {
  cleaned <- trimws(sub("^\\*\\*\\*\\*\\s*", "", header_line))
  if (!nzchar(cleaned)) return(list())
  tokens <- unlist(strsplit(cleaned, "\\s+", perl = TRUE), use.names = FALSE)
  tokens <- tokens[nzchar(tokens)]

  meta <- list()
  for (token in tokens) {
    if (!startsWith(token, "*")) next
    raw <- sub("^\\*+", "", token)
    raw <- trimws(raw)
    if (!nzchar(raw)) next
    parts <- strsplit(raw, "_", fixed = TRUE)[[1]]
    key <- parts[[1]] %||% ""
    key <- trimws(key)
    if (!nzchar(key)) next
    value <- if (length(parts) > 1) paste(parts[-1], collapse = "_") else "1"
    meta[[make.names(key, unique = TRUE)]] <- value
  }
  meta
}

if (!exists("import_corpus_iramuteq", mode = "function")) {
  import_corpus_iramuteq <- function(chemin_fichier) {
    lignes <- readLines(chemin_fichier, encoding = "UTF-8", warn = FALSE)
    if (!length(lignes)) stop("Corpus vide : aucun contenu lisible.")

    headers <- grepl("^\\*\\*\\*\\*", lignes)
    rows <- list()

    if (any(headers)) {
      starts <- which(headers)
      bounds <- c(starts, length(lignes) + 1L)
      for (index in seq_along(starts)) {
        start_line <- starts[[index]]
        next_start <- bounds[[index + 1L]] - 1L
        content <- if (start_line + 1L <= next_start) lignes[(start_line + 1L):next_start] else character(0)
        content <- trimws(content)
        content <- content[nzchar(content)]
        if (!length(content)) next

        meta <- parse_iramuteq_header(lignes[[start_line]])
        doc_id <- meta$id %||% meta$docid %||% meta$doc %||% paste0("doc_", index)
        row <- c(
          list(
            doc_id = as.character(doc_id),
            text = paste(content, collapse = " ")
          ),
          meta
        )
        rows[[length(rows) + 1L]] <- row
      }
    } else {
      cleaned <- trimws(lignes)
      cleaned <- cleaned[nzchar(cleaned)]
      for (index in seq_along(cleaned)) {
        rows[[length(rows) + 1L]] <- list(
          doc_id = paste0("doc_", index),
          text = cleaned[[index]]
        )
      }
    }

    if (!length(rows)) stop("Corpus vide : aucune unité de texte détectée.")

    df <- bind_rows(rows)
    df$doc_id <- make.unique(as.character(df$doc_id), sep = "_")
    quanteda::corpus(df, text_field = "text")
  }
}

if (!exists("split_segments", mode = "function")) {
  split_segments <- function(corpus_obj, segment_size = 40L) {
    docs <- as.character(corpus_obj)
    doc_names <- as.character(quanteda::docnames(corpus_obj))
    doc_vars <- quanteda::docvars(corpus_obj)
    rows <- list()

    for (index in seq_along(docs)) {
      tok_doc <- quanteda::tokens(
        docs[[index]],
        remove_punct = FALSE,
        remove_numbers = FALSE,
        remove_symbols = FALSE,
        remove_separators = TRUE
      )
      tokens_doc <- as.character(tok_doc[[1]])
      tokens_doc <- tokens_doc[nzchar(tokens_doc)]
      if (!length(tokens_doc)) next

      blocks <- split(seq_along(tokens_doc), ceiling(seq_along(tokens_doc) / max(1L, as.integer(segment_size))))
      meta <- if (nrow(doc_vars)) as.list(doc_vars[index, , drop = FALSE]) else list()
      meta$segment_source <- doc_names[[index]]

      for (block_index in seq_along(blocks)) {
        row <- c(
          list(
            doc_id = paste0(doc_names[[index]], "_seg", block_index),
            text = paste(tokens_doc[blocks[[block_index]]], collapse = " ")
          ),
          meta
        )
        rows[[length(rows) + 1L]] <- row
      }
    }

    if (!length(rows)) stop("Aucun segment n'a pu être créé.")
    quanteda::corpus(bind_rows(rows), text_field = "text")
  }
}

split_sentences_with_docvars <- function(corpus_obj) {
  docs <- as.character(corpus_obj)
  doc_names <- as.character(quanteda::docnames(corpus_obj))
  doc_vars <- quanteda::docvars(corpus_obj)
  rows <- list()

  for (index in seq_along(docs)) {
    sentences <- quanteda::tokenize_sentences(docs[[index]])[[1]]
    sentences <- trimws(sentences)
    sentences <- sentences[nzchar(sentences)]
    if (!length(sentences)) next
    meta <- if (nrow(doc_vars)) as.list(doc_vars[index, , drop = FALSE]) else list()
    meta$segment_source <- doc_names[[index]]

    for (sentence_index in seq_along(sentences)) {
      row <- c(
        list(
          doc_id = paste0(doc_names[[index]], "_phrase", sentence_index),
          text = sentences[[sentence_index]]
        ),
        meta
      )
      rows[[length(rows) + 1L]] <- row
    }
  }

  if (!length(rows)) stop("Aucune phrase n'a pu être extraite du corpus.")
  quanteda::corpus(bind_rows(rows), text_field = "text")
}

formater_df_csv_6_decimales <- function(df) {
  if (is.null(df)) return(df)
  df_out <- df
  for (name in names(df_out)) {
    column <- df_out[[name]]
    if (is.numeric(column)) {
      df_out[[name]] <- ifelse(
        is.na(column),
        NA_character_,
        formatC(column, format = "f", digits = 6)
      )
    }
  }
  df_out
}

ecrire_csv_6_decimales <- function(df, chemin, row.names = FALSE) {
  write.csv(formater_df_csv_6_decimales(df), chemin, row.names = row.names, fileEncoding = "UTF-8")
}

safe_png <- function(file_path, expr) {
  grDevices::png(file_path, width = 1800, height = 1400, res = 180)
  on.exit(try(grDevices::dev.off(), silent = TRUE), add = TRUE)
  force(expr)
  invisible(file_path)
}

rv <- new.env(parent = emptyenv())
rv$logs <- ""
rv$statut <- "Initialisation"
rv$progression <- 0
rv$export_dir <- output_dir
rv$spacy_tokens_df <- NULL
rv$textes_indexation <- NULL
rv$ner_df <- NULL
rv$afc_obj <- NULL
rv$afc_erreur <- NULL
rv$afc_vars_obj <- NULL
rv$afc_vars_erreur <- NULL
rv$res <- NULL
rv$res_chd <- NULL
rv$dfm <- NULL
rv$dfm_chd <- NULL
rv$explor_assets <- NULL

avancer <- function(progress, detail) {
  rv$progression <- as.integer(round(progress * 100))
  rv$statut <- detail
  ajouter_log(rv, detail)
}

mode_decoupage <- config_chr(c("mode_decoupage"), "segment_size")
segment_size <- config_int(c("segment_size"), 40L, minimum = 5L)
k_demande <- config_int(c("k"), 3L, minimum = 2L)
min_segment_size <- config_int(c("min_segment_size"), 10L, minimum = 1L)
min_split_members <- config_int(c("min_split_members", "min_split_segments"), 10L, minimum = 1L)
min_docfreq <- config_int(c("min_docfreq"), 3L, minimum = 1L)
max_p <- config_num(c("max_p"), 0.05, minimum = 0, maximum = 1)
spacy_langue <- config_chr(c("spacy_langue"), "fr")
type_classification <- config_chr(c("type_classification"), "simple")
min_segment_size2 <- config_int(c("min_segment_size2"), 15L, minimum = 1L)
max_k_double <- config_int(c("max_k_double"), 8L, minimum = 2L)
nettoyage_caracteres <- config_bool(c("nettoyage_caracteres"), FALSE)
supprimer_ponctuation <- config_bool(c("supprimer_ponctuation"), FALSE)
supprimer_chiffres <- config_bool(c("supprimer_chiffres"), FALSE)
supprimer_apostrophes <- config_bool(c("supprimer_apostrophes"), FALSE)
forcer_minuscules_avant <- config_bool(c("forcer_minuscules_avant"), FALSE)
retirer_stopwords <- config_bool(c("retirer_stopwords"), FALSE)
filtrage_morpho <- config_bool(c("filtrage_morpho", "lemmatisation"), FALSE)
spacy_utiliser_lemmes <- config_bool(c("spacy_utiliser_lemmes"), FALSE)
activer_ner <- config_bool(c("activer_ner"), FALSE)
afc_reduire_chevauchement <- config_bool(c("afc_reduire_chevauchement"), FALSE)
afc_taille_mots <- config_chr(c("afc_taille_mots"), "frequency")
afc_top_termes <- config_int(c("afc_top_termes"), 120L, minimum = 20L)
afc_top_modalites <- config_int(c("afc_top_modalites"), 120L, minimum = 20L)
top_n <- config_int(c("top_n"), 20L, minimum = 5L)
window_cooc <- config_int(c("window_cooc"), 5L, minimum = 1L)
top_feat <- config_int(c("top_feat"), 20L, minimum = 5L)
pos_spacy_a_conserver <- config_chr_vec(c("pos_spacy_a_conserver", "upos_a_conserver"), c("NOUN", "VERB"))
if (!length(pos_spacy_a_conserver)) pos_spacy_a_conserver <- c("NOUN", "VERB")

tryCatch({
  avancer(0.04, "Import du corpus")
  corpus_brut <- import_corpus_iramuteq(input_path)
  ajouter_log(rv, paste0("Nombre de documents importés : ", quanteda::ndoc(corpus_brut)))

  avancer(0.10, "Segmentation")
  corpus_segments <- if (identical(mode_decoupage, "ponctuation")) {
    split_sentences_with_docvars(corpus_brut)
  } else {
    split_segments(corpus_brut, segment_size = segment_size)
  }

  if (quanteda::ndoc(corpus_segments) < 2) {
    stop("Le corpus segmenté contient moins de 2 segments : analyse impossible.")
  }
  ajouter_log(rv, paste0("Nombre de segments après découpage : ", quanteda::ndoc(corpus_segments)))

  ids_corpus <- quanteda::docnames(corpus_segments)
  textes_orig <- as.character(corpus_segments)

  avancer(0.16, "Préparation du texte")
  textes_chd <- appliquer_nettoyage_et_minuscules(
    textes = textes_orig,
    activer_nettoyage = nettoyage_caracteres,
    forcer_minuscules = forcer_minuscules_avant,
    supprimer_chiffres = supprimer_chiffres,
    supprimer_apostrophes = supprimer_apostrophes
  )
  names(textes_chd) <- ids_corpus

  verifier_coherence_dictionnaire_langue(textes_chd, spacy_langue, rv = rv)

  avancer(0.22, "Prétraitement et DFM")
  config_spacy <- configurer_langue_spacy(spacy_langue)
  utiliser_pipeline_spacy <- filtrage_morpho || spacy_utiliser_lemmes

  if (!utiliser_pipeline_spacy) {
    tok_base <- quanteda::tokens(
      textes_chd,
      remove_punct = supprimer_ponctuation,
      remove_numbers = supprimer_chiffres
    )
    res_dfm <- construire_dfm_avec_fallback_stopwords(
      tok_base = tok_base,
      min_docfreq = min_docfreq,
      retirer_stopwords = retirer_stopwords,
      langue_spacy = spacy_langue,
      rv = rv,
      libelle = "Standard"
    )
    tok <- res_dfm$tok
    dfm_obj <- res_dfm$dfm
  } else {
    avancer(0.30, paste0("spaCy : ", config_spacy$modele))
    sp <- executer_spacy_filtrage(
      ids = ids_corpus,
      textes = unname(textes_chd),
      pos_a_conserver = if (filtrage_morpho) pos_spacy_a_conserver else character(0),
      utiliser_lemmes = spacy_utiliser_lemmes,
      lower_input = forcer_minuscules_avant,
      modele_spacy = config_spacy$modele,
      rv = rv
    )
    textes_spacy <- sp$textes
    names(textes_spacy) <- ids_corpus
    rv$spacy_tokens_df <- sp$tokens_df

    tok_base <- quanteda::tokens(
      textes_spacy,
      remove_punct = supprimer_ponctuation,
      remove_numbers = supprimer_chiffres
    )
    res_dfm <- construire_dfm_avec_fallback_stopwords(
      tok_base = tok_base,
      min_docfreq = min_docfreq,
      retirer_stopwords = retirer_stopwords,
      langue_spacy = spacy_langue,
      rv = rv,
      libelle = "spaCy"
    )
    tok <- res_dfm$tok
    dfm_obj <- res_dfm$dfm
  }

  filtered_corpus_all <- corpus_segments[quanteda::docnames(dfm_obj)]
  tok <- tok[quanteda::docnames(dfm_obj)]
  dfm_obj <- assurer_docvars_dfm_minimal(dfm_obj, filtered_corpus_all)

  tmp <- supprimer_docs_vides_dfm(dfm_obj, filtered_corpus_all, tok, rv)
  dfm_obj <- tmp$dfm
  filtered_corpus_all <- tmp$corpus
  tok <- tmp$tok

  verifier_dfm_avant_rainette(dfm_obj, list())
  rv$textes_indexation <- vapply(as.list(tok), function(x) paste(x, collapse = " "), FUN.VALUE = character(1))
  names(rv$textes_indexation) <- quanteda::docnames(dfm_obj)

  avancer(0.46, "Classification Rainette")
  k_effectif <- calculer_k_effectif(dfm_obj, k_demande, min_split_members, rv)
  groupes_all <- NULL
  res_final <- NULL
  plot_res <- NULL
  plot_dtm <- NULL
  max_k_plot <- NULL
  max_k_cutree <- NULL

  if (identical(type_classification, "double")) {
    max_k_double <- max(max_k_double, k_effectif)
    res1 <- rainette(
      dfm_obj,
      k = k_effectif,
      min_segment_size = min_segment_size,
      min_split_members = min_split_members,
      doc_id = "segment_source"
    )
    if (is.null(res1$group) || !length(res1$group)) {
      stop("Classification 1 (rainette) impossible.")
    }

    res2 <- rainette(
      dfm_obj,
      k = k_effectif,
      min_segment_size = min_segment_size2,
      min_split_members = min_split_members,
      doc_id = "segment_source"
    )
    if (is.null(res2$group) || !length(res2$group)) {
      stop("Classification 2 (rainette) impossible.")
    }

    res_d <- rainette2(res1, res2, max_k = max_k_double)
    groupes_all <- rainette::cutree(res_d, k = k_effectif)
    res_final <- res_d
    plot_res <- res1
    plot_dtm <- dfm_obj
    rv$res_chd <- res1
    rv$dfm_chd <- dfm_obj
    max_k_plot <- max(res1$group, na.rm = TRUE)
    max_k_cutree <- max_k_double
  } else {
    res <- rainette(
      dfm_obj,
      k = k_effectif,
      min_segment_size = min_segment_size,
      min_split_members = min_split_members,
      doc_id = "segment_source"
    )
    if (is.null(res$group) || !length(res$group)) {
      stop("Rainette n'a pas pu calculer de clusters. Réduis les filtrages ou ajuste k.")
    }
    groupes_all <- res$group
    res_final <- res
    plot_res <- res
    plot_dtm <- dfm_obj
    rv$res_chd <- res
    rv$dfm_chd <- dfm_obj
    max_k_plot <- max(res$group, na.rm = TRUE)
    max_k_cutree <- max_k_plot
  }

  quanteda::docvars(filtered_corpus_all)$Classes <- as.integer(groupes_all)
  idx_ok <- !is.na(quanteda::docvars(filtered_corpus_all)$Classes)
  filtered_corpus_ok <- filtered_corpus_all[idx_ok]
  dfm_ok <- dfm_obj[idx_ok, ]
  tok_ok <- tok[idx_ok]

  if (quanteda::ndoc(dfm_ok) < 2) stop("Après classification, il reste moins de 2 segments classés.")
  if (quanteda::nfeat(dfm_ok) < 2) stop("Après classification, il reste moins de 2 termes utiles.")

  rv$res <- res_final
  rv$dfm <- dfm_ok
  rv$filtered_corpus <- filtered_corpus_ok

  avancer(0.56, "NER (si activé)")
  if (activer_ner) {
    ids_ner <- quanteda::docnames(filtered_corpus_ok)
    textes_ner <- as.character(filtered_corpus_ok)
    df_ent <- executer_spacy_ner(
      ids = ids_ner,
      textes = textes_ner,
      modele_spacy = config_spacy$modele,
      rv = rv
    )
    classes_vec <- as.integer(quanteda::docvars(filtered_corpus_ok)$Classes)
    names(classes_vec) <- ids_ner
    df_ent$Classe <- classes_vec[df_ent$doc_id]
    df_ent <- df_ent[!is.na(df_ent$Classe), , drop = FALSE]
    rv$ner_df <- df_ent
  }

  avancer(0.62, "Statistiques CHD")
  segments_vec <- as.character(filtered_corpus_ok)
  names(segments_vec) <- quanteda::docnames(filtered_corpus_ok)
  segments_by_class <- split(segments_vec, quanteda::docvars(filtered_corpus_ok)$Classes)

  segments_file <- file.path(output_dir, "segments_par_classe.txt")
  writeLines(
    unlist(lapply(names(segments_by_class), function(cl) c(paste0("Classe ", cl, ":"), unname(segments_by_class[[cl]]), ""))),
    segments_file,
    useBytes = TRUE
  )

  res_stats_list <- rainette_stats(
    dtm = dfm_ok,
    groups = quanteda::docvars(filtered_corpus_ok)$Classes,
    measure = c("chi2", "lr", "frequency", "docprop"),
    n_terms = 9999,
    show_negative = TRUE,
    max_p = max_p
  )

  res_stats_df <- bind_rows(res_stats_list, .id = "ClusterID") %>%
    rename(Terme = feature, Classe = ClusterID) %>%
    mutate(
      Classe = as.numeric(Classe),
      p_value_filter = ifelse(p <= max_p, paste0("≤ ", max_p), paste0("> ", max_p)),
      Classe_max = paste0("Classe ", Classe)
    ) %>%
    arrange(Classe, desc(chi2))

  detail_df <- construire_segments_exemples_afc(
    termes_stats = res_stats_df,
    dfm_obj = dfm_ok,
    corpus_obj = filtered_corpus_ok
  ) %>%
    select(any_of(c("Classe", "Terme", "chi2", "lr", "frequency", "docprop", "p", "p_value_filter", "Segment_texte", "Classe_max")))

  stats_file <- file.path(output_dir, "stats_par_classe.csv")
  detail_file <- file.path(output_dir, "mots_chi2_frequence_segments.csv")
  detail_segments_file <- file.path(output_dir, "mots_chi2_segments.csv")
  ecrire_csv_6_decimales(res_stats_df, stats_file, row.names = FALSE)
  ecrire_csv_6_decimales(detail_df, detail_file, row.names = FALSE)
  ecrire_csv_6_decimales(detail_df[, intersect(c("Classe", "Terme", "Segment_texte"), names(detail_df)), drop = FALSE], detail_segments_file, row.names = FALSE)

  top_terms_lookup <- split(
    detail_df %>%
      filter(!is.na(Classe), !is.na(Terme), nzchar(Terme)) %>%
      group_by(Classe) %>%
      arrange(desc(chi2), .by_group = TRUE) %>%
      slice_head(n = top_n) %>%
      summarise(termes = list(unique(Terme)), .groups = "drop") %>%
      pull(termes),
    detail_df %>%
      filter(!is.na(Classe), !is.na(Terme), nzchar(Terme)) %>%
      group_by(Classe) %>%
      arrange(desc(chi2), .by_group = TRUE) %>%
      slice_head(n = top_n) %>%
      summarise(termes = list(unique(Terme)), .groups = "drop") %>%
      pull(Classe)
  )

  classes_df <- as.data.frame(table(Classe = quanteda::docvars(filtered_corpus_ok)$Classes), stringsAsFactors = FALSE)
  classes_df$Classe <- as.character(classes_df$Classe)
  classes_df$Segments <- as.integer(classes_df$Freq)
  classes_df$Pourcentage <- round(100 * classes_df$Segments / sum(classes_df$Segments), 2)
  classes_df$Top_termes <- vapply(
    classes_df$Classe,
    function(cl) paste(top_terms_lookup[[cl]] %||% character(0), collapse = ", "),
    character(1)
  )
  classes_df$Freq <- NULL
  resume_classes_path <- file.path(output_dir, "resume_classes.csv")
  ecrire_csv_6_decimales(classes_df, resume_classes_path, row.names = FALSE)

  safe_png(file.path(output_dir, "class_distribution.png"), {
    barplot(
      height = classes_df$Segments,
      names.arg = classes_df$Classe,
      col = "#cf6f2d",
      main = "Répartition des segments par classe",
      xlab = "Classe",
      ylab = "Nombre de segments"
    )
  })

  avancer(0.72, "AFC")
  rv$afc_dir <- file.path(output_dir, "afc")
  dir.create(rv$afc_dir, showWarnings = FALSE, recursive = TRUE)

  termes_signif <- unique(subset(res_stats_df, p <= max_p)$Terme)
  termes_signif <- termes_signif[!is.na(termes_signif) & nzchar(termes_signif)]
  if (length(termes_signif) < 2) termes_signif <- NULL

  tryCatch({
    obj <- executer_afc_classes(
      dfm_obj = dfm_ok,
      groupes = quanteda::docvars(filtered_corpus_ok)$Classes,
      termes_cibles = termes_signif,
      max_termes = 400,
      seuil_p = max_p,
      rv = rv
    )
    obj$termes_stats <- construire_segments_exemples_afc(
      termes_stats = obj$termes_stats,
      dfm_obj = dfm_ok,
      corpus_obj = filtered_corpus_ok
    )
    rv$afc_obj <- obj
  }, error = function(error) {
    rv$afc_erreur <- paste0("AFC classes × termes : ", conditionMessage(error))
    ajouter_log(rv, rv$afc_erreur)
  })

  tryCatch({
    rv$afc_vars_obj <- executer_afc_variables_etoilees(
      corpus_aligne = filtered_corpus_ok,
      groupes = quanteda::docvars(filtered_corpus_ok)$Classes,
      max_modalites = 400,
      seuil_p = max_p,
      rv = rv
    )
  }, error = function(error) {
    rv$afc_vars_erreur <- paste0("AFC variables étoilées : ", conditionMessage(error))
    ajouter_log(rv, rv$afc_vars_erreur)
  })

  if (!is.null(rv$afc_obj) && !is.null(rv$afc_obj$ca)) {
    afc_classes_png <- file.path(rv$afc_dir, "afc_classes.png")
    afc_termes_png <- file.path(rv$afc_dir, "afc_termes.png")

    safe_png(afc_classes_png, tracer_afc_classes_seules(rv$afc_obj, axes = c(1, 2), cex_labels = 1.05))
    safe_png(
      afc_termes_png,
      tracer_afc_classes_termes(
        rv$afc_obj,
        axes = c(1, 2),
        top_termes = afc_top_termes,
        taille_sel = if (afc_taille_mots %in% c("frequency", "chi2")) afc_taille_mots else "frequency",
        activer_repel = afc_reduire_chevauchement
      )
    )

    ecrire_csv_6_decimales(rv$afc_obj$table, file.path(rv$afc_dir, "table_classes_termes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(rv$afc_obj$rowcoord, file.path(rv$afc_dir, "coords_classes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(rv$afc_obj$colcoord, file.path(rv$afc_dir, "coords_termes.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(rv$afc_obj$termes_stats, file.path(rv$afc_dir, "stats_termes.csv"), row.names = FALSE)
    if (!is.null(rv$afc_obj$ca$eig)) {
      ecrire_csv_6_decimales(as.data.frame(rv$afc_obj$ca$eig), file.path(rv$afc_dir, "valeurs_propres.csv"), row.names = TRUE)
    }
  }

  if (!is.null(rv$afc_vars_obj) && !is.null(rv$afc_vars_obj$ca)) {
    afc_vars_png <- file.path(rv$afc_dir, "afc_variables_etoilees.png")
    safe_png(
      afc_vars_png,
      tracer_afc_variables_etoilees(
        rv$afc_vars_obj,
        axes = c(1, 2),
        top_modalites = afc_top_modalites,
        activer_repel = afc_reduire_chevauchement
      )
    )
    ecrire_csv_6_decimales(rv$afc_vars_obj$table, file.path(rv$afc_dir, "table_classes_variables.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(rv$afc_vars_obj$rowcoord, file.path(rv$afc_dir, "coords_classes_vars.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(rv$afc_vars_obj$colcoord, file.path(rv$afc_dir, "coords_modalites.csv"), row.names = TRUE)
    ecrire_csv_6_decimales(rv$afc_vars_obj$modalites_stats, file.path(rv$afc_dir, "stats_modalites.csv"), row.names = FALSE)
    if (!is.null(rv$afc_vars_obj$ca$eig)) {
      ecrire_csv_6_decimales(as.data.frame(rv$afc_vars_obj$ca$eig), file.path(rv$afc_dir, "valeurs_propres_vars.csv"), row.names = TRUE)
    }
  }

  avancer(0.80, "Wordclouds et cooccurrences")
  wordcloud_dir <- file.path(output_dir, "wordclouds")
  cooc_dir <- file.path(output_dir, "cooccurrences")
  dir.create(wordcloud_dir, showWarnings = FALSE, recursive = TRUE)
  dir.create(cooc_dir, showWarnings = FALSE, recursive = TRUE)

  classes_uniques <- sort(unique(as.integer(quanteda::docvars(filtered_corpus_ok)$Classes)))
  for (cl in classes_uniques) {
    df_stats_cl <- subset(res_stats_df, Classe == cl & p <= max_p)
    if (nrow(df_stats_cl) > 0) {
      df_stats_cl <- df_stats_cl[order(-df_stats_cl$chi2), , drop = FALSE]
      df_stats_cl <- head(df_stats_cl, top_n)
      safe_png(file.path(wordcloud_dir, paste0("cluster_", cl, "_wordcloud.png")), {
        suppressWarnings(wordcloud(
          words = df_stats_cl$Terme,
          freq = df_stats_cl$chi2,
          scale = c(10, 0.5),
          min.freq = 0,
          max.words = nrow(df_stats_cl),
          colors = brewer.pal(8, "Dark2")
        ))
      })
    }

    tok_cl <- tok_ok[quanteda::docvars(filtered_corpus_ok)$Classes == cl]
    if (length(tok_cl) > 0) {
      try({
        fcm_cl <- fcm(tok_cl, context = "window", window = window_cooc, tri = FALSE)
        term_freq <- sort(colSums(fcm_cl), decreasing = TRUE)
        top_feat_effectif <- min(top_feat, top_n, length(term_freq))
        if (top_feat_effectif >= 2) {
          feat_sel <- names(term_freq)[seq_len(top_feat_effectif)]
          fcm_sel <- fcm_select(fcm_cl, feat_sel, selection = "keep")
          adj <- as.matrix(fcm_sel)
          graph <- graph_from_adjacency_matrix(adj, mode = "undirected", weighted = TRUE, diag = FALSE)
          if (length(V(graph)) > 0) {
            palette_colors <- brewer.pal(min(8, max(3, length(V(graph)))), "Set3")[seq_along(V(graph))]
            V(graph)$color <- palette_colors
            safe_png(file.path(cooc_dir, paste0("cluster_", cl, "_fcm_network.png")), {
              plot(
                graph,
                layout = layout_with_fr(graph),
                main = paste("Cooccurrences - Classe", cl),
                vertex.size = 16,
                vertex.color = V(graph)$color,
                vertex.label = V(graph)$name,
                vertex.label.cex = 1,
                edge.width = E(graph)$weight / 2,
                edge.color = "gray80"
              )
            })
          }
        }
      }, silent = TRUE)
    }
  }

  if (!is.null(rv$ner_df) && nrow(rv$ner_df) > 0) {
    avancer(0.86, "Exports NER")
    ner_dir <- file.path(output_dir, "ner")
    dir.create(ner_dir, showWarnings = FALSE, recursive = TRUE)
    ner_resume <- rv$ner_df %>%
      count(Classe, ent_label, sort = TRUE, name = "Occurrences")
    ecrire_csv_6_decimales(rv$ner_df, file.path(ner_dir, "ner_details.csv"), row.names = FALSE)
    ecrire_csv_6_decimales(ner_resume, file.path(ner_dir, "ner_resume.csv"), row.names = FALSE)

    entites_globales <- rv$ner_df %>%
      count(ent_text, sort = TRUE, name = "Occurrences")

    safe_png(file.path(ner_dir, "ner_wordcloud_global.png"), {
      suppressWarnings(wordcloud(
        words = entites_globales$ent_text,
        freq = entites_globales$Occurrences,
        scale = c(8, 0.7),
        min.freq = 1,
        max.words = min(120, nrow(entites_globales)),
        colors = brewer.pal(8, "Dark2")
      ))
    })

    for (cl in sort(unique(rv$ner_df$Classe))) {
      entites_cl <- rv$ner_df %>%
        filter(Classe == cl) %>%
        count(ent_text, sort = TRUE, name = "Occurrences")
      if (nrow(entites_cl) == 0) next
      safe_png(file.path(ner_dir, paste0("ner_wordcloud_classe_", cl, ".png")), {
        suppressWarnings(wordcloud(
          words = entites_cl$ent_text,
          freq = entites_cl$Occurrences,
          scale = c(8, 0.7),
          min.freq = 1,
          max.words = min(100, nrow(entites_cl)),
          colors = brewer.pal(8, "Set2")
        ))
      })
    }
  }

  avancer(0.90, "Concordancier HTML")
  html_file <- file.path(output_dir, "segments_par_classe.html")
  textes_index_ok <- rv$textes_indexation[quanteda::docnames(dfm_ok)]
  names(textes_index_ok) <- quanteda::docnames(dfm_ok)

  ok_chd_png <- generer_chd_explor_si_absente(rv)
  if (isTRUE(ok_chd_png) && file.exists(file.path(output_dir, "explor", "chd.png"))) {
    file.copy(file.path(output_dir, "explor", "chd.png"), file.path(output_dir, "rainette_plot.png"), overwrite = TRUE)
  }

  wordcloud_files <- list.files(wordcloud_dir, pattern = "\\.png$", full.names = FALSE)
  cooc_files <- list.files(cooc_dir, pattern = "\\.png$", full.names = FALSE)
  rv$explor_assets <- list(
    chd = if (file.exists(file.path(output_dir, "explor", "chd.png"))) file.path("explor", "chd.png") else NULL,
    chd_html = generer_chd_html_explor(rv, if (file.exists(file.path(output_dir, "explor", "chd.png"))) file.path("explor", "chd.png") else NULL),
    wordclouds = data.frame(
      classe = gsub("^cluster_([0-9]+)_wordcloud\\.png$", "\\1", wordcloud_files),
      src = file.path("wordclouds", wordcloud_files),
      stringsAsFactors = FALSE
    ),
    coocs = data.frame(
      classe = gsub("^cluster_([0-9]+)_fcm_network\\.png$", "\\1", cooc_files),
      src = file.path("cooccurrences", cooc_files),
      stringsAsFactors = FALSE
    )
  )

  generer_concordancier_html(
    chemin_sortie = html_file,
    segments_by_class = segments_by_class,
    res_stats_df = res_stats_df,
    max_p = max_p,
    textes_indexation = textes_index_ok,
    spacy_tokens_df = rv$spacy_tokens_df,
    explor_assets = rv$explor_assets,
    rv = rv
  )

  avancer(0.96, "Bundle d'exploration")
  metadata <- list(
    input_file = basename(input_path),
    settings = as.list(config),
    n_documents_imported = quanteda::ndoc(corpus_brut),
    n_segments_created = quanteda::ndoc(corpus_segments),
    n_segments_analyzed = quanteda::ndoc(filtered_corpus_ok),
    n_features = quanteda::nfeat(dfm_ok),
    n_classes = length(unique(quanteda::docvars(filtered_corpus_ok)$Classes)),
    classification_type = type_classification,
    max_k = max_k_cutree,
    max_k_plot = max_k_plot,
    has_afc = !is.null(rv$afc_obj),
    has_afc_variables = !is.null(rv$afc_vars_obj),
    has_ner = !is.null(rv$ner_df) && nrow(rv$ner_df) > 0,
    afc_error = rv$afc_erreur,
    afc_variables_error = rv$afc_vars_erreur,
    ner_entities = if (!is.null(rv$ner_df)) nrow(rv$ner_df) else 0L
  )

  bundle_path <- file.path(output_dir, "analysis_bundle.rds")
  analysis_bundle <- list(
    res = res_final,
    plot_res = plot_res,
    cutree_res = res_final,
    dtm = dfm_ok,
    plot_dtm = plot_dtm,
    corpus_src = filtered_corpus_all,
    groups_current = as.integer(quanteda::docvars(filtered_corpus_all)$Classes),
    metadata = metadata,
    summary = classes_df,
    keyness = res_stats_df,
    max_k = max_k_cutree,
    max_k_plot = max_k_plot,
    current_k = length(unique(quanteda::docvars(filtered_corpus_ok)$Classes))
  )
  saveRDS(analysis_bundle, bundle_path)

  metadata$bundle_file <- basename(bundle_path)
  metadata$output_files <- list.files(output_dir, recursive = TRUE)
  metadata$classes_distribution <- split(classes_df, seq_len(nrow(classes_df)))
  write_json(metadata, path = file.path(output_dir, "metadata.json"), auto_unbox = TRUE, pretty = TRUE)

  avancer(1.00, "Analyse CHD Rainette terminée")
}, error = function(error) {
  stop(conditionMessage(error))
})
