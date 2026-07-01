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
lemmatisation <- isTRUE(config$lemmatisation)
upos_a_conserver <- if (!is.null(config$upos_a_conserver)) as.character(config$upos_a_conserver) else c("NOUN", "ADJ")

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

log_info("Préparation de la DFM...")
tok <- quanteda::tokens(corpus_lemmat, remove_punct = TRUE, remove_numbers = TRUE)
tok <- quanteda::tokens_remove(tok, quanteda::stopwords("fr"))
tok <- quanteda::tokens_split(tok, "'")
tok <- quanteda::tokens_remove(tok, pattern = c("\\b[a-zA-Z]\\b", "^[^a-zA-Z]+$"), valuetype = "regex")
tok <- quanteda::tokens_tolower(tok)
dfm_obj <- quanteda::dfm(tok)
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
    labels = "Visualisation Rainette indisponible en mode Shiny.\nLe VPS affiche un export statique de secours.",
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
  classes_distribution = split(resume_classes, seq_len(nrow(resume_classes))),
  output_files = list.files(output_dir, recursive = TRUE)
)

jsonlite::write_json(metadata, path = file.path(output_dir, "metadata.json"), auto_unbox = TRUE, pretty = TRUE)
log_info("Analyse Rainette terminée.")
