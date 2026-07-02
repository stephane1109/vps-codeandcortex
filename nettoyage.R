# nettoyage.R

# Regex : on supprime tout caractère NON présent dans la liste autorisée.
# Cette liste provient de ta consigne : ^a-zA-Z0-9... + ponctuation basique
# Important : cette regex agit AVANT la tokenisation quanteda. La tokenisation peut ensuite retirer
# la ponctuation (remove_punct=TRUE), même si elle est "autorisée" ici.

REGEX_CARACTERES_AUTORISES <- "a-zA-Z0-9àÀâÂäÄáÁåÅãéÉèÈêÊëËìÌîÎïÏíÍóÓòÒôÔöÖõÕøØùÙûÛüÜúÚçÇßœŒ’ñÑ\\.:,;!\\?'"
REGEX_CARACTERES_A_SUPPRIMER <- paste0("[^", REGEX_CARACTERES_AUTORISES, "]")

appliquer_nettoyage_et_minuscules <- function(textes,
                                             activer_nettoyage = FALSE,
                                             forcer_minuscules = FALSE,
                                             supprimer_chiffres = FALSE,
                                             supprimer_apostrophes = FALSE) {
  x <- textes
  if (is.null(x)) return(character(0))

  # Normaliser quelques espaces exotiques
  x <- gsub("\u00A0", " ", x, fixed = TRUE)

  # Option : suppression des chiffres AVANT tokenisation
  if (isTRUE(supprimer_chiffres)) {
    x <- gsub("[0-9]+", " ", x, perl = TRUE)
  }

  # Option : traitement des élisions françaises en début de mot (m', l', d', n', t', s', c', j', qu')
  # Exemple : "c'est" -> "est", "m'ecrire" -> "ecrire"
  # Les apostrophes lexicales internes (ex. "aujourd'hui") sont conservées.
  if (isTRUE(supprimer_apostrophes)) {
    x <- gsub("(?i)\\b(?:[cdjlmnst]|qu)['’](?=\\p{L})", "", x, perl = TRUE)
  }

  # Option : nettoyage des caractères "non autorisés"
  if (isTRUE(activer_nettoyage)) {
    x <- gsub(REGEX_CARACTERES_A_SUPPRIMER, " ", x, perl = TRUE)
  }

  # Normaliser les espaces
  x <- gsub("\\s+", " ", x, perl = TRUE)
  x <- trimws(x)

  # Option : minuscules (UNE seule fois dans toute l'appli)
  if (isTRUE(forcer_minuscules)) {
    x <- tolower(x)
  }

  x
}
