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
})

log_info <- function(message) cat(sprintf("[info] %s\n", message))

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) return(right)
  left
}

script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)[1] %||% ""
script_path <- if (nzchar(script_arg)) sub("^--file=", "", script_arg) else ""
app_root <- if (nzchar(script_path)) {
  normalizePath(file.path(dirname(script_path), ".."), winslash = "/", mustWork = TRUE)
} else {
  normalizePath(getwd(), winslash = "/", mustWork = TRUE)
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
mode_decoupage <- if (!is.null(config$mode_decoupage)) as.character(config$mode_decoupage) else "segment_size"
segment_size <- if (!is.null(config$segment_size)) as.integer(config$segment_size) else 40L
k <- if (!is.null(config$k)) as.integer(config$k) else 6L
min_split_segments <- if (!is.null(config$min_split_segments)) as.integer(config$min_split_segments) else 12L
min_docfreq <- if (!is.null(config$min_docfreq)) as.integer(config$min_docfreq) else 1L
top_n <- if (!is.null(config$top_n)) as.integer(config$top_n) else 20L
lemmatisation <- isTRUE(config$lemmatisation) || isTRUE(config$spacy_utiliser_lemmes)
upos_a_conserver <- if (!is.null(config$upos_a_conserver)) {
  as.character(config$upos_a_conserver)
} else if (!is.null(config$pos_spacy_a_conserver)) {
  as.character(config$pos_spacy_a_conserver)
} else {
  c("NOUN", "ADJ")
}
mode_nettoyage_lexical <- as.character(config$mode_nettoyage_lexical %||% "stopwords_quanteda")
if (!mode_nettoyage_lexical %in% c("stopwords_quanteda", "lexique_iramuteq", "aucun")) {
  mode_nettoyage_lexical <- "stopwords_quanteda"
}
lexique_utiliser_lemmes <- isTRUE(config$lexique_utiliser_lemmes %||% TRUE)
pos_lexique_a_conserver <- unique(toupper(trimws(as.character(unlist(config$pos_lexique_a_conserver %||% c("NOM", "VER", "ADJ"), use.names = FALSE)))))
pos_lexique_a_conserver <- pos_lexique_a_conserver[nzchar(pos_lexique_a_conserver)]
if (!length(pos_lexique_a_conserver)) pos_lexique_a_conserver <- c("NOM", "VER", "ADJ")
morpho_conserver_hors_lexique <- isTRUE(config$morpho_conserver_hors_lexique %||% TRUE)
morpho_exclure_etre_verbe <- isTRUE(config$morpho_exclure_etre_verbe)
config$mode_nettoyage_lexical <- mode_nettoyage_lexical
config$lexique_utiliser_lemmes <- lexique_utiliser_lemmes
config$pos_lexique_a_conserver <- pos_lexique_a_conserver
config$morpho_conserver_hors_lexique <- morpho_conserver_hors_lexique
config$morpho_exclure_etre_verbe <- morpho_exclure_etre_verbe

if (!exists("import_corpus_iramuteq", mode = "function")) {
  import_corpus_iramuteq <- function(chemin_fichier) {
    lignes <- readLines(chemin_fichier, encoding = "UTF-8", warn = FALSE)
    if (length(lignes) == 0) stop("Corpus vide : aucun contenu lisible.")

    headers <- grepl("^\\*\\*\\*\\*", lignes)
    textes <- character(0)
    ids <- character(0)

    if (any(headers)) {
      idx <- which(headers)
      bornes <- c(idx, length(lignes) + 1L)
      for (i in seq_along(idx)) {
        debut <- idx[[i]] + 1L
        fin <- bornes[[i + 1L]] - 1L
        contenu <- if (debut <= fin) lignes[debut:fin] else character(0)
        contenu <- trimws(contenu)
        contenu <- contenu[nzchar(contenu)]
        if (!length(contenu)) next
        textes <- c(textes, paste(contenu, collapse = " "))
        ids <- c(ids, paste0("doc_", i))
      }
    } else {
      lignes2 <- trimws(lignes)
      lignes2 <- lignes2[nzchar(lignes2)]
      textes <- lignes2
      ids <- paste0("doc_", seq_along(textes))
    }

    if (!length(textes)) stop("Corpus vide : aucune unité de texte détectée.")

    base_df <- data.frame(doc_id = ids, text = textes, stringsAsFactors = FALSE)
    quanteda::corpus(base_df, text_field = "text")
  }
}

split_segments_local <- function(corpus_obj, segment_size = 40L) {
  docs <- as.character(corpus_obj)
  dn <- as.character(quanteda::docnames(corpus_obj))
  out_text <- character(0)
  out_id <- character(0)

  for (i in seq_along(docs)) {
    tok_doc <- quanteda::tokens(
      docs[[i]],
      remove_punct = FALSE,
      remove_numbers = FALSE,
      remove_symbols = FALSE,
      remove_separators = TRUE
    )
    tok <- as.character(tok_doc[[1]])
    tok <- tok[nzchar(tok)]
    if (!length(tok)) next
    blocs <- split(seq_along(tok), ceiling(seq_along(tok) / max(1L, segment_size)))
    for (j in seq_along(blocs)) {
      out_text <- c(out_text, paste(tok[blocs[[j]]], collapse = " "))
      out_id <- c(out_id, paste0(dn[[i]], "_seg", j))
    }
  }

  if (!length(out_text)) stop("Aucun segment n'a pu être créé.")
  quanteda::corpus(data.frame(doc_id = out_id, text = out_text, stringsAsFactors = FALSE), text_field = "text")
}

ensure_udpipe_model <- function() {
  if (!requireNamespace("udpipe", quietly = TRUE)) {
    stop("Le package R 'udpipe' n'est pas installé alors que la lemmatisation est activée.")
  }

  cache_dir <- Sys.getenv("CHDRAINETTE_CACHE_DIR", unset = file.path(output_dir, "cache"))
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)

  files <- list.files(cache_dir, pattern = "\\.udpipe$", full.names = TRUE)
  if (length(files)) return(files[[1]])

  log_info("Téléchargement du modèle UDPipe français...")
  dl <- udpipe::udpipe_download_model(language = "french", model_dir = cache_dir, overwrite = FALSE)
  if (!length(dl$file_model) || !file.exists(dl$file_model)) {
    stop("Impossible de télécharger le modèle UDPipe français.")
  }
  dl$file_model
}

safe_wordcloud <- function(words, freq, file_path, colors) {
  if (!length(words) || !length(freq) || max(freq, na.rm = TRUE) <= 0) return(FALSE)
  png(file_path, width = 800, height = 600)
  wordcloud(
    words = words,
    freq = as.numeric(freq),
    scale = c(10, 0.5),
    max.words = length(words),
    colors = colors
  )
  dev.off()
  TRUE
}

charger_lexique_fr_iramuteq <- function(path = file.path(app_root, "dictionnaires", "lexique_fr.csv")) {
  if (!file.exists(path)) {
    stop(paste0("Fichier lexique_fr.csv introuvable : ", path))
  }

  lexique <- utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8")
  colonnes_requises <- c("c_mot", "c_lemme", "c_morpho")
  if (!all(colonnes_requises %in% names(lexique))) {
    stop("Le fichier lexique_fr.csv doit contenir les colonnes c_mot, c_lemme et c_morpho.")
  }

  lexique$c_mot <- tolower(trimws(as.character(lexique$c_mot)))
  lexique$c_lemme <- tolower(trimws(as.character(lexique$c_lemme)))
  lexique$c_morpho <- trimws(as.character(lexique$c_morpho))
  lexique <- lexique[
    nzchar(lexique$c_mot) & nzchar(lexique$c_lemme),
    c("c_mot", "c_lemme", "c_morpho"),
    drop = FALSE
  ]
  lexique <- lexique[!duplicated(lexique$c_mot), , drop = FALSE]
  attr(lexique, "source_file") <- path
  lexique
}

lemmatiser_tokens_lexique_iramuteq <- function(tok, lexique_fr_df) {
  vocabulaire <- quanteda::featnames(quanteda::dfm(tok))
  idx <- match(vocabulaire, lexique_fr_df$c_mot)
  a_remplacer <- !is.na(idx)
  if (!any(a_remplacer)) {
    log_info("Lemmatisation lexique_fr active, mais aucune forme du vocabulaire n'a trouvé de lemme.")
    return(tok)
  }

  motifs <- vocabulaire[a_remplacer]
  remplacements <- lexique_fr_df$c_lemme[idx[a_remplacer]]
  tok <- quanteda::tokens_replace(
    tok,
    pattern = motifs,
    replacement = remplacements,
    valuetype = "fixed",
    case_insensitive = FALSE
  )
  log_info(sprintf("Lemmatisation lexique_fr appliquée sur %s forme(s) du vocabulaire.", length(motifs)))
  tok
}

filtrer_dfm_lexique_iramuteq <- function(dfm_obj,
                                         lexique_fr_df,
                                         categories = c("NOM", "VER", "ADJ"),
                                         conserver_hors_lexique = TRUE,
                                         exclure_etre_verbe = FALSE) {
  morpho_selection <- unique(toupper(trimws(as.character(unlist(categories, use.names = FALSE)))))
  morpho_selection <- morpho_selection[nzchar(morpho_selection)]
  if (!length(morpho_selection)) morpho_selection <- c("NOM", "VER", "ADJ")

  inclure_autre_forme <- isTRUE(conserver_hors_lexique) || ("AUTRE_FORME" %in% morpho_selection)
  if (isTRUE(inclure_autre_forme) && !("AUTRE_FORME" %in% morpho_selection)) {
    morpho_selection <- c(morpho_selection, "AUTRE_FORME")
  }
  morpho_selection_lexique <- setdiff(morpho_selection, "AUTRE_FORME")

  if (!length(morpho_selection_lexique) && !isTRUE(inclure_autre_forme)) {
    log_info("Filtrage morphosyntaxique lexique_fr ignoré : aucune catégorie c_morpho sélectionnée.")
    return(dfm_obj)
  }

  lex <- lexique_fr_df
  lex_morpho <- toupper(trimws(as.character(lex$c_morpho)))
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

  n_feat_avant <- quanteda::nfeat(dfm_obj)
  pattern_keep <- featnames_dfm[keep_mask]
  dfm_filtre <- quanteda::dfm_select(
    dfm_obj,
    pattern = pattern_keep,
    selection = "keep",
    valuetype = "fixed",
    case_insensitive = FALSE
  )
  n_feat_apres <- quanteda::nfeat(dfm_filtre)

  repartition_categories <- character(0)
  if (length(morpho_selection_lexique) > 0) {
    feat_ret_norm <- featnames_norm[keep_mask]
    feat_ret_core <- featnames_core[keep_mask]
    repartition_categories <- vapply(
      morpho_selection_lexique,
      function(cat) {
        idx_cat <- idx & lex_morpho == cat
        termes_cat <- unique(c(
          tolower(trimws(as.character(lex$c_mot[idx_cat]))),
          tolower(trimws(as.character(lex$c_lemme[idx_cat])))
        ))
        termes_cat <- termes_cat[nzchar(termes_cat)]
        if (!length(termes_cat)) return("0")
        as.character(sum((feat_ret_norm %in% termes_cat) | (feat_ret_core %in% termes_cat)))
      },
      character(1)
    )
  }
  if (length(repartition_categories) > 0) {
    log_info(paste0("Répartition des termes conservés par c_morpho : ", paste0(names(repartition_categories), "=", repartition_categories, collapse = "; "), "."))
  }
  log_info(
    paste0(
      "Filtrage morphosyntaxique lexique_fr appliqué (c_morpho=",
      paste(morpho_selection, collapse = ","),
      " | inclure_autre_forme=",
      ifelse(isTRUE(inclure_autre_forme), "1", "0"),
      " | exclure_etre_verbe=",
      ifelse(isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee), "1", "0"),
      ") : ",
      n_feat_avant,
      " -> ",
      n_feat_apres,
      " termes uniques."
    )
  )

  dfm_filtre
}

highlight_text_html <- function(text, terms, start_tag, end_tag) {
  out <- text
  for (term in terms) {
    escaped_term <- gsub("([\\^\\$\\*\\+\\?\\(\\)\\[\\]\\{\\}\\.\\|])", "\\\\\\1", term)
    out <- gsub(
      paste0("\\b", escaped_term, "\\b"),
      paste0(start_tag, term, end_tag),
      out,
      ignore.case = TRUE
    )
  }
  out
}

log_info("Chargement du corpus...")
corpus_brut <- import_corpus_iramuteq(input_path)
log_info(sprintf("Nombre de documents importés : %s", quanteda::ndoc(corpus_brut)))

log_info("Découpage du corpus...")
if (identical(mode_decoupage, "segment_size")) {
  corpus_segments <- split_segments_local(corpus_brut, segment_size = segment_size)
} else if (identical(mode_decoupage, "ponctuation")) {
  textes <- as.character(corpus_brut)
  noms_docs <- quanteda::docnames(corpus_brut)
  phrases_list <- lapply(seq_along(textes), function(i) {
    doc_id <- noms_docs[[i]]
    phrases <- quanteda::tokenize_sentences(textes[[i]])[[1]]
    phrases <- phrases[nchar(phrases) > 0]
    names(phrases) <- paste0(doc_id, "_phrase", seq_along(phrases))
    phrases
  })
  phrases_all <- unlist(phrases_list)
  corpus_segments <- quanteda::corpus(phrases_all)
  quanteda::docnames(corpus_segments) <- names(phrases_all)
} else {
  stop("Mode de découpage invalide.")
}

if (quanteda::ndoc(corpus_segments) < 2) {
  stop("Le corpus segmenté contient moins de 2 segments : analyse impossible.")
}

log_info(sprintf("Nombre de segments créés : %s", quanteda::ndoc(corpus_segments)))

if (lemmatisation) {
  log_info("Lemmatisation UDPipe en cours...")
  model_file <- ensure_udpipe_model()
  ud_model <- udpipe::udpipe_load_model(model_file)
  corpus_segments_text <- as.character(corpus_segments)
  annotation_list <- lapply(seq_along(corpus_segments), function(i) {
    res <- udpipe::udpipe_annotate(ud_model, x = corpus_segments_text[[i]])
    df <- as.data.frame(res)
    df$doc_id <- quanteda::docnames(corpus_segments)[[i]]
    df
  })
  annotation_df <- do.call(rbind, annotation_list)
  annotation_df <- annotation_df %>%
    filter(upos %in% upos_a_conserver, !is.na(lemma), lemma != "", lemma != " ")

  textes_lemmat <- annotation_df %>%
    group_by(doc_id) %>%
    summarise(text = paste(lemma, collapse = " "), .groups = "drop")

  if (!nrow(textes_lemmat)) {
    stop("La lemmatisation a vidé entièrement le corpus.")
  }

  corpus_lemmat <- quanteda::corpus(textes_lemmat$text, docnames = textes_lemmat$doc_id)
} else {
  corpus_lemmat <- quanteda::corpus(as.character(corpus_segments), docnames = quanteda::docnames(corpus_segments))
}

log_info(sprintf("Préparation de la DFM (nettoyage lexical = %s)...", mode_nettoyage_lexical))
tok <- quanteda::tokens(corpus_lemmat, remove_punct = TRUE, remove_numbers = TRUE)
if (identical(mode_nettoyage_lexical, "stopwords_quanteda")) {
  n_feat_avant_stop <- quanteda::nfeat(quanteda::dfm(tok))
  tok <- quanteda::tokens_remove(tok, quanteda::stopwords("fr"))
  n_feat_apres_stop <- quanteda::nfeat(quanteda::dfm(tok))
  log_info(sprintf("Filtrage stopwords quanteda(fr) appliqué : %s -> %s termes uniques.", n_feat_avant_stop, n_feat_apres_stop))
} else if (identical(mode_nettoyage_lexical, "lexique_iramuteq")) {
  log_info("Stopwords quanteda désactivés : filtrage par dictionnaire IRaMuTeQ-lite.")
} else {
  log_info("Nettoyage lexical désactivé : aucun stopword ni dictionnaire appliqué.")
}
tok <- quanteda::tokens_split(tok, "'")
tok <- quanteda::tokens_remove(tok, pattern = c("\\b[a-zA-Z]\\b", "^[^a-zA-Z]+$"), valuetype = "regex")
tok <- quanteda::tokens_tolower(tok)
dfm_obj <- quanteda::dfm(tok)
if (identical(mode_nettoyage_lexical, "lexique_iramuteq")) {
  lexique_fr_df <- charger_lexique_fr_iramuteq()
  log_info(sprintf("Lexique IRaMuTeQ-lite chargé : %s entrées.", nrow(lexique_fr_df)))
  if (isTRUE(lexique_utiliser_lemmes)) {
    tok <- lemmatiser_tokens_lexique_iramuteq(tok, lexique_fr_df)
    dfm_obj <- quanteda::dfm(tok)
  } else {
    log_info("Lemmatisation lexique_fr désactivée.")
  }
  dfm_obj <- filtrer_dfm_lexique_iramuteq(
    dfm_obj = dfm_obj,
    lexique_fr_df = lexique_fr_df,
    categories = pos_lexique_a_conserver,
    conserver_hors_lexique = morpho_conserver_hors_lexique,
    exclure_etre_verbe = morpho_exclure_etre_verbe
  )
}
dfm_obj <- quanteda::dfm_trim(dfm_obj, min_docfreq = min_docfreq)

if (quanteda::ndoc(dfm_obj) < 2 || quanteda::nfeat(dfm_obj) < 2) {
  stop("Après nettoyage, le corpus est trop pauvre pour une CHD Rainette.")
}

included_segments <- quanteda::docnames(dfm_obj)
corpus_affichage <- corpus_segments[included_segments]
filtered_corpus <- corpus_lemmat[included_segments]

log_info(sprintf("DFM prête : %s segments / %s termes.", quanteda::ndoc(dfm_obj), quanteda::nfeat(dfm_obj)))
log_info("Lancement de la classification Rainette...")

res <- rainette::rainette(
  dfm_obj,
  k = k,
  min_segment_size = 0,
  min_split_members = max(3L, min_split_segments)
)

classes <- as.integer(res$group)
quanteda::docvars(filtered_corpus)$Classes <- classes
quanteda::docvars(corpus_affichage)$Classes <- classes

classes_df <- as.data.frame(table(Classe = classes), stringsAsFactors = FALSE)
classes_df$Classe <- as.character(classes_df$Classe)
classes_df$Segments <- as.integer(classes_df$Freq)
classes_df$Freq <- NULL

log_info("Calcul des termes discriminants...")
res_stats_list <- rainette::rainette_stats(
  dtm = dfm_obj,
  groups = classes,
  measure = c("chi2"),
  n_terms = 9999,
  show_negative = TRUE,
  max_p = 0.05
)
res_stats_df <- dplyr::bind_rows(res_stats_list, .id = "Classe")

top_terms_by_class <- res_stats_df %>%
  filter(p <= 0.05, nchar(feature) >= 3) %>%
  group_by(Classe) %>%
  arrange(desc(chi2), .by_group = TRUE) %>%
  slice_head(n = top_n) %>%
  summarise(terms = list(unique(feature)), .groups = "drop")

top_terms_lookup <- setNames(top_terms_by_class$terms, top_terms_by_class$Classe)

segments_list_raw <- split(as.character(corpus_affichage), quanteda::docvars(corpus_affichage)$Classes)
segments_names_raw <- split(quanteda::docnames(corpus_affichage), quanteda::docvars(corpus_affichage)$Classes)

segments_by_class <- lapply(names(segments_list_raw), function(cl) {
  segs <- segments_list_raw[[cl]]
  seg_names <- segments_names_raw[[cl]]
  terms <- top_terms_lookup[[cl]]
  if (is.null(terms) || !length(terms)) {
    names(segs) <- seg_names
    return(segs)
  }
  keep <- sapply(segs, function(segment) {
    any(sapply(terms, function(term) grepl(paste0("\\b", term, "\\b"), segment, ignore.case = TRUE)))
  })
  out <- segs[keep]
  names(out) <- seg_names[keep]
  out
})
names(segments_by_class) <- names(segments_list_raw)

segments_file <- file.path(output_dir, "segments_par_classe.txt")
writeLines(
  unlist(lapply(names(segments_by_class), function(cl) {
    c(paste0("Classe ", cl, ":"), unname(segments_by_class[[cl]]), "")
  })),
  segments_file
)

html_file <- file.path(output_dir, "segments_par_classe.html")
if (file.exists(html_file)) file.remove(html_file)
cat("<html><head><meta charset='UTF-8'><style>body { font-family: Arial; } span.highlight { background-color: yellow; }</style></head><body>\n",
    file = html_file, append = TRUE)
cat("<h1>Segments par classe (termes discriminants surlignés)</h1>\n", file = html_file, append = TRUE)
for (cl in names(segments_by_class)) {
  cat(paste0("<h2>Classe ", cl, "</h2>\n"), file = html_file, append = TRUE)
  terms <- top_terms_lookup[[cl]]
  for (segment in segments_by_class[[cl]]) {
    highlighted_segment <- if (is.null(terms) || !length(terms)) segment else highlight_text_html(
      segment,
      terms,
      "<span class='highlight'>",
      "</span>"
    )
    cat(paste0("<p>", highlighted_segment, "</p>\n"), file = html_file, append = TRUE)
  }
}
cat("</body></html>\n", file = html_file, append = TRUE)

wordcloud_dir <- file.path(output_dir, "wordclouds")
dir.create(wordcloud_dir, showWarnings = FALSE, recursive = TRUE)

for (cl in sort(unique(classes))) {
  subset_stats <- subset(res_stats_df, Classe == cl & p <= 0.05)
  subset_stats <- subset_stats[order(-subset_stats$chi2), ]
  if (nrow(subset_stats) > 0) {
    subset_stats <- head(subset_stats, top_n)
    safe_wordcloud(
      words = subset_stats$feature,
      freq = subset_stats$chi2,
      file_path = file.path(wordcloud_dir, paste0("classe_", cl, "_wordcloud_chi2.png")),
      colors = brewer.pal(8, "Dark2")
    )
  }

  idx <- which(classes == cl)
  if (length(idx) > 0) {
    dfm_cl <- dfm_obj[idx, ]
    freq_terms <- sort(Matrix::colSums(dfm_cl), decreasing = TRUE)
    if (length(freq_terms) > 0) {
      freq_terms <- freq_terms[seq_len(min(top_n, length(freq_terms)))]
      safe_wordcloud(
        words = names(freq_terms),
        freq = as.numeric(freq_terms),
        file_path = file.path(wordcloud_dir, paste0("classe_", cl, "_wordcloud_frequence.png")),
        colors = brewer.pal(8, "Set2")
      )
    }
  }
}

mot_segment_liste <- list()
for (cl in sort(unique(classes))) {
  mots_cl <- res_stats_df %>%
    filter(Classe == cl, p <= 0.05, nchar(feature) >= 3) %>%
    arrange(desc(chi2)) %>%
    slice_head(n = top_n) %>%
    pull(feature)

  segments_cl <- as.character(segments_by_class[[as.character(cl)]])
  noms_segments_cl <- names(segments_by_class[[as.character(cl)]])

  for (mot in mots_cl) {
    keep <- grepl(paste0("\\b", mot, "\\b"), segments_cl, ignore.case = TRUE)
    if (any(keep)) {
      mot_segment_liste[[length(mot_segment_liste) + 1L]] <- data.frame(
        Mot = mot,
        Classe = cl,
        Segment = segments_cl[keep],
        Nom_Segment = noms_segments_cl[keep],
        stringsAsFactors = FALSE
      )
    }
  }
}

df_mot_segments <- if (length(mot_segment_liste)) do.call(rbind, mot_segment_liste) else data.frame(
  Mot = character(0),
  Classe = integer(0),
  Segment = character(0),
  Nom_Segment = character(0),
  stringsAsFactors = FALSE
)

csv_mot_segments_path <- file.path(output_dir, "mots_chi2_segments.csv")
write.csv(df_mot_segments, file = csv_mot_segments_path, row.names = FALSE, fileEncoding = "UTF-8")

res_stats_df_clean <- res_stats_df %>%
  rename(Mot = feature, Chi2 = chi2, p_value = p) %>%
  mutate(Mot = as.character(Mot))

donnees_finales <- merge(
  df_mot_segments,
  res_stats_df_clean[, c("Mot", "Classe", "Chi2", "p_value")],
  by = c("Mot", "Classe"),
  all.x = TRUE
)

frequences_par_classe <- lapply(sort(unique(classes)), function(cl) {
  idx <- which(classes == cl)
  dfm_cl <- dfm_obj[idx, ]
  freqs <- sort(Matrix::colSums(dfm_cl), decreasing = TRUE)
  data.frame(
    Mot = names(freqs),
    Frequence = as.numeric(freqs),
    Classe = cl,
    stringsAsFactors = FALSE
  )
})
frequences_df <- do.call(rbind, frequences_par_classe)

donnees_finales <- merge(
  donnees_finales,
  frequences_df[, c("Mot", "Classe", "Frequence")],
  by = c("Mot", "Classe"),
  all.x = TRUE
)

donnees_finales <- donnees_finales %>%
  arrange(as.numeric(Classe), desc(Chi2), Mot)

csv_fusion_path <- file.path(output_dir, "mots_chi2_frequence_segments.csv")
write.csv(donnees_finales, file = csv_fusion_path, row.names = FALSE, fileEncoding = "UTF-8")

classe_dir <- file.path(output_dir, "mots_par_classe_csv")
dir.create(classe_dir, showWarnings = FALSE, recursive = TRUE)
for (cl in sort(unique(donnees_finales$Classe))) {
  data_cl <- donnees_finales %>%
    filter(Classe == cl) %>%
    arrange(desc(Chi2), Mot)
  write.csv(
    data_cl,
    file = file.path(classe_dir, paste0("classe_", cl, "_mots_chi2_segments.csv")),
    row.names = FALSE,
    fileEncoding = "UTF-8"
  )
}

resume_classes <- classes_df
resume_classes$Top_termes <- vapply(
  resume_classes$Classe,
  function(cl) {
    terms <- top_terms_lookup[[as.character(cl)]]
    if (is.null(terms) || !length(terms)) return("")
    paste(terms, collapse = ", ")
  },
  character(1)
)
resume_classes_path <- file.path(output_dir, "resume_classes.csv")
write.csv(resume_classes, file = resume_classes_path, row.names = FALSE, fileEncoding = "UTF-8")

png(file.path(output_dir, "class_distribution.png"), width = 900, height = 600)
barplot(
  height = resume_classes$Segments,
  names.arg = resume_classes$Classe,
  col = "steelblue",
  main = "Répartition des segments par classe",
  xlab = "Classe",
  ylab = "Nombre de segments"
)
dev.off()

rainette_plot_path <- file.path(output_dir, "rainette_plot.png")
tryCatch({
  png(rainette_plot_path, width = 1200, height = 800)
  plot(res)
  dev.off()
}, error = function(e) {
  if (dev.cur() > 1) dev.off()
  png(rainette_plot_path, width = 1200, height = 800)
  plot.new()
  text(
    0.5,
    0.55,
    labels = "Visualisation Rainette indisponible pour ce rendu.\nLe VPS affiche un export statique de secours.",
    cex = 1.2
  )
  text(
    0.5,
    0.40,
    labels = paste("Détail R :", conditionMessage(e)),
    cex = 0.9
  )
  dev.off()
})

metadata <- list(
  input_file = basename(input_path),
  settings = config,
  n_documents_imported = quanteda::ndoc(corpus_brut),
  n_segments_created = quanteda::ndoc(corpus_segments),
  n_segments_analyzed = quanteda::ndoc(filtered_corpus),
  n_features = quanteda::nfeat(dfm_obj),
  n_classes = nrow(resume_classes),
  classes_distribution = split(resume_classes, seq_len(nrow(resume_classes)))
)

bundle_path <- file.path(output_dir, "analysis_bundle.rds")
analysis_bundle <- list(
  res = res,
  dtm = dfm_obj,
  corpus_src = corpus_affichage,
  metadata = metadata,
  summary = resume_classes,
  keyness = res_stats_df,
  max_k = max(classes, na.rm = TRUE)
)
saveRDS(analysis_bundle, bundle_path)

metadata$bundle_file <- basename(bundle_path)
metadata$output_files <- list.files(output_dir, recursive = TRUE)

jsonlite::write_json(metadata, path = file.path(output_dir, "metadata.json"), auto_unbox = TRUE, pretty = TRUE)
log_info("Analyse Rainette terminée.")
