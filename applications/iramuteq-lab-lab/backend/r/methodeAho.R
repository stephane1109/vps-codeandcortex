# Indexation Aho-Corasick des expressions et substitutions selon les règles natives.
# La CHD, les dictionnaires et le traitement classique ne sont pas modifiés.

appliquer_dictionnaire_expressions_aho <- function(textes, expressions_df, script_python, appliquer_natif) {
  if (!is.function(appliquer_natif)) {
    stop("Aho-Corasick : fonction de substitution native indisponible.")
  }
  if (is.null(textes) || length(textes) == 0L ||
      is.null(expressions_df) || !is.data.frame(expressions_df) || nrow(expressions_df) == 0L) {
    return(appliquer_natif(textes, expressions_df))
  }
  if (!file.exists(script_python)) {
    stop("Aho-Corasick : module Python introuvable : ", script_python)
  }
  python <- Sys.which("python3")
  if (!nzchar(python)) {
    stop("Aho-Corasick : Python 3 indisponible.")
  }
  if (!requireNamespace("jsonlite", quietly = TRUE)) {
    stop("Aho-Corasick : le package jsonlite est requis.")
  }

  # Reprendre strictement le même ordre que la fonction de substitution classique.
  dic <- expressions_df
  ord <- order(nchar(dic$dic_mot), decreasing = TRUE)
  dic <- dic[ord, , drop = FALSE]

  # Appliquer sur tous les documents la normalisation initiale du moteur classique.
  textes_sortie <- as.character(textes)
  textes_sortie <- gsub(paste0("[’", intToUtf8(96L), "´ʼʹ]"), "'", textes_sortie, perl = TRUE)

  fichier_entree <- tempfile("methode_aho_entree_", fileext = ".json")
  fichier_sortie <- tempfile("methode_aho_sortie_", fileext = ".json")
  fichier_erreurs <- tempfile("methode_aho_erreurs_", fileext = ".log")
  on.exit(unlink(c(fichier_entree, fichier_sortie, fichier_erreurs)), add = TRUE)

  jsonlite::write_json(
    list(textes = textes_sortie, motifs = as.character(dic$dic_mot)),
    path = fichier_entree,
    auto_unbox = FALSE,
    na = "null"
  )
  log_info(
    paste0("Aho-Corasick : indexation de ", length(textes_sortie),
           " documents et ", nrow(dic), " expressions."),
    progress = 27
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
    stop("Aho-Corasick : indexation impossible. ", paste(erreurs, collapse = " "))
  }

  resultat <- jsonlite::fromJSON(fichier_sortie, simplifyVector = FALSE)
  candidats_par_expression <- resultat$candidats
  if (is.null(candidats_par_expression)) {
    stop("Aho-Corasick : index des expressions absent.")
  }
  log_info("Aho-Corasick : indexation terminée ; substitutions natives ciblées.", progress = 27)

  # Reproduire les expressions régulières utilisées par la méthode native.
  construire_motif_regex_expression <- function(motif) {
    accent_map <- list(
      a = "aàáâäãå",
      e = "eèéêë",
      i = "iìíîï",
      o = "oòóôöõø",
      u = "uùúûü",
      y = "yÿ",
      c = "cç",
      n = "nñ"
    )
    chars <- strsplit(motif, "", fixed = TRUE)[[1]]
    out <- character(length(chars))
    for (k in seq_along(chars)) {
      ch <- chars[[k]]
      ch_l <- tolower(ch)
      if (ch == "'") {
        out[[k]] <- "['’`´ʼʹ]"
      } else if (ch_l %in% names(accent_map)) {
        out[[k]] <- paste0("[", accent_map[[ch_l]], "]")
      } else if (ch_l == "œ") {
        out[[k]] <- "(?:œ|oe)"
      } else {
        regex_chars <- c("\\", "^", "$", ".", "|", "?", "*", "+", "(", ")", "[", "]", "{", "}")
        out[[k]] <- if (ch %in% regex_chars) paste0("\\", ch) else ch
      }
    }
    paste0(out, collapse = "")
  }

  # Un document déjà modifié reste candidat pour les expressions suivantes.
  # Cela préserve les correspondances créées par les substitutions antérieures.
  documents_modifies <- integer(0)
  nombre_occurrences <- 0L

  for (i in seq_len(nrow(dic))) {
    indices_initiaux <- candidats_par_expression[[as.character(i - 1L)]]
    indices_initiaux <- if (is.null(indices_initiaux)) integer(0) else {
      as.integer(unlist(indices_initiaux, use.names = FALSE)) + 1L
    }
    if (anyNA(indices_initiaux) ||
        any(indices_initiaux < 1L | indices_initiaux > length(textes_sortie))) {
      stop("Aho-Corasick : index documentaire invalide à l'expression ", i, ".")
    }
    indices_a_verifier <- sort(unique(c(indices_initiaux, documents_modifies)))

    if (length(indices_a_verifier)) {
      motif <- dic$dic_mot[[i]]
      remplacement <- dic$dic_norm[[i]]
      motif_echappe <- construire_motif_regex_expression(motif)
      regex <- paste0("(?i)(?<![[:alnum:]_])", motif_echappe, "(?![[:alnum:]_])")
      textes_a_verifier <- textes_sortie[indices_a_verifier]
      matches <- gregexpr(regex, textes_a_verifier, perl = TRUE)
      captures <- regmatches(textes_a_verifier, matches)
      captures_count <- sum(lengths(captures), na.rm = TRUE)

      if (captures_count > 0L) {
        remplacements <- lapply(captures, function(vals) {
          if (!length(vals)) return(character(0))
          rep(remplacement, length(vals))
        })
        regmatches(textes_a_verifier, matches) <- remplacements
        textes_sortie[indices_a_verifier] <- textes_a_verifier
        nouveaux_modifies <- indices_a_verifier[lengths(captures) > 0L]
        documents_modifies <- union(documents_modifies, nouveaux_modifies)
        nombre_occurrences <- nombre_occurrences + as.integer(captures_count)
      }
    }

    if (i < nrow(dic) && (i %% 250L) == 0L) {
      progress_pct <- 24L + as.integer(floor((i / nrow(dic)) * 3))
      log_info(
        paste0(
          "Application du dictionnaire d'expressions : ",
          i, "/", nrow(dic), " entrées traitées (",
          nombre_occurrences, " remplacement(s) détecté(s))."
        ),
        progress = progress_pct
      )
    }
  }

  list(
    textes = textes_sortie,
    n_patterns = nrow(dic),
    n_occurrences = as.integer(nombre_occurrences)
  )
}
