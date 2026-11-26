# Rôle du fichier : utilitaires de contextualisation des termes AFC.
# Les exemples sont sélectionnés dans la matrice lexicale creuse, sans conversion dense.

construire_segments_exemples_afc <- function(termes_stats, dfm_obj, corpus_obj, max_chars = 220) {
  if (is.null(termes_stats) || nrow(termes_stats) == 0 || is.null(dfm_obj) || is.null(corpus_obj)) return(termes_stats)
  if (!all(c("Terme", "Classe_max") %in% names(termes_stats))) return(termes_stats)

  classes_docs <- suppressWarnings(as.integer(quanteda::docvars(corpus_obj)$Classes))
  classes_docs[!is.finite(classes_docs) | is.na(classes_docs) | classes_docs <= 0] <- NA_integer_
  classes_docs <- as.character(classes_docs)
  textes <- as.character(corpus_obj)

  if (length(classes_docs) != quanteda::ndoc(dfm_obj) || length(textes) != quanteda::ndoc(dfm_obj)) return(termes_stats)

  # Le format dgCMatrix conserve les occurrences par colonne et les lignes
  # correspondantes dans l'ordre croissant. Aucune matrice dense n'est créée.
  matrice_creuse <- methods::as(dfm_obj, "dgCMatrix")
  pointeurs_colonnes <- matrice_creuse@p
  indices_lignes <- matrice_creuse@i
  frequences <- matrice_creuse@x
  positions_termes <- match(as.character(termes_stats$Terme), colnames(matrice_creuse))

  termes_stats$Segment_texte <- NA_character_

  for (i in seq_len(nrow(termes_stats))) {
    terme <- as.character(termes_stats$Terme[i])
    classe_num <- suppressWarnings(as.numeric(gsub("^Classe\\s+", "", as.character(termes_stats$Classe_max[i]))))
    colonne <- positions_termes[i]

    if (is.na(classe_num) || is.na(terme) || !nzchar(terme) || is.na(colonne)) next

    # Les pointeurs sont indexés à partir de zéro dans dgCMatrix.
    debut <- pointeurs_colonnes[colonne] + 1L
    fin <- pointeurs_colonnes[colonne + 1L]
    if (debut > fin) next

    positions <- seq.int(debut, fin)
    lignes <- indices_lignes[positions] + 1L
    comptes <- frequences[positions]

    # Reproduire le critère initial : classe identique, fréquence strictement
    # positive et maximum d'occurrences. En cas d'égalité, garder le premier
    # segment dans l'ordre du corpus, comme avec which.max() sur la matrice dense.
    garder <- classes_docs[lignes] == as.character(classe_num) & comptes > 0
    garder[is.na(garder)] <- FALSE
    if (!any(garder)) next

    i_best <- lignes[garder][which.max(comptes[garder])]
    seg <- gsub("\\s+", " ", trimws(textes[i_best]), perl = TRUE)
    if (!nzchar(seg)) next
    if (nchar(seg) > max_chars) seg <- paste0(substr(seg, 1, max_chars - 1), "…")

    termes_stats$Segment_texte[i] <- seg
  }

  termes_stats
}
