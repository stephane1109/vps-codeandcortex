# Module AFC - helpers de contextualisation des termes
# Ce fichier regroupe des utilitaires AFC, notamment la construction de segments
# exemples associés aux termes caractéristiques de classes.

construire_segments_exemples_afc <- function(termes_stats, dfm_obj, corpus_obj, max_chars = 220) {
  if (is.null(termes_stats) || nrow(termes_stats) == 0 || is.null(dfm_obj) || is.null(corpus_obj)) return(termes_stats)
  if (!all(c("Terme", "Classe_max") %in% names(termes_stats))) return(termes_stats)

  classes_docs <- normaliser_classes(docvars(corpus_obj)$Classes)
  textes <- as.character(corpus_obj)

  if (length(classes_docs) != ndoc(dfm_obj) || length(textes) != ndoc(dfm_obj)) return(termes_stats)

  mat <- as.matrix(dfm_obj)
  termes_stats$Segment_texte <- NA_character_

  for (i in seq_len(nrow(termes_stats))) {
    terme <- as.character(termes_stats$Terme[i])
    classe_num <- suppressWarnings(as.numeric(gsub("^Classe\\s+", "", as.character(termes_stats$Classe_max[i]))))

    if (is.na(classe_num) || !nzchar(terme) || !(terme %in% colnames(mat))) next

    idx <- which(classes_docs == as.character(classe_num) & mat[, terme] > 0)
    if (length(idx) == 0) next

    # Segment le plus représentatif pour le terme dans la classe (fréquence max du terme)
    i_best <- idx[which.max(mat[idx, terme])]
    seg <- gsub("\\s+", " ", trimws(textes[i_best]), perl = TRUE)
    if (!nzchar(seg)) next
    if (nchar(seg) > max_chars) seg <- paste0(substr(seg, 1, max_chars - 1), "…")

    termes_stats$Segment_texte[i] <- seg
  }

  termes_stats
}
