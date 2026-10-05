# Dictionnaires, spaCy, nettoyage et construction du DFM.
# Les fonctions sont extraites sans modification de leur comportement.

normaliser_add_expression_df_batch <- function(df) {
  if (is.list(df) && !is.data.frame(df)) {
    if (!length(df)) return(NULL)
    if (all(vapply(df, is.list, logical(1)))) {
      rows <- lapply(df, function(entry) {
        data.frame(
          dic_mot = as.character(entry$dic_mot %||% ""),
          dic_norm = as.character(entry$dic_norm %||% ""),
          dic_morpho = as.character(entry$dic_morpho %||% ""),
          stringsAsFactors = FALSE
        )
      })
      df <- do.call(rbind, rows)
    } else {
      df <- tryCatch(as.data.frame(df, stringsAsFactors = FALSE), error = function(e) NULL)
    }
  }
  if (is.null(df) || !is.data.frame(df)) return(NULL)
  noms <- names(df)
  noms <- gsub("^\ufeff", "", noms, perl = TRUE)
  names(df) <- noms
  if (!all(c("dic_mot", "dic_norm") %in% names(df))) return(NULL)
  if (!"dic_morpho" %in% names(df)) df$dic_morpho <- ""
  df <- df[, c("dic_mot", "dic_norm", "dic_morpho"), drop = FALSE]
  df$dic_mot[is.na(df$dic_mot)] <- ""
  df$dic_norm[is.na(df$dic_norm)] <- ""
  df$dic_morpho[is.na(df$dic_morpho)] <- ""
  df$dic_mot <- tolower(trimws(as.character(df$dic_mot)))
  df$dic_mot <- gsub("[’`´ʼʹ]", "'", df$dic_mot, perl = TRUE)
  df$dic_norm <- tolower(trimws(as.character(df$dic_norm)))
  df$dic_norm <- gsub("[’`´ʼʹ]", "'", df$dic_norm, perl = TRUE)
  df$dic_morpho <- trimws(as.character(df$dic_morpho))
  df <- df[nzchar(df$dic_mot) & nzchar(df$dic_norm), , drop = FALSE]
  df <- df[!duplicated(df$dic_mot), , drop = FALSE]
  df
}
lire_add_expression_depuis_fichier_batch <- function(path_in) {
  if (is.null(path_in) || !nzchar(path_in) || !file.exists(path_in)) return(NULL)

  lecteurs <- list(
    function() utils::read.csv2(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character()),
    function() utils::read.csv(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character(), sep = ","),
    function() utils::read.csv(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character(), sep = ";"),
    function() utils::read.delim(path_in, stringsAsFactors = FALSE, encoding = "UTF-8", na.strings = character(), sep = "\t")
  )

  for (lecteur in lecteurs) {
    df <- tryCatch(lecteur(), error = function(e) NULL)
    df_norm <- normaliser_add_expression_df_batch(df)
    if (!is.null(df_norm)) return(df_norm)
  }

  NULL
}
catalogue_dictionnaires <- function() {
  list(
    lexique_fr = list(fichier = "lexique_fr.csv", langue = "fr", libelle = "français", format = "csv2", auxiliaires = c("être", "etre")),
    lexique_en = list(fichier = "lexique_en.txt", langue = "en", libelle = "anglais", format = "tsv", auxiliaires = "be"),
    lexique_sp = list(fichier = "lexique_sp.txt", langue = "es", libelle = "espagnol", format = "tsv", auxiliaires = c("ser", "estar")),
    lexique_it = list(fichier = "lexique_it.txt", langue = "it", libelle = "italien", format = "tsv", auxiliaires = "essere"),
    spacy = list(fichier = NA_character_, langue = "xx", libelle = "spaCy", format = "spacy", auxiliaires = character(0))
  )
}

normaliser_source_dictionnaire <- function(source_dictionnaire) {
  source <- trimws(as.character(source_dictionnaire %||% "lexique_fr")[[1]])
  if (!source %in% names(catalogue_dictionnaires())) "lexique_fr" else source
}

infos_dictionnaire <- function(source_dictionnaire) {
  catalogue_dictionnaires()[[normaliser_source_dictionnaire(source_dictionnaire)]]
}

preparer_documents_spacy <- function(textes, ids_docs, config) {
  modele <- scalar_chr(config$spacy_model, "")
  if (!grepl("^[a-z]{2,3}_[a-z0-9_]+_(sm|md|lg|trf)$", modele)) {
    stop("spaCy : indiquez un modèle valide, par exemple en_core_web_md.")
  }
  python <- Sys.which("python3")
  if (!nzchar(python)) stop("spaCy : exécutable python3 introuvable.")
  script <- file.path(repo_root, "backend", "gestion_spacy.py")
  if (!file.exists(script)) stop(paste0("spaCy : module introuvable : ", script))

  input_file <- tempfile("iramuteq-spacy-input-", fileext = ".tsv")
  docs_file <- tempfile("iramuteq-spacy-docs-", fileext = ".tsv")
  lexicon_file <- tempfile("iramuteq-spacy-lexicon-", fileext = ".tsv")
  on.exit(unlink(c(input_file, docs_file, lexicon_file), force = TRUE), add = TRUE)
  utils::write.table(
    data.frame(doc_id = ids_docs, text = as.character(textes), stringsAsFactors = FALSE),
    input_file,
    sep = "\t",
    quote = TRUE,
    row.names = FALSE,
    fileEncoding = "UTF-8"
  )

  morpho_selection <- unique(toupper(trimws(as.character(unlist(config$pos_lexique_a_conserver, use.names = FALSE)))))
  pos_conserves <- morpho_selection[nzchar(morpho_selection) & morpho_selection != "AUTRE_FORME"]
  cache_key <- paste(
    "spacy",
    modele,
    unname(tools::md5sum(input_file)),
    scalar_bool(config$lexique_utiliser_lemmes, TRUE),
    scalar_bool(config$retirer_stopwords, FALSE),
    scalar_bool(config$supprimer_ponctuation, FALSE),
    scalar_bool(config$supprimer_chiffres, FALSE),
    scalar_bool(config$filtrage_morpho, FALSE),
    paste(sort(pos_conserves), collapse = ","),
    scalar_bool(config$morpho_conserver_hors_lexique, TRUE),
    sep = "::"
  )
  if (exists(cache_key, envir = .iramuteq_runtime_cache, inherits = FALSE)) {
    return(get(cache_key, envir = .iramuteq_runtime_cache, inherits = FALSE))
  }

  args <- c(
    script,
    "--input", input_file,
    "--output-docs", docs_file,
    "--output-lexicon", lexicon_file,
    "--model", modele,
    "--batch-size", as.character(scalar_int(config$spacy_batch_size, 64L, 1L))
  )
  if (scalar_bool(config$lexique_utiliser_lemmes, TRUE)) args <- c(args, "--lemmatize")
  if (scalar_bool(config$retirer_stopwords, FALSE)) args <- c(args, "--remove-stopwords")
  if (scalar_bool(config$supprimer_ponctuation, FALSE)) args <- c(args, "--remove-punct")
  if (scalar_bool(config$supprimer_chiffres, FALSE)) args <- c(args, "--remove-numbers")
  if (scalar_bool(config$filtrage_morpho, FALSE)) {
    args <- c(args, "--filter-morpho", "--keep-pos", paste(pos_conserves, collapse = ","))
    if (scalar_bool(config$morpho_conserver_hors_lexique, TRUE) || "AUTRE_FORME" %in% morpho_selection) {
      args <- c(args, "--keep-unknown")
    }
  }

  sortie <- suppressWarnings(system2(python, args = args, stdout = TRUE, stderr = TRUE))
  statut <- attr(sortie, "status") %||% 0L
  if (!identical(as.integer(statut), 0L) || !file.exists(docs_file) || !file.exists(lexicon_file)) {
    stop(paste0("spaCy : échec du prétraitement. ", paste(sortie, collapse = " ")))
  }
  docs <- utils::read.delim(docs_file, sep = "\t", quote = "\"", stringsAsFactors = FALSE, encoding = "UTF-8")
  lexique <- utils::read.delim(lexicon_file, sep = "\t", quote = "\"", stringsAsFactors = FALSE, encoding = "UTF-8")
  idx <- match(ids_docs, as.character(docs$doc_id))
  textes_prepares <- as.character(docs$text[idx])
  textes_prepares[is.na(textes_prepares)] <- ""
  names(textes_prepares) <- ids_docs
  resultat <- list(textes = textes_prepares, lexique = lexique, modele = modele)
  assign(cache_key, resultat, envir = .iramuteq_runtime_cache)
  resultat
}

charger_lexique <- function(repo_root, source_dictionnaire = "lexique_fr") {
  source_dictionnaire <- normaliser_source_dictionnaire(source_dictionnaire)
  infos <- infos_dictionnaire(source_dictionnaire)
  path <- file.path(repo_root, "dictionnaires", infos$fichier)
  if (!file.exists(path)) {
    stop(paste0("Fichier lexique introuvable: ", path))
  }

  cache_key <- paste0(source_dictionnaire, "::", normalizePath(path, winslash = "/", mustWork = TRUE))
  if (exists(cache_key, envir = .iramuteq_runtime_cache, inherits = FALSE)) {
    return(get(cache_key, envir = .iramuteq_runtime_cache, inherits = FALSE))
  }

  lexique <- if (identical(infos$format, "csv2")) {
    utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8")
  } else {
    lexique_lines <- readLines(path, encoding = "UTF-8", warn = FALSE)
    lexique_connection <- textConnection(lexique_lines)
    on.exit(close(lexique_connection), add = TRUE)
    utils::read.delim(
      lexique_connection,
      header = FALSE,
      sep = "\t",
      quote = "\"",
      comment.char = "",
      col.names = c("c_mot", "c_lemme", "c_morpho"),
      stringsAsFactors = FALSE
    )
  }
  colonnes_requises <- c("c_mot", "c_lemme", "c_morpho")
  if (!all(colonnes_requises %in% names(lexique))) {
    stop(paste0("Le fichier ", infos$fichier, " doit contenir trois colonnes: mot, lemme et morphologie."))
  }

  lexique$c_mot <- as.character(lexique$c_mot)
  lexique$c_lemme <- as.character(lexique$c_lemme)
  Encoding(lexique$c_mot) <- "UTF-8"
  Encoding(lexique$c_lemme) <- "UTF-8"
  lexique$c_mot <- sub("^\xef\xbb\xbf", "", lexique$c_mot, useBytes = TRUE)
  lexique$c_mot <- tolower(trimws(lexique$c_mot))
  lexique$c_lemme <- tolower(trimws(lexique$c_lemme))
  lexique$c_morpho <- trimws(as.character(lexique$c_morpho))
  lexique <- lexique[nzchar(lexique$c_mot) & nzchar(lexique$c_lemme), c("c_mot", "c_lemme", "c_morpho"), drop = FALSE]
  lexique <- lexique[!duplicated(lexique$c_mot), , drop = FALSE]
  assign(cache_key, lexique, envir = .iramuteq_runtime_cache)
  lexique
}

charger_expressions <- function(repo_root, source_dictionnaire = "lexique_fr") {
  source_dictionnaire <- normaliser_source_dictionnaire(source_dictionnaire)
  chemins_candidats <- switch(
    source_dictionnaire,
    lexique_fr = c(
      file.path(repo_root, "dictionnaires", "expression_fr.csv"),
      file.path(repo_root, "dictionnaires", "expressions.csv")
    ),
    lexique_en = file.path(repo_root, "dictionnaires", "expression_en.txt"),
    character(0)
  )
  if (!length(chemins_candidats)) {
    return(data.frame(dic_mot = character(0), dic_norm = character(0), stringsAsFactors = FALSE))
  }
  path <- chemins_candidats[file.exists(chemins_candidats)][1]
  if (is.na(path) || !nzchar(path)) {
    stop(
      paste0(
        "Fichier dictionnaire d'expressions introuvable. Chemins testés: ",
        paste(chemins_candidats, collapse = " | ")
      )
    )
  }

  cache_key <- paste0("expressions::", source_dictionnaire, "::", normalizePath(path, winslash = "/", mustWork = TRUE))
  if (exists(cache_key, envir = .iramuteq_runtime_cache, inherits = FALSE)) {
    return(get(cache_key, envir = .iramuteq_runtime_cache, inherits = FALSE))
  }

  expressions <- if (identical(source_dictionnaire, "lexique_fr")) {
    utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8")
  } else {
    utils::read.delim(
      path,
      header = FALSE,
      sep = "\t",
      quote = "",
      comment.char = "",
      col.names = c("dic_mot", "dic_norm"),
      stringsAsFactors = FALSE
    )
  }
  colonnes_requises <- c("dic_mot", "dic_norm")
  if (!all(colonnes_requises %in% names(expressions))) {
    stop(paste0("Le fichier d'expressions ", basename(path), " doit contenir les colonnes dic_mot et dic_norm."))
  }

  expressions$dic_mot <- tolower(trimws(as.character(expressions$dic_mot)))
  expressions$dic_mot <- gsub("[’`´ʼʹ]", "'", expressions$dic_mot, perl = TRUE)
  expressions$dic_norm <- tolower(trimws(as.character(expressions$dic_norm)))
  expressions <- expressions[nzchar(expressions$dic_mot) & nzchar(expressions$dic_norm), c("dic_mot", "dic_norm"), drop = FALSE]
  expressions <- expressions[!duplicated(expressions$dic_mot), , drop = FALSE]
  attr(expressions, "source_file") <- path
  assign(cache_key, expressions, envir = .iramuteq_runtime_cache)
  expressions
}

appliquer_dictionnaire_expressions <- function(textes, expressions_df) {
  if (is.null(textes) || length(textes) == 0 ||
      is.null(expressions_df) || !is.data.frame(expressions_df) || nrow(expressions_df) == 0) {
    return(list(textes = as.character(textes), n_patterns = 0L, n_occurrences = 0L))
  }
  textes_out <- as.character(textes)
  textes_out <- gsub("[’`´ʼʹ]", "'", textes_out, perl = TRUE)
  dic <- expressions_df
  ord <- order(nchar(dic$dic_mot), decreasing = TRUE)
  dic <- dic[ord, , drop = FALSE]
  n_occurrences <- 0L

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

  for (i in seq_len(nrow(dic))) {
    motif <- dic$dic_mot[[i]]
    remplacement <- dic$dic_norm[[i]]
    motif_echappe <- construire_motif_regex_expression(motif)
    regex <- paste0("(?i)(?<![[:alnum:]_])", motif_echappe, "(?![[:alnum:]_])")
    matches <- gregexpr(regex, textes_out, perl = TRUE)
    captures <- regmatches(textes_out, matches)
    captures_count <- sum(lengths(captures), na.rm = TRUE)
    if (captures_count > 0L) {
      remplacements <- lapply(captures, function(vals) {
        if (!length(vals)) return(character(0))
        rep(remplacement, length(vals))
      })
      regmatches(textes_out, matches) <- remplacements
      n_occurrences <- n_occurrences + as.integer(captures_count)
    }
    if (i < nrow(dic) && (i %% 250L) == 0L) {
      progress_pct <- 24L + as.integer(floor((i / nrow(dic)) * 3))
      log_info(
        paste0(
          "Application du dictionnaire d'expressions : ",
          i,
          "/",
          nrow(dic),
          " entrées traitées (",
          n_occurrences,
          " remplacement(s) détecté(s))."
        ),
        progress = progress_pct
      )
    }
  }
  list(textes = textes_out, n_patterns = nrow(dic), n_occurrences = as.integer(n_occurrences))
}

preparer_pipeline_chd <- function(segmented_corpus, config) {
  ids_docs <- as.character(quanteda::docnames(segmented_corpus))
  textes_orig <- as.character(segmented_corpus)
  source_dictionnaire <- normaliser_source_dictionnaire(scalar_chr(config$source_dictionnaire, "lexique_fr"))
  infos_langue <- infos_dictionnaire(source_dictionnaire)
  utiliser_spacy <- identical(source_dictionnaire, "spacy")
  if (isTRUE(utiliser_spacy)) {
    infos_langue$langue <- sub("_.*$", "", scalar_chr(config$spacy_model, "xx"))
  }
  expressions_actives_df <- NULL

  if (scalar_bool(config$expression_utiliser_dictionnaire, FALSE)) {
    expression_base_df <- charger_expressions(repo_root, source_dictionnaire)
    expression_base_df$source_expr <- "base"
    expressions_actives_df <- expression_base_df
    if (nrow(expression_base_df) > 0) {
      log_info(
        paste0(
          "Dictionnaire d'expressions ",
          infos_langue$libelle,
          " chargé : ",
          nrow(expression_base_df),
          " entrées (source=",
          attr(expression_base_df, "source_file") %||% "inconnue",
          ")."
        ),
        progress = 24
      )
    } else {
      log_info(
        paste0("Aucun dictionnaire d'expressions de base n'est fourni pour la langue ", infos_langue$libelle, "."),
        progress = 24
      )
    }

    add_expression_actif <- scalar_bool(config$utiliser_add_expression, FALSE) && identical(source_dictionnaire, "lexique_fr")
    expr_session_df <- NULL
    if (isTRUE(add_expression_actif) && !is.null(config$expression_annotations)) {
      expr_session_df <- normaliser_add_expression_df_batch(config$expression_annotations)
    }

    if (isTRUE(add_expression_actif) && (is.null(expr_session_df) || !nrow(expr_session_df))) {
      add_expression_path <- Sys.getenv("IRAMUTEQ_ADD_EXPRESSION_PATH", unset = "")
      if (!nzchar(add_expression_path)) {
        add_expression_path <- file.path(repo_root, "dictionnaires", "add_expression_fr.csv")
      }
      expr_session_df <- lire_add_expression_depuis_fichier_batch(add_expression_path)
      if (!is.null(expr_session_df) && nrow(expr_session_df) > 0) {
        log_info(
          paste0(
            "add_expression_fr.csv rechargé depuis le disque : ",
            nrow(expr_session_df),
            " entrées (",
            add_expression_path,
            ")."
          ),
          progress = 25
        )
      }
    }

    if (isTRUE(add_expression_actif) && !is.null(expr_session_df) && nrow(expr_session_df) > 0) {
      log_info(paste0("add_expression_fr.csv chargé : ", nrow(expr_session_df), " entrées utilisateur."), progress = 25)
      expr_session_df$source_expr <- "user"
      deja_base <- expr_session_df$dic_mot %in% expression_base_df$dic_mot
      expr_session_ajouts <- expr_session_df[!deja_base, c("dic_mot", "dic_norm", "source_expr"), drop = FALSE]
      expressions_actives_df <- rbind(
        expression_base_df[, c("dic_mot", "dic_norm", "source_expr"), drop = FALSE],
        expr_session_ajouts
      )
      expressions_actives_df <- expressions_actives_df[!duplicated(expressions_actives_df$dic_mot), , drop = FALSE]
      log_info(
        paste0(
          "Dictionnaire utilisateur ajouté au dictionnaire de base : +",
          nrow(expr_session_ajouts),
          " nouvelle(s) entrée(s) (",
          sum(deja_base),
          " déjà présentes ignorées)."
        ),
        progress = 26
      )
    } else if (isTRUE(add_expression_actif)) {
      log_info("add_expression_fr.csv active mais vide/invalide ; utilisation du dictionnaire de base uniquement.", progress = 25)
    } else {
      log_info("add_expression_fr.csv non activé ; utilisation du dictionnaire de base uniquement.", progress = 25)
    }

    log_info(
      paste0(
        "Dictionnaire d'expressions chargé : ",
        nrow(expressions_actives_df),
        " entrées actives."
      ),
      progress = 27
    )

    if (nrow(expressions_actives_df) > 0) {
      remplacements_expr <- appliquer_dictionnaire_expressions(textes_orig, expressions_actives_df)
      textes_orig <- remplacements_expr$textes
      log_info(
        paste0(
          "Dictionnaire d'expressions appliqué avant analyse : ",
          remplacements_expr$n_occurrences,
          " occurrence(s) remplacée(s) via ",
          remplacements_expr$n_patterns,
          " entrée(s) du dictionnaire."
        ),
        progress = 28
      )
    }
  } else {
    log_info("Dictionnaire d'expressions désactivé (expression_utiliser_dictionnaire=0).", progress = 24)
  }

  log_info("Préparation du texte (nettoyage / minuscules).", progress = 30)
  textes_nettoyes <- appliquer_nettoyage_iramuteq(
    textes = textes_orig,
    activer_nettoyage = scalar_bool(config$nettoyage_caracteres, TRUE),
    forcer_minuscules = TRUE,
    supprimer_chiffres = scalar_bool(config$supprimer_chiffres, FALSE),
    supprimer_apostrophes = scalar_bool(config$supprimer_apostrophes, TRUE),
    remplacer_tirets_espaces = scalar_bool(config$remplacer_tirets_espaces, FALSE)
  )
  textes_chd <- textes_nettoyes
  names(textes_chd) <- ids_docs

  spacy_pipeline <- NULL
  textes_tok <- textes_chd
  if (isTRUE(utiliser_spacy)) {
    log_info(paste0("spaCy : lancement du modèle ", scalar_chr(config$spacy_model, ""), "."), progress = 31)
    spacy_pipeline <- preparer_documents_spacy(textes_chd, ids_docs, config)
    textes_tok <- spacy_pipeline$textes
    log_info(
      paste0("spaCy : prétraitement terminé avec ", spacy_pipeline$modele, " ; ", nrow(spacy_pipeline$lexique), " formes observées."),
      progress = 32
    )
  } else if (scalar_bool(config$retirer_stopwords, FALSE) && identical(infos_langue$langue, "fr")) {
    textes_tok <- gsub(
      pattern = "(?i)\\b(?:[cdjlmnst]|qu)['’`´ʼʹ](?=[[:alpha:]])",
      replacement = "",
      x = textes_tok,
      perl = TRUE
    )
  }

  log_info("IRaMuTeQ-lite : préparation du texte exécutée via iramuteqlite/nettoyage_iramuteq.R", progress = 32)
  log_info(
    paste0(
      "Diagnostic du pipeline : dictionnaire=",
      source_dictionnaire,
      " | langue=",
      infos_langue$langue,
      " | filtrage_morpho=",
      ifelse(scalar_bool(config$filtrage_morpho, FALSE), "1", "0"),
      " | inclure_autre_forme=",
      ifelse(
        scalar_bool(config$morpho_conserver_hors_lexique, TRUE) ||
          ("AUTRE_FORME" %in% toupper(trimws(as.character(unlist(config$pos_lexique_a_conserver, use.names = FALSE))))),
        "1",
        "0"
      ),
      " | retirer_stopwords=",
      ifelse(scalar_bool(config$retirer_stopwords, FALSE), "1", "0"),
      " | supprimer_ponctuation=",
      ifelse(scalar_bool(config$supprimer_ponctuation, FALSE), "1", "0"),
      " | segmenter_sur_ponctuation_forte=",
      ifelse(scalar_bool(config$segmenter_sur_ponctuation_forte, TRUE), "1", "0"),
      " | supprimer_chiffres=",
      ifelse(scalar_bool(config$supprimer_chiffres, FALSE), "1", "0"),
      " | supprimer_apostrophes=",
      ifelse(scalar_bool(config$supprimer_apostrophes, TRUE), "1", "0"),
      " | remplacer_tirets_espaces=",
      ifelse(scalar_bool(config$remplacer_tirets_espaces, FALSE), "1", "0"),
      " | nettoyage_caracteres=",
      ifelse(scalar_bool(config$nettoyage_caracteres, TRUE), "1", "0")
    ),
    progress = 33
  )

  tok <- quanteda::tokens(
    textes_tok,
    remove_punct = scalar_bool(config$supprimer_ponctuation, FALSE),
    remove_numbers = scalar_bool(config$supprimer_chiffres, FALSE)
  )
  quanteda::docnames(tok) <- ids_docs
  tok <- quanteda::tokens_tolower(tok)

  lexique_df <- if (isTRUE(utiliser_spacy)) spacy_pipeline$lexique else NULL
  if (!isTRUE(utiliser_spacy) && (scalar_bool(config$lexique_utiliser_lemmes, TRUE) || scalar_bool(config$filtrage_morpho, FALSE))) {
    lexique_df <- charger_lexique(repo_root, source_dictionnaire)
    log_info(
      paste0("Lexique ", infos_langue$libelle, " chargé : ", nrow(lexique_df), " entrées."),
      progress = 34
    )
  }

  if (!isTRUE(utiliser_spacy) && scalar_bool(config$lexique_utiliser_lemmes, TRUE) && !is.null(lexique_df)) {
    vocabulaire <- quanteda::featnames(quanteda::dfm(tok))
    idx <- match(vocabulaire, lexique_df$c_mot)
    a_remplacer <- !is.na(idx)
    if (any(a_remplacer)) {
      motifs <- vocabulaire[a_remplacer]
      remplacements <- lexique_df$c_lemme[idx[a_remplacer]]
      tok <- quanteda::tokens_replace(
        tok,
        pattern = motifs,
        replacement = remplacements,
        valuetype = "fixed",
        case_insensitive = FALSE
      )
      log_info(
        paste0("Lemmatisation ", source_dictionnaire, " appliquée sur ", length(motifs), " formes du vocabulaire."),
        progress = 34
      )
    }
  }

  if (!isTRUE(utiliser_spacy) && scalar_bool(config$retirer_stopwords, FALSE)) {
    stop_langue <- quanteda::stopwords(infos_langue$langue)
    n_feat_avant_stop <- quanteda::nfeat(quanteda::dfm(tok))
    tok <- quanteda::tokens_remove(tok, pattern = stop_langue, valuetype = "fixed", case_insensitive = TRUE)
    n_feat_apres_stop <- quanteda::nfeat(quanteda::dfm(tok))
    log_info(
      paste0(
        "Filtrage des stopwords quanteda(",
        infos_langue$langue,
        ") appliqué : ",
        n_feat_avant_stop,
        " -> ",
        n_feat_apres_stop,
        " termes uniques."
      ),
      progress = 36
    )
  }

  dfm_obj <- quanteda::dfm(tok)
  quanteda::docnames(dfm_obj) <- ids_docs

  source_dict_chd <- source_dictionnaire
  if (!isTRUE(utiliser_spacy) && scalar_bool(config$filtrage_morpho, FALSE)) {
    morpho_selection <- unique(toupper(trimws(as.character(unlist(config$pos_lexique_a_conserver, use.names = FALSE)))))
    inclure_autre_forme <- scalar_bool(config$morpho_conserver_hors_lexique, TRUE) || ("AUTRE_FORME" %in% morpho_selection)
    if (isTRUE(inclure_autre_forme) && !("AUTRE_FORME" %in% morpho_selection)) {
      morpho_selection <- c(morpho_selection, "AUTRE_FORME")
    }
    morpho_selection_lexique <- setdiff(morpho_selection, "AUTRE_FORME")

    if (length(morpho_selection_lexique) > 0 || isTRUE(inclure_autre_forme)) {
      lex <- lexique_df
      lex_morpho <- toupper(trimws(as.character(lex$c_morpho)))
      exclure_etre_verbe <- scalar_bool(config$morpho_exclure_etre_verbe, FALSE)
      categorie_verbe_selectionnee <- any(morpho_selection_lexique %in% c("VER", "VERB", "AUX", "VER_SUP"))

      idx <- nzchar(lex_morpho) & lex_morpho %in% morpho_selection_lexique
      termes_autorises <- unique(c(
        tolower(trimws(as.character(lex$c_mot[idx]))),
        tolower(trimws(as.character(lex$c_lemme[idx])))
      ))
      termes_autorises <- termes_autorises[nzchar(termes_autorises)]
      if (isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee)) {
        termes_autorises <- setdiff(termes_autorises, infos_langue$auxiliaires)
      }

      toutes_formes_lexique <- unique(c(
        tolower(trimws(as.character(lex$c_mot))),
        tolower(trimws(as.character(lex$c_lemme)))
      ))
      toutes_formes_lexique <- toutes_formes_lexique[nzchar(toutes_formes_lexique)]

      featnames_dfm <- quanteda::featnames(dfm_obj)
      featnames_norm <- tolower(trimws(as.character(featnames_dfm)))
      featnames_core <- gsub("^[[:punct:]]+|[[:punct:]]+$", "", featnames_norm, perl = TRUE)
      is_punct_feature <- !nzchar(featnames_core)

      in_selection <- (featnames_norm %in% termes_autorises) | (featnames_core %in% termes_autorises)
      in_lexique <- (featnames_norm %in% toutes_formes_lexique) | (featnames_core %in% toutes_formes_lexique)

      keep_mask <- in_selection
      if (isTRUE(inclure_autre_forme)) {
        keep_mask <- keep_mask | (!in_lexique & !is_punct_feature)
      }

      pattern_keep <- featnames_dfm[keep_mask]
      dfm_obj <- quanteda::dfm_select(
        dfm_obj,
        pattern = pattern_keep,
        selection = "keep",
        valuetype = "fixed",
        case_insensitive = FALSE
      )
      log_info("Filtrage morphosyntaxique appliqué.", progress = 38)
    } else {
      log_info("Filtrage morphosyntaxique activé sans catégorie c_morpho sélectionnée : étape ignorée.", progress = 38)
    }
  }

  dfm_stats <- dfm_obj
  freq_termes <- sort(as.numeric(Matrix::colSums(dfm_stats)), decreasing = TRUE)
  freq_termes <- freq_termes[is.finite(freq_termes) & !is.na(freq_termes) & freq_termes > 0]
  zipf_df <- if (length(freq_termes) >= 2) {
    rang <- seq_along(freq_termes)
    fit <- tryCatch(stats::lm(log(freq_termes) ~ log(rang)), error = function(e) NULL)
    pred <- if (is.null(fit)) rep(NA_real_, length(freq_termes)) else as.numeric(exp(stats::predict(fit)))
    data.frame(
      rang = rang,
      frequence = freq_termes,
      pred = pred,
      log_rang = log(rang),
      log_frequence = log(freq_termes),
      log_pred = ifelse(is.na(pred), NA_real_, log(pred)),
      stringsAsFactors = FALSE
    )
  } else {
    NULL
  }

  dfm_obj <- quanteda::dfm_trim(dfm_obj, min_docfreq = scalar_int(config$min_docfreq, 3L, 1L))
  log_info(
    paste0(
      "min_docfreq appliqué (IRaMuTeQ-lite) = ",
      scalar_int(config$min_docfreq, 3L, 1L),
      " (manuel)."
    ),
    progress = 40
  )
  included_segments <- as.character(quanteda::docnames(dfm_obj))
  included_segments <- included_segments[!is.na(included_segments) & nzchar(included_segments)]
  included_segments <- unique(included_segments)
  filtered_corpus <- segmented_corpus[included_segments]
  tok <- tok[included_segments]

  segment_source <- as.character(quanteda::docnames(dfm_obj))
  if ("segment_source" %in% names(quanteda::docvars(filtered_corpus))) {
    ss <- as.character(quanteda::docvars(filtered_corpus)$segment_source)
    idx_ss <- match(as.character(quanteda::docnames(dfm_obj)), as.character(quanteda::docnames(filtered_corpus)))
    ss_aligne <- ss[idx_ss]
    ok_ss <- !is.na(ss_aligne) & nzchar(trimws(ss_aligne))
    segment_source[ok_ss] <- ss_aligne[ok_ss]
  }
  quanteda::docvars(dfm_obj, "segment_source") <- segment_source

  cleaned <- supprimer_docs_vides_dfm(dfm_obj, filtered_corpus = filtered_corpus, tok = tok)
  if (cleaned$nb_vides > 0) {
    log_info(paste0("Segments vides supprimés du DFM : ", cleaned$nb_vides, "."))
  }
  textes_indexation <- vapply(as.list(cleaned$tok), function(x) paste(x, collapse = " "), FUN.VALUE = character(1))
  names(textes_indexation) <- as.character(quanteda::docnames(cleaned$dfm_obj))
  log_info(
    paste0(
      "Après suppression des segments vides : ",
      quanteda::ndoc(cleaned$dfm_obj),
      " docs ; ",
      quanteda::nfeat(cleaned$dfm_obj),
      " termes."
    ),
    progress = 41
  )

  list(
    filtered_corpus = cleaned$filtered_corpus,
    tok = cleaned$tok,
    dfm_obj = cleaned$dfm_obj,
    textes_indexation = textes_indexation,
    lexique_df = lexique_df,
    lexique_fr_df = lexique_df,
    source_dictionnaire = source_dictionnaire,
    langue = infos_langue$langue,
    expressions_actives_df = expressions_actives_df,
    corpus_stats = list(
      n_tokens = sum(freq_termes),
      n_formes = length(freq_termes),
      n_hapax = if (length(freq_termes)) sum(freq_termes == 1) else 0L,
      zipf = if (is.null(zipf_df)) NULL else utils::head(zipf_df, 160L)
    )
  )
}
