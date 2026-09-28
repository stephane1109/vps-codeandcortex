# Outils communs pour lire les variables étoilées des en-têtes IRaMuTeQ.

extraire_tokens_entete_iramuteq <- function(entete) {
  if (is.null(entete) || !length(entete)) return(character(0))
  texte <- enc2utf8(as.character(entete))
  texte <- texte[!is.na(texte) & nzchar(texte)]
  if (!length(texte)) return(character(0))

  champs <- unlist(strsplit(trimws(texte), "[[:space:]]+", perl = TRUE), use.names = FALSE)
  tokens <- champs[grepl("^\\*[^*[:space:]]+$", champs, perl = TRUE)]
  unique(tokens[!is.na(tokens) & nchar(tokens, type = "chars") > 1L])
}
