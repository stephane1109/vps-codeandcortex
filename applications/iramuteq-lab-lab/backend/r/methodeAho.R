# Présélection des documents par Aho-Corasick ; substitutions réalisées par le moteur classique.
# Ce fichier ne modifie ni le dictionnaire ni les règles de remplacement existantes.

appliquer_dictionnaire_expressions_aho <- function(textes, expressions_df, script_python, appliquer_natif) {
  if (is.null(textes) || length(textes) == 0L ||
      is.null(expressions_df) || !is.data.frame(expressions_df) || nrow(expressions_df) == 0L) {
    return(appliquer_natif(textes, expressions_df))
  }
  if (!is.function(appliquer_natif)) {
    stop("Aho-Corasick : la fonction native de substitution est indisponible.")
  }
  if (!file.exists(script_python)) {
    stop("Aho-Corasick : module Python introuvable : ", script_python)
  }
  python <- Sys.which("python3")
  if (!nzchar(python)) {
    stop("Aho-Corasick : Python 3 est indisponible.")
  }
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Aho-Corasick : le package R jsonlite est indisponible.")
  }

  fichier_entree <- tempfile("methode_aho_entree_", fileext = ".json")
  fichier_sortie <- tempfile("methode_aho_sortie_", fileext = ".json")
  fichier_erreurs <- tempfile("methode_aho_erreurs_", fileext = ".log")
  on.exit(unlink(c(fichier_entree, fichier_sortie, fichier_erreurs)), add = TRUE)

  jsonlite::write_json(
    list(textes = as.character(textes), motifs = as.character(expressions_df$dic_mot)),
    path = fichier_entree,
    auto_unbox = FALSE,
    na = "null"
  )
  code_sortie <- suppressWarnings(system2(
    python,
    args = c(shQuote(script_python), shQuote(fichier_entree), shQuote(fichier_sortie)),
    stdout = FALSE,
    stderr = fichier_erreurs,
    wait = TRUE
  ))
  if (!identical(as.integer(code_sortie), 0L) || !file.exists(fichier_sortie)) {
    erreurs <- if (file.exists(fichier_erreurs)) readLines(fichier_erreurs, warn = FALSE) else character()
    stop("Aho-Corasick : échec de la présélection Python. ", paste(erreurs, collapse = " "))
  }

  resultat <- jsonlite::fromJSON(fichier_sortie, simplifyVector = TRUE)
  indices_bruts <- resultat$indices
  indices <- as.integer(indices_bruts) + 1L
  if (anyNA(indices) || any(indices < 1L | indices > length(textes))) {
    stop("Aho-Corasick : la présélection a renvoyé des indices invalides.")
  }
  indices <- sort(unique(indices))

  # Conserver la normalisation globale des apostrophes, même sans correspondance.
  textes_sortie <- as.character(textes)
  textes_sortie <- gsub(paste0("[’", intToUtf8(96L), "´ʼʹ]"), "'", textes_sortie, perl = TRUE)
  if (!length(indices)) {
    return(list(textes = textes_sortie, n_patterns = nrow(expressions_df), n_occurrences = 0L))
  }

  # Appliquer sans modification la fonction classique, dans le même ordre, aux documents candidats.
  remplacements <- appliquer_natif(textes[indices], expressions_df)
  textes_sortie[indices] <- remplacements$textes
  list(
    textes = textes_sortie,
    n_patterns = remplacements$n_patterns,
    n_occurrences = remplacements$n_occurrences
  )
}
