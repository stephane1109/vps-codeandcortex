# Module NLP - exécution spaCy via reticulate
# Ce fichier branche directement les scripts Python de l'application dans R via
# reticulate, au lieu de lancer des commandes shell intermédiaires.

normaliser_tokens_reticulate <- function(tokens) {
  if (is.null(tokens) || length(tokens) == 0) {
    return(NULL)
  }

  if (is.data.frame(tokens)) {
    return(tokens)
  }

  tokens <- lapply(tokens, function(row) {
    if (is.null(row)) {
      return(NULL)
    }
    as.list(row)
  })
  tokens <- Filter(Negate(is.null), tokens)
  if (!length(tokens)) {
    return(NULL)
  }

  data.frame(
    doc_id = vapply(tokens, function(row) as.character(row$doc_id %||% ""), character(1)),
    token = vapply(tokens, function(row) as.character(row$token %||% ""), character(1)),
    lemma = vapply(tokens, function(row) as.character(row$lemma %||% ""), character(1)),
    pos = vapply(tokens, function(row) as.character(row$pos %||% ""), character(1)),
    stringsAsFactors = FALSE
  )
}

executer_spacy_filtrage <- function(ids, textes, pos_a_conserver, utiliser_lemmes, lower_input, modele_spacy, rv) {
  bridge <- obtenir_bridge_reticulate()

  if (is.null(pos_a_conserver)) {
    pos_a_conserver <- character(0)
  }

  ajouter_log(
    rv,
    paste0(
      "spaCy / reticulate : modèle ", modele_spacy,
      " | POS=",
      if (length(pos_a_conserver)) paste(pos_a_conserver, collapse = ", ") else "aucun filtrage POS",
      " | lemmes=", ifelse(isTRUE(utiliser_lemmes), "1", "0")
    )
  )

  result <- tryCatch(
    bridge$preprocess_corpus(
      doc_ids = as.list(as.character(ids)),
      textes = as.list(as.character(textes)),
      modele = as.character(modele_spacy),
      pos_keep = as.list(as.character(pos_a_conserver)),
      utiliser_lemmes = isTRUE(utiliser_lemmes),
      lower_input = isTRUE(lower_input)
    ),
    error = function(error) {
      stop("Erreur spaCy / reticulate : ", conditionMessage(error))
    }
  )

  doc_ids <- as.character(result$doc_ids %||% character(0))
  textes_sortie <- as.character(result$texts %||% character(0))
  if (!length(doc_ids) || length(doc_ids) != length(textes_sortie)) {
    stop("spaCy / reticulate a renvoyé une sortie incohérente.")
  }

  names(textes_sortie) <- doc_ids
  tokens_df <- normaliser_tokens_reticulate(result$tokens %||% NULL)
  list(textes = textes_sortie[as.character(ids)], tokens_df = tokens_df)
}

executer_spacy_ner <- function(ids, textes, modele_spacy, rv) {
  bridge <- obtenir_bridge_reticulate()

  ajouter_log(rv, paste0("NER / reticulate : modèle ", modele_spacy))

  rows <- tryCatch(
    bridge$extract_entities(
      doc_ids = as.list(as.character(ids)),
      textes = as.list(as.character(textes)),
      modele = as.character(modele_spacy)
    ),
    error = function(error) {
      stop("Erreur NER / reticulate : ", conditionMessage(error))
    }
  )

  if (is.null(rows) || length(rows) == 0) {
    return(data.frame(
      doc_id = character(0),
      ent_text = character(0),
      ent_label = character(0),
      start_char = integer(0),
      end_char = integer(0),
      stringsAsFactors = FALSE
    ))
  }

  if (is.data.frame(rows)) {
    df_ent <- rows
  } else {
    df_ent <- data.frame(
      doc_id = vapply(rows, function(row) as.character(row$doc_id %||% ""), character(1)),
      ent_text = vapply(rows, function(row) as.character(row$ent_text %||% ""), character(1)),
      ent_label = vapply(rows, function(row) as.character(row$ent_label %||% ""), character(1)),
      start_char = suppressWarnings(as.integer(vapply(rows, function(row) as.character(row$start_char %||% NA_character_), character(1)))),
      end_char = suppressWarnings(as.integer(vapply(rows, function(row) as.character(row$end_char %||% NA_character_), character(1)))),
      stringsAsFactors = FALSE
    )
  }

  df_ent$doc_id <- trimws(as.character(df_ent$doc_id))
  df_ent$ent_text <- trimws(gsub("\\s+", " ", as.character(df_ent$ent_text), perl = TRUE))
  df_ent$ent_label <- as.character(df_ent$ent_label)
  df_ent <- df_ent[!is.na(df_ent$ent_text) & nzchar(df_ent$ent_text), , drop = FALSE]
  df_ent
}
