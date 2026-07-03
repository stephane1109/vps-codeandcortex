split_sentences_with_docvars <- function(corpus_obj) {
  docs <- as.character(corpus_obj)
  doc_names <- as.character(quanteda::docnames(corpus_obj))
  doc_vars <- quanteda::docvars(corpus_obj)
  rows <- list()

  for (index in seq_along(docs)) {
    text <- docs[[index]]
    if (is.na(text) || !nzchar(trimws(text))) {
      next
    }

    # Découpage léger sur ponctuation forte pour proposer une alternative
    # au segment_size sans ouvrir de second navigateur ni casser les docvars.
    sentences <- unlist(strsplit(text, "(?<=[\\.!?;:])\\s+", perl = TRUE), use.names = FALSE)
    sentences <- trimws(sentences)
    sentences <- sentences[nzchar(sentences)]
    if (!length(sentences)) {
      next
    }

    meta <- as.list(doc_vars[index, , drop = FALSE])
    meta$segment_source <- doc_names[[index]]

    for (sentence_index in seq_along(sentences)) {
      rows[[length(rows) + 1L]] <- c(
        list(
          doc_id = paste0(doc_names[[index]], "_phrase", sentence_index),
          text = sentences[[sentence_index]]
        ),
        meta
      )
    }
  }

  if (!length(rows)) {
    stop("Aucune phrase n'a pu être extraite du corpus.")
  }

  quanteda::corpus(dplyr::bind_rows(rows), text_field = "text")
}
