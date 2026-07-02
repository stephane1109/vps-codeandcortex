compter_tokens <- function(tok) {
  lst <- as.list(tok)
  sum(vapply(lst, length, integer(1)))
}

md5_fichier <- function(chemin) {
  if (is.null(chemin) || !file.exists(chemin)) return(NA_character_)
  as.character(tools::md5sum(chemin))[1]
}
