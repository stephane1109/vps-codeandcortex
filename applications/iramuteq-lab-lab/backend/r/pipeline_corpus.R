# Importation et segmentation des corpus IRAMUTEQ Lab.
# Les fonctions sont extraites sans modification de leur comportement.

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
      tokens_entete <- extraire_tokens_entete_iramuteq(entete)
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
# Découpage indexé : chaque token est examiné une seule fois pour déterminer
# son type, puis les frontières sont recherchées uniquement à la taille cible.
# Cette fonction conserve les priorités et les départages du code précédent.
.segmenter_ponctuation_indices <- function(tok, taille_segment, supprimer_ponctuation = FALSE) {
  nb_tokens <- length(tok)
  if (nb_tokens == 0L) return(character(0))

  est_ponctuation <- grepl("^[[:punct:]]+$", tok)
  rangs <- rep.int(4L, nb_tokens)
  rangs[est_ponctuation & grepl("^[.!?…]+$", tok)] <- 1L
  rangs[est_ponctuation & grepl("^[;:]+$", tok)] <- 2L
  rangs[est_ponctuation & grepl("^[,]+$", tok)] <- 3L

  # Une position préfixe permet de compter les mots sans reparcourir
  # l'ensemble des tokens déjà analysés à chaque nouveau mot.
  comptes_cumules <- c(0L, cumsum(as.integer(!est_ponctuation & tok != "__NL_SEG_BREAK__")))
  seuil_candidat <- max(1L, floor(taille_segment * 0.5))

  segments <- character(max(1L, ceiling(nb_tokens / taille_segment)))
  nb_segments <- 0L
  debut_segment <- 1L

  ajouter_segment <- function(debut, fin) {
    if (debut > fin) return(invisible(NULL))
    mots <- tok[seq.int(debut, fin)]
    mots <- mots[mots != "__NL_SEG_BREAK__"]
    if (isTRUE(supprimer_ponctuation)) {
      mots <- mots[!grepl("^[[:punct:]]+$", mots)]
    }
    texte <- paste(mots, collapse = " ")
    if (!nzchar(texte)) return(invisible(NULL))
    nb_segments <<- nb_segments + 1L
    if (nb_segments > length(segments)) {
      segments <<- c(segments, character(max(1L, length(segments))))
    }
    segments[[nb_segments]] <<- texte
    invisible(NULL)
  }

  for (position in seq_len(nb_tokens)) {
    if (identical(tok[[position]], "__NL_SEG_BREAK__")) {
      # Conserver le traitement existant des retours à la ligne.
      if (debut_segment < position) {
        ajouter_segment(debut_segment, position - 1L)
      }
      debut_segment <- position + 1L
      next
    }

    # Contrairement à l'ancienne version, la recherche n'est déclenchée
    # que lorsque le nombre de mots atteint la taille demandée.
    while (debut_segment <= position &&
           comptes_cumules[[position + 1L]] - comptes_cumules[[debut_segment]] >= taille_segment) {
      positions <- seq.int(debut_segment, position)
      comptes <- comptes_cumules[positions + 1L] - comptes_cumules[[debut_segment]]
      candidats <- which(comptes >= seuil_candidat)
      if (!length(candidats)) candidats <- seq_along(positions)

      # Priorité : ponctuation, distance à la taille cible, position la plus à droite.
      ordre <- order(
        rangs[positions[candidats]],
        abs(comptes[candidats] - taille_segment),
        -positions[candidats]
      )
      position_coupure <- positions[candidats[ordre[[1L]]]]
      ajouter_segment(debut_segment, position_coupure)
      debut_segment <- position_coupure + 1L
    }
  }

  # Le reliquat final peut être inférieur à la taille cible.
  if (debut_segment <= nb_tokens) {
    ajouter_segment(debut_segment, nb_tokens)
  }

  if (!nb_segments) return(character(0))
  segments[seq_len(nb_segments)]
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
  dv_in <- tryCatch(quanteda::docvars(corpus), error = function(e) NULL)

  # Conserver l'ordre des textes et les options de tokenisation existantes,
  # sans multiplier les concaténations de vecteurs pour chaque nouveau segment.
  textes_par_document <- vector("list", length(docs))

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

      textes_par_document[[i]] <- .segmenter_ponctuation_indices(
        tok,
        taille_segment = segment_size,
        supprimer_ponctuation = isTRUE(remove_punct)
      )
    } else {
      # Le découpage strict par nombre de mots et toutes ses options restent inchangés.
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
      debuts <- ((seq_len(nseg) - 1L) * segment_size) + 1L
      fins <- pmin(seq_len(nseg) * segment_size, length(tok))
      textes_par_document[[i]] <- vapply(seq_len(nseg), function(j) {
        paste(tok[debuts[[j]]:fins[[j]]], collapse = " ")
      }, character(1))
    }
  }

  nombres_segments <- lengths(textes_par_document)
  if (!sum(nombres_segments)) stop("Segmentation impossible : aucun segment généré.")

  # Les indices remplacent la copie répétée des métadonnées documentaires.
  indices_documents <- rep.int(seq_along(docs), nombres_segments)
  numeros_segments <- sequence(nombres_segments)
  out_text <- unlist(textes_par_document, use.names = FALSE)
  out_id <- paste0(dn[indices_documents], "_seg", numeros_segments)
  out_src <- dn[indices_documents]

  corp <- quanteda::corpus(
    data.frame(doc_id = out_id, text = out_text, segment_source = out_src, stringsAsFactors = FALSE),
    text_field = "text"
  )
  quanteda::docvars(corp, "segment_source") <- out_src

  if (!is.null(dv_in) && nrow(dv_in) > 0L) {
    indices_valides <- which(indices_documents <= nrow(dv_in))
    if (length(indices_valides)) {
      # Reproduire les affectations de l'ancien code, avec les mêmes types
      # de colonnes, sans construire un data.frame pour chaque segment.
      colonnes <- setdiff(colnames(dv_in), "segment_source")
      for (cn in colonnes) {
        valeurs <- rep(NA, length(out_text))
        valeurs[indices_valides] <- dv_in[[cn]][indices_documents[indices_valides]]
        quanteda::docvars(corp, cn) <- valeurs
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
