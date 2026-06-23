if (!exists("%||%", mode = "function")) {
  `%||%` <- function(x, y) {
    if (is.null(x) || length(x) == 0) y else x
  }
}

selectionner_variable_suivi_sante <- function(docvars_df, variable_suivi = NULL) {
  if (is.null(docvars_df) || !is.data.frame(docvars_df) || !nrow(docvars_df)) {
    return(NULL)
  }

  colonnes_etoilees <- names(docvars_df)[startsWith(names(docvars_df), "*")]
  if (!length(colonnes_etoilees)) {
    return(NULL)
  }

  has_levels <- function(col) {
    vals <- trimws(as.character(docvars_df[[col]]))
    vals <- vals[!is.na(vals) & nzchar(vals)]
    length(unique(vals)) >= 2L
  }

  if (!is.null(variable_suivi) && nzchar(as.character(variable_suivi))) {
    candidate <- as.character(variable_suivi)[[1]]
    if (!startsWith(candidate, "*")) candidate <- paste0("*", candidate)
    if (candidate %in% colonnes_etoilees && has_levels(candidate)) {
      return(candidate)
    }
  }

  priorites <- c("*seance", "*date", "*mois", "*annee", "*phase", "*temps")
  for (candidate in priorites) {
    if (candidate %in% colonnes_etoilees && has_levels(candidate)) {
      return(candidate)
    }
  }

  for (candidate in colonnes_etoilees) {
    if (has_levels(candidate)) {
      return(candidate)
    }
  }

  NULL
}

selectionner_variable_filtre_sante <- function(docvars_df, variable_filtre = NULL) {
  if (is.null(docvars_df) || !is.data.frame(docvars_df) || !nrow(docvars_df)) {
    return(NULL)
  }

  if (is.null(variable_filtre) || !nzchar(as.character(variable_filtre))) {
    return(NULL)
  }

  candidate <- as.character(variable_filtre)[[1]]
  if (!startsWith(candidate, "*")) candidate <- paste0("*", candidate)
  if (!candidate %in% names(docvars_df)) {
    return(NULL)
  }

  vals <- trimws(as.character(docvars_df[[candidate]]))
  vals <- vals[!is.na(vals) & nzchar(vals)]
  if (!length(vals)) {
    return(NULL)
  }

  candidate
}

normaliser_ordre_suivi_sante <- function(ordre = "asc") {
  ordre_chr <- tolower(trimws(as.character(ordre %||% "asc")))
  if (!ordre_chr %in% c("asc", "desc")) "asc" else ordre_chr
}

normaliser_unite_lexicale_sante <- function(value = "unigramme") {
  x <- tolower(trimws(as.character(value %||% "unigramme")))
  x <- iconv(x, from = "", to = "ASCII//TRANSLIT")
  x[is.na(x)] <- "unigramme"
  x <- gsub("[^a-z0-9]+", "", x)

  if (x %in% c("bigramme", "bigrammes", "bigram", "2gram", "2grammes")) {
    return("bigramme")
  }

  "unigramme"
}

normaliser_couche_analyse_sante <- function(value = "lexicale_brute") {
  x <- tolower(trimws(as.character(value %||% "lexicale_brute")))
  x <- iconv(x, from = "", to = "ASCII//TRANSLIT")
  x[is.na(x)] <- "lexicale_brute"
  x <- gsub("[^a-z0-9]+", "", x)

  if (x %in% c("emotionnelle", "emotion", "emotionnel", "emotions")) {
    return("emotionnelle")
  }

  "lexicale_brute"
}

normaliser_lexique_emotionnel_sante <- function(value = "feel") {
  x <- tolower(trimws(as.character(value %||% "feel")))
  x <- iconv(x, from = "", to = "ASCII//TRANSLIT")
  x[is.na(x)] <- "feel"
  x <- gsub("[^a-z0-9]+", "", x)

  if (x %in% c("nrc", "nrcemotion", "nrcexicon", "nrcfr")) {
    return("nrc")
  }

  "feel"
}

obtenir_repo_root_sante <- function() {
  if (exists("repo_root", inherits = TRUE)) {
    return(get("repo_root", inherits = TRUE))
  }

  normalizePath(getwd(), winslash = "/", mustWork = FALSE)
}

normaliser_nom_colonne_sante <- function(x) {
  y <- tolower(iconv(trimws(as.character(x %||% "")), from = "", to = "ASCII//TRANSLIT"))
  y[is.na(y)] <- ""
  gsub("[^a-z0-9]+", "_", y)
}

normaliser_nom_emotion_sante <- function(x) {
  key <- tolower(iconv(trimws(as.character(x %||% "")), from = "", to = "ASCII//TRANSLIT"))
  key[is.na(key)] <- ""
  key <- gsub("[^a-z0-9]+", "", key)

  alias <- c(
    joie = "joie",
    joy = "joie",
    happiness = "joie",
    plaisir = "joie",
    tristesse = "tristesse",
    sadness = "tristesse",
    sad = "tristesse",
    peur = "peur",
    fear = "peur",
    anxiete = "anxiete",
    anxiety = "anxiete",
    colere = "colere",
    anger = "colere",
    degout = "degout",
    disgust = "degout",
    surprise = "surprise",
    trust = "confiance",
    confiance = "confiance",
    anticipation = "anticipation",
    honte = "honte",
    shame = "honte",
    culpabilite = "culpabilite",
    guilt = "culpabilite",
    apaisement = "apaisement",
    calm = "apaisement",
    serenity = "apaisement",
    positive = "positive",
    positif = "positive",
    negative = "negative",
    negatif = "negative"
  )

  mapped <- unname(alias[key])
  if (length(mapped) && !is.na(mapped)) mapped[[1]] else trimws(as.character(x %||% ""))
}

determiner_valence_emotion_sante <- function(emotion) {
  emotion_norm <- normaliser_nom_emotion_sante(emotion)
  key <- tolower(iconv(trimws(as.character(emotion_norm %||% "")), from = "", to = "ASCII//TRANSLIT"))
  key[is.na(key)] <- ""
  key <- gsub("[^a-z0-9]+", "", key)

  if (key %in% c("joie", "confiance", "anticipation", "apaisement", "positive")) {
    return("positive")
  }
  if (key %in% c("tristesse", "peur", "anxiete", "colere", "degout", "honte", "culpabilite", "negative")) {
    return("negative")
  }

  ""
}

lire_csv_souplement_sante <- function(path) {
  lecteurs <- list(
    function() utils::read.csv2(path, stringsAsFactors = FALSE, encoding = "UTF-8"),
    function() utils::read.csv(path, stringsAsFactors = FALSE, encoding = "UTF-8"),
    function() utils::read.delim(path, stringsAsFactors = FALSE, encoding = "UTF-8", sep = "\t"),
    function() utils::read.delim(path, stringsAsFactors = FALSE, encoding = "UTF-8", sep = "\t", header = FALSE)
  )

  essais <- lapply(lecteurs, function(fun) {
    tryCatch(fun(), error = function(e) NULL)
  })
  essais <- essais[vapply(essais, is.data.frame, logical(1))]

  if (!length(essais)) {
    stop(paste0("Lecture impossible du lexique émotionnel : ", path))
  }

  score_df <- function(df) {
    generic_names <- sum(grepl("^V[0-9]+$", names(df)))
    header_bonus <- if (generic_names == 0) 100000 else 0
    ncol(df) * 1000 + nrow(df) + header_bonus - generic_names * 100
  }

  essais[[which.max(vapply(essais, score_df, numeric(1)))]]
}

parser_lexique_emotionnel_sante <- function(raw_df) {
  if (is.null(raw_df) || !is.data.frame(raw_df) || !nrow(raw_df)) {
    return(data.frame(
      terme = character(0),
      emotion = character(0),
      poids = numeric(0),
      valence = character(0),
      stringsAsFactors = FALSE
    ))
  }

  df <- raw_df
  names(df) <- normaliser_nom_colonne_sante(names(df))

  trouver_colonne <- function(candidats) {
    noms <- names(df)
    match_idx <- match(candidats, noms)
    candidat <- noms[match_idx[!is.na(match_idx)]][1]
    if (length(candidat) && !is.na(candidat) && nzchar(candidat)) {
      return(candidat)
    }
    ""
  }

  col_terme <- trouver_colonne(c("term", "terme", "mot", "lemme", "word", "token", "c_mot", "c_lemme"))
  if (!nzchar(col_terme)) {
    col_terme <- trouver_colonne(c("french", "francais", "francais_french", "fr"))
  }
  if (!nzchar(col_terme) && identical(ncol(df), 3L) && all(grepl("^v[0-9]+$", names(df)))) {
    names(df) <- c("term", "emotion", "weight")
    col_terme <- "term"
  }
  if (!nzchar(col_terme)) {
    return(data.frame(
      terme = character(0),
      emotion = character(0),
      poids = numeric(0),
      valence = character(0),
      stringsAsFactors = FALSE
    ))
  }

  col_emotion <- trouver_colonne(c("emotion", "emotions", "categorie", "category", "label", "affect"))
  col_poids <- trouver_colonne(c("poids", "weight", "score", "value", "valeur"))
  col_valence <- trouver_colonne(c("valence", "polarity", "polarite"))

  if (nzchar(col_emotion)) {
    terme <- tolower(trimws(as.character(df[[col_terme]])))
    emotion <- vapply(df[[col_emotion]], normaliser_nom_emotion_sante, character(1))
    poids <- if (nzchar(col_poids)) suppressWarnings(as.numeric(df[[col_poids]])) else rep(1, nrow(df))
    poids[!is.finite(poids) | is.na(poids)] <- 1
    valence <- rep("", length(emotion))
    if (nzchar(col_valence)) {
      valence_src <- tolower(trimws(as.character(df[[col_valence]])))
      if (length(valence_src)) {
        len_copy <- min(length(valence), length(valence_src))
        valence[seq_len(len_copy)] <- valence_src[seq_len(len_copy)]
      }
    }
    idx_valence_vide <- !nzchar(valence)
    if (any(idx_valence_vide)) {
      valence[idx_valence_vide] <- vapply(emotion[idx_valence_vide], determiner_valence_emotion_sante, character(1))
    }

    out <- data.frame(
      terme = terme,
      emotion = emotion,
      poids = poids,
      valence = valence,
      stringsAsFactors = FALSE
    )
    out <- out[nzchar(out$terme) & nzchar(out$emotion), , drop = FALSE]
    return(out)
  }

  emotions_connues <- vapply(names(df), normaliser_nom_emotion_sante, character(1))
  colonnes_emotions_renommees <- names(df)[nzchar(emotions_connues) & emotions_connues != names(df)]
  colonnes_emotions_connues <- names(df)[vapply(emotions_connues, function(x) {
    x %in% c(
      "joie", "tristesse", "peur", "anxiete", "colere", "degout", "surprise",
      "confiance", "anticipation", "honte", "culpabilite", "apaisement",
      "positive", "negative"
    )
  }, logical(1))]
  colonnes_emotions <- unique(c(colonnes_emotions_renommees, colonnes_emotions_connues))

  if (!length(colonnes_emotions)) {
    return(data.frame(
      terme = character(0),
      emotion = character(0),
      poids = numeric(0),
      valence = character(0),
      stringsAsFactors = FALSE
    ))
  }

  terme <- tolower(trimws(as.character(df[[col_terme]])))
  rows <- vector("list", 0)
  for (col in colonnes_emotions) {
    poids <- suppressWarnings(as.numeric(df[[col]]))
    poids[is.na(poids)] <- 0
    idx <- poids > 0 & nzchar(terme)
    if (!any(idx)) next
    emotion <- normaliser_nom_emotion_sante(col)
    rows[[length(rows) + 1L]] <- data.frame(
      terme = terme[idx],
      emotion = rep(emotion, sum(idx)),
      poids = poids[idx],
      valence = rep(determiner_valence_emotion_sante(emotion), sum(idx)),
      stringsAsFactors = FALSE
    )
  }

  if (!length(rows)) {
    return(data.frame(
      terme = character(0),
      emotion = character(0),
      poids = numeric(0),
      valence = character(0),
      stringsAsFactors = FALSE
    ))
  }

  do.call(rbind, rows)
}

charger_lexique_emotionnel_sante <- function(source = "feel", repo_root = obtenir_repo_root_sante()) {
  source_resolue <- normaliser_lexique_emotionnel_sante(source)
  chemins_candidats <- switch(
    source_resolue,
    feel = c(
      file.path(repo_root, "dictionnaires", "feel_fr.csv"),
      file.path(repo_root, "dictionnaires", "FEEL_fr.csv"),
      file.path(repo_root, "dictionnaires", "feel.csv")
    ),
    nrc = c(
      file.path(repo_root, "dictionnaires", "NRC-Emotion-Lexicon-ForVariousLanguages.txt"),
      file.path(repo_root, "dictionnaires", "NRC-Emotion-Lexicon-Wordlevel-v0.92.txt"),
      file.path(repo_root, "dictionnaires", "nrc_emotions_fr.csv"),
      file.path(repo_root, "dictionnaires", "NRCEmotionLexicon_fr.csv"),
      file.path(repo_root, "dictionnaires", "nrc_fr.csv")
    )
  )

  path <- chemins_candidats[file.exists(chemins_candidats)][1]
  if (is.na(path) || !nzchar(path)) {
    return(list(
      data = NULL,
      path = "",
      note = paste0(
        "Lexique émotionnel ",
        toupper(source_resolue),
        " introuvable dans dictionnaires/. Déposez par exemple ",
        basename(chemins_candidats[[1]]),
        " pour activer la trajectoire émotionnelle."
      )
    ))
  }

  raw_df <- tryCatch(lire_csv_souplement_sante(path), error = function(e) NULL)
  if (is.null(raw_df)) {
    return(list(
      data = NULL,
      path = path,
      note = paste0("Lecture impossible du lexique émotionnel : ", basename(path), ".")
    ))
  }

  lexique_df <- parser_lexique_emotionnel_sante(raw_df)
  if (!nrow(lexique_df)) {
    return(list(
      data = NULL,
      path = path,
      note = paste0("Le lexique émotionnel ", basename(path), " est vide ou n'utilise pas un format reconnu.")
    ))
  }

  lexique_df$terme <- tolower(trimws(as.character(lexique_df$terme)))
  lexique_df$emotion <- vapply(lexique_df$emotion, normaliser_nom_emotion_sante, character(1))
  lexique_df$poids <- suppressWarnings(as.numeric(lexique_df$poids))
  lexique_df$poids[!is.finite(lexique_df$poids) | is.na(lexique_df$poids)] <- 1
  lexique_df$valence <- trimws(as.character(lexique_df$valence))
  lexique_df$valence <- ifelse(
    nzchar(lexique_df$valence),
    lexique_df$valence,
    vapply(lexique_df$emotion, determiner_valence_emotion_sante, character(1))
  )
  lexique_df <- lexique_df[nzchar(lexique_df$terme) & nzchar(lexique_df$emotion), , drop = FALSE]

  list(
    data = lexique_df,
    path = path,
    note = ""
  )
}

construire_matrice_emotionnelle_sante <- function(dfm_obj, lexique_df) {
  empty <- list(
    doc_emotion_mat = matrix(0, nrow = quanteda::ndoc(dfm_obj), ncol = 0),
    emotions = character(0),
    valence = character(0),
    termes_couverts = character(0)
  )

  if (is.null(dfm_obj) || !quanteda::ndoc(dfm_obj) || !quanteda::nfeat(dfm_obj) ||
      is.null(lexique_df) || !is.data.frame(lexique_df) || !nrow(lexique_df)) {
    return(empty)
  }

  features <- tolower(trimws(as.character(quanteda::featnames(dfm_obj))))
  idx_feat <- match(lexique_df$terme, features)
  idx_valides <- which(!is.na(idx_feat))
  if (!length(idx_valides)) {
    return(empty)
  }

  emotions <- unique(lexique_df$emotion[idx_valides])
  emotion_idx <- match(lexique_df$emotion[idx_valides], emotions)
  poids <- suppressWarnings(as.numeric(lexique_df$poids[idx_valides]))
  poids[!is.finite(poids) | is.na(poids)] <- 1

  mat_features_emotions <- Matrix::sparseMatrix(
    i = idx_feat[idx_valides],
    j = emotion_idx,
    x = poids,
    dims = c(length(features), length(emotions)),
    dimnames = list(features, emotions)
  )

  doc_emotion_mat <- as.matrix(dfm_obj %*% mat_features_emotions)
  if (!is.matrix(doc_emotion_mat)) {
    doc_emotion_mat <- as.matrix(doc_emotion_mat)
  }
  rownames(doc_emotion_mat) <- quanteda::docnames(dfm_obj)
  colnames(doc_emotion_mat) <- emotions

  valence_by_emotion <- vapply(emotions, function(emotion) {
    valences <- unique(trimws(as.character(lexique_df$valence[lexique_df$emotion == emotion])))
    valences <- valences[nzchar(valences)]
    if (length(valences)) valences[[1]] else determiner_valence_emotion_sante(emotion)
  }, character(1))

  list(
    doc_emotion_mat = doc_emotion_mat,
    emotions = emotions,
    valence = valence_by_emotion,
    termes_couverts = unique(lexique_df$terme[idx_valides])
  )
}

construire_matrice_valence_sante <- function(mat, valence_by_feature) {
  if (is.null(mat) || !is.matrix(mat) || !nrow(mat) || !ncol(mat) || !length(valence_by_feature)) {
    return(matrix(0, nrow = nrow(mat %||% matrix(0, nrow = 0, ncol = 0)), ncol = 0))
  }

  valence_by_feature <- trimws(as.character(valence_by_feature))
  positives <- which(valence_by_feature == "positive")
  negatives <- which(valence_by_feature == "negative")
  if (!length(positives) && !length(negatives)) {
    return(matrix(0, nrow = nrow(mat), ncol = 0))
  }

  out <- cbind(
    positive = if (length(positives)) rowSums(mat[, positives, drop = FALSE]) else rep(0, nrow(mat)),
    negative = if (length(negatives)) rowSums(mat[, negatives, drop = FALSE]) else rep(0, nrow(mat))
  )
  rownames(out) <- rownames(mat)
  out
}

creer_resultat_suivi_vide_sante <- function(variable = "",
                                            ordre_utilise = "asc",
                                            unite_lexicale = "unigramme",
                                            variable_filtre = NULL,
                                            modalite_filtre = "",
                                            couche_analyse = "lexicale_brute",
                                            lexique_emotionnel = "",
                                            note = "") {
  empty_indicateurs <- data.frame(
    Ordre = integer(0),
    Unite = character(0),
    Tokens_total = integer(0),
    Types_total = integer(0),
    Entropie_lexicale = numeric(0),
    Entropie_normalisee = numeric(0),
    Redondance_relative = numeric(0),
    stringsAsFactors = FALSE
  )
  empty_jsd <- data.frame(
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Divergence_Jensen_Shannon = numeric(0),
    stringsAsFactors = FALSE
  )
  empty_ref <- data.frame(
    Unite_reference = character(0),
    Unite_comparee = character(0),
    Divergence_Jensen_Shannon = numeric(0),
    stringsAsFactors = FALSE
  )
  empty_terms <- data.frame(
    Mode_comparaison = character(0),
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Type_evolution = character(0),
    Terme = character(0),
    Frequence_relative_depart = numeric(0),
    Frequence_relative_arrivee = numeric(0),
    Difference_relative = numeric(0),
    stringsAsFactors = FALSE
  )
  empty_contrib <- data.frame(
    Mode_comparaison = character(0),
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Terme = character(0),
    Frequence_relative_depart = numeric(0),
    Frequence_relative_arrivee = numeric(0),
    Difference_relative = numeric(0),
    Contribution_Jensen_Shannon = numeric(0),
    stringsAsFactors = FALSE
  )
  empty_ruptures <- data.frame(
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Divergence_Jensen_Shannon = numeric(0),
    Valeur_detection = numeric(0),
    Score_standardise = numeric(0),
    Pic_local = character(0),
    Rupture_detectee = character(0),
    Niveau_rupture = character(0),
    Termes_explicatifs = character(0),
    stringsAsFactors = FALSE
  )
  empty_profiles <- data.frame(Unite = character(0), stringsAsFactors = FALSE)

  list(
    variable = variable,
    ordre_utilise = ordre_utilise,
    unite_lexicale = unite_lexicale,
    couche_analyse = couche_analyse,
    lexique_emotionnel = lexique_emotionnel,
    variable_filtre = variable_filtre,
    modalite_filtre = modalite_filtre,
    unites = character(0),
    grouped_mat = matrix(0, nrow = 0, ncol = 0),
    rel_mat = matrix(0, nrow = 0, ncol = 0),
    indicateurs_df = empty_indicateurs,
    successive_df = empty_jsd,
    reference_df = empty_ref,
    terms_df = empty_terms,
    contributions_df = empty_contrib,
    ruptures_df = empty_ruptures,
    jsd_mat = matrix(0, nrow = 0, ncol = 0),
    profils_emotionnels_df = empty_profiles,
    profils_valence_df = empty_profiles,
    note = note,
    n_vocabulaire = 0L
  )
}

construire_dfm_lexical_sante <- function(dfm_obj,
                                         tok_obj = NULL,
                                         unite_lexicale = "unigramme") {
  unite_resolue <- normaliser_unite_lexicale_sante(unite_lexicale)

  if (identical(unite_resolue, "unigramme")) {
    return(dfm_obj)
  }

  if (is.null(tok_obj)) {
    stop("Le calcul en bigrammes nécessite les tokens prétraités du pipeline.")
  }

  featnames_finales <- quanteda::featnames(dfm_obj)
  if (!length(featnames_finales)) {
    stop("Le vocabulaire unigramme est vide ; impossible de construire les bigrammes.")
  }

  tok_filtre <- quanteda::tokens_select(
    tok_obj,
    pattern = featnames_finales,
    selection = "keep",
    valuetype = "fixed",
    case_insensitive = FALSE,
    padding = FALSE
  )
  tok_bigrams <- quanteda::tokens_ngrams(tok_filtre, n = 2L)
  dfm_bigrams <- quanteda::dfm(tok_bigrams)
  quanteda::docnames(dfm_bigrams) <- quanteda::docnames(dfm_obj)
  dfm_bigrams
}

parser_modalites_dates_sante <- function(vals) {
  valeurs <- trimws(as.character(vals))
  if (!length(valeurs)) {
    return(as.Date(character(0)))
  }

  parser_avec_format <- function(x, format) {
    tryCatch(
      as.Date(x, format = format),
      error = function(e) rep(as.Date(NA), length(x))
    )
  }

  essais <- list(
    list(values = valeurs, format = "%Y-%m-%d"),
    list(values = valeurs, format = "%Y/%m/%d"),
    list(values = valeurs, format = "%d/%m/%Y"),
    list(values = valeurs, format = "%d-%m-%Y"),
    list(values = valeurs, format = "%Y.%m.%d"),
    list(values = valeurs, format = "%d.%m.%Y"),
    list(values = valeurs, format = "%Y_%m_%d"),
    list(values = valeurs, format = "%d_%m_%Y")
  )

  valeurs_ym <- ifelse(grepl("^\\d{4}[-_/\\.]\\d{1,2}$", valeurs), paste0(gsub("[_/\\.]", "-", valeurs), "-01"), NA_character_)
  essais[[length(essais) + 1L]] <- list(values = valeurs_ym, format = "%Y-%m-%d")

  valeurs_my <- ifelse(grepl("^\\d{1,2}[-_/\\.]\\d{4}$", valeurs), paste0("01-", gsub("[_/\\.]", "-", valeurs)), NA_character_)
  essais[[length(essais) + 1L]] <- list(values = valeurs_my, format = "%d-%m-%Y")

  valeurs_y <- ifelse(grepl("^\\d{4}$", valeurs), paste0(valeurs, "-01-01"), NA_character_)
  essais[[length(essais) + 1L]] <- list(values = valeurs_y, format = "%Y-%m-%d")

  for (essai in essais) {
    candidats <- essai$values
    if (is.null(candidats) || !length(candidats) || anyNA(candidats)) {
      next
    }
    dates <- parser_avec_format(candidats, essai$format)
    if (length(dates) == length(valeurs) && all(!is.na(dates))) {
      return(dates)
    }
  }

  rep(as.Date(NA), length(valeurs))
}

ordonner_modalites_naturelles_sante <- function(vals) {
  valeurs <- trimws(as.character(vals))
  if (!length(valeurs)) {
    return(character(0))
  }

  prefixes <- tolower(gsub("(\\d.*)$", "", valeurs, perl = TRUE))
  nombres <- suppressWarnings(as.numeric(sub("^.*?(\\d+)\\D*$", "\\1", valeurs, perl = TRUE)))
  has_number <- grepl("\\d", valeurs)

  if (all(has_number)) {
    return(valeurs[order(prefixes, nombres, valeurs, method = "radix")])
  }

  valeurs[order(valeurs, method = "radix")]
}

ordonner_modalites_suivi_sante <- function(values, ordre = "asc") {
  vals <- trimws(as.character(values))
  vals <- vals[!is.na(vals) & nzchar(vals)]
  vals <- unique(vals)
  if (!length(vals)) return(character(0))

  nums <- suppressWarnings(as.numeric(vals))
  if (all(is.finite(nums))) {
    ordered_vals <- vals[order(nums, vals)]
  } else {
    parsed_dates <- parser_modalites_dates_sante(vals)
    if (all(!is.na(parsed_dates))) {
      ordered_vals <- vals[order(parsed_dates, vals)]
    } else {
      ordered_vals <- ordonner_modalites_naturelles_sante(vals)
    }
  }

  if (identical(normaliser_ordre_suivi_sante(ordre), "desc")) {
    rev(ordered_vals)
  } else {
    ordered_vals
  }
}

normaliser_modalites_selectionnees_sante <- function(selection, modalites_ordonnees) {
  if (!length(modalites_ordonnees)) return(character(0))
  selected <- trimws(as.character(selection))
  selected <- selected[!is.na(selected) & nzchar(selected)]
  if (!length(selected)) return(modalites_ordonnees)
  modalites_ordonnees[modalites_ordonnees %in% selected]
}

calculer_entropie_lexicale_sante <- function(freq_vec) {
  freq <- as.numeric(freq_vec)
  freq <- freq[is.finite(freq) & !is.na(freq) & freq > 0]

  nb_tokens <- sum(freq)
  nb_types <- length(freq)
  if (!length(freq) || nb_tokens <= 0) {
    return(list(
      nb_tokens = 0L,
      nb_types = 0L,
      entropie_lexicale = NA_real_,
      entropie_normalisee = NA_real_,
      redondance_relative = NA_real_
    ))
  }

  probas <- freq / nb_tokens
  entropie <- -sum(probas * log2(probas))
  if (nb_types <= 1L) {
    entropie_norm <- 0
    redondance <- 1
  } else {
    entropie_norm <- entropie / log2(nb_types)
    entropie_norm <- min(1, max(0, entropie_norm))
    redondance <- 1 - entropie_norm
  }

  list(
    nb_tokens = as.integer(nb_tokens),
    nb_types = as.integer(nb_types),
    entropie_lexicale = entropie,
    entropie_normalisee = entropie_norm,
    redondance_relative = redondance
  )
}

calculer_divergence_jensen_shannon_sante <- function(p, q) {
  p <- as.numeric(p)
  q <- as.numeric(q)

  if (!length(p) || !length(q) || length(p) != length(q)) {
    return(NA_real_)
  }

  somme_p <- sum(p)
  somme_q <- sum(q)
  if (!is.finite(somme_p) || !is.finite(somme_q) || somme_p <= 0 || somme_q <= 0) {
    return(NA_real_)
  }

  p <- p / somme_p
  q <- q / somme_q
  m <- (p + q) / 2

  kl_safe <- function(a, b) {
    idx <- a > 0 & b > 0
    if (!any(idx)) return(0)
    sum(a[idx] * log2(a[idx] / b[idx]))
  }

  0.5 * kl_safe(p, m) + 0.5 * kl_safe(q, m)
}

construire_message_exploratoire_sante <- function(nb_unites, grouped_mat) {
  messages <- character(0)
  totals <- rowSums(grouped_mat)
  vocabulaire <- ncol(grouped_mat)

  if (nb_unites <= 3L) {
    messages <- c(messages, "moins de quatre entretiens sont disponibles")
  }
  if (length(totals) && any(totals < 80)) {
    messages <- c(messages, "au moins un entretien est très court")
  }
  if (isTRUE(vocabulaire < 30L)) {
    messages <- c(messages, "le vocabulaire commun est faible")
  }

  if (!length(messages)) {
    return("")
  }

  paste0("Suivi exploratoire : ", paste(messages, collapse = "; "), ".")
}

calculer_contributions_jensen_shannon_sante <- function(prev_rel, cur_rel) {
  p <- as.numeric(prev_rel)
  q <- as.numeric(cur_rel)

  if (!length(p) || !length(q) || length(p) != length(q)) {
    return(rep(NA_real_, max(length(p), length(q))))
  }

  somme_p <- sum(p)
  somme_q <- sum(q)
  if (!is.finite(somme_p) || !is.finite(somme_q) || somme_p <= 0 || somme_q <= 0) {
    return(rep(NA_real_, length(p)))
  }

  p <- p / somme_p
  q <- q / somme_q
  m <- (p + q) / 2

  kl_term_safe <- function(a, b) {
    contrib <- numeric(length(a))
    idx <- a > 0 & b > 0
    contrib[idx] <- a[idx] * log2(a[idx] / b[idx])
    contrib
  }

  0.5 * kl_term_safe(p, m) + 0.5 * kl_term_safe(q, m)
}

extraire_termes_evolution_sante <- function(prev_rel,
                                            cur_rel,
                                            unite_depart,
                                            unite_arrivee,
                                            mode_comparaison,
                                            top_n_terms = 20L) {
  empty_df <- data.frame(
    Mode_comparaison = character(0),
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Type_evolution = character(0),
    Terme = character(0),
    Frequence_relative_depart = numeric(0),
    Frequence_relative_arrivee = numeric(0),
    Difference_relative = numeric(0),
    stringsAsFactors = FALSE
  )

  diff_rel <- as.numeric(cur_rel) - as.numeric(prev_rel)
  names(diff_rel) <- names(cur_rel)

  etiquettes <- rep(NA_character_, length(diff_rel))
  etiquettes[prev_rel == 0 & cur_rel > 0] <- "nouveau"
  etiquettes[prev_rel > 0 & cur_rel == 0] <- "disparu"
  etiquettes[prev_rel > 0 & cur_rel > prev_rel] <- "hausse"
  etiquettes[prev_rel > cur_rel & cur_rel > 0] <- "baisse"

  idx_valides <- which(!is.na(etiquettes))
  if (!length(idx_valides)) {
    return(empty_df)
  }

  base_df <- data.frame(
    Mode_comparaison = rep(mode_comparaison, length(idx_valides)),
    Unite_depart = rep(unite_depart, length(idx_valides)),
    Unite_arrivee = rep(unite_arrivee, length(idx_valides)),
    Type_evolution = etiquettes[idx_valides],
    Terme = names(diff_rel)[idx_valides],
    Frequence_relative_depart = as.numeric(prev_rel[idx_valides]),
    Frequence_relative_arrivee = as.numeric(cur_rel[idx_valides]),
    Difference_relative = as.numeric(diff_rel[idx_valides]),
    stringsAsFactors = FALSE
  )

  extraire_top <- function(df, type) {
    sous_df <- df[df$Type_evolution == type, , drop = FALSE]
    if (!nrow(sous_df)) return(sous_df)
    ord <- order(abs(sous_df$Difference_relative), decreasing = TRUE)
    sous_df <- sous_df[ord, , drop = FALSE]
    utils::head(sous_df, top_n_terms)
  }

  rbind(
    extraire_top(base_df, "nouveau"),
    extraire_top(base_df, "hausse"),
    extraire_top(base_df, "baisse"),
    extraire_top(base_df, "disparu")
  )
}

extraire_contributions_termes_jsd_sante <- function(prev_rel,
                                                    cur_rel,
                                                    unite_depart,
                                                    unite_arrivee,
                                                    mode_comparaison,
                                                    top_n_terms = 20L) {
  empty_df <- data.frame(
    Mode_comparaison = character(0),
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Terme = character(0),
    Frequence_relative_depart = numeric(0),
    Frequence_relative_arrivee = numeric(0),
    Difference_relative = numeric(0),
    Contribution_Jensen_Shannon = numeric(0),
    stringsAsFactors = FALSE
  )

  diff_rel <- as.numeric(cur_rel) - as.numeric(prev_rel)
  names(diff_rel) <- names(cur_rel)
  contributions <- calculer_contributions_jensen_shannon_sante(prev_rel, cur_rel)
  names(contributions) <- names(cur_rel)

  idx_valides <- which(is.finite(contributions) & contributions > 0)
  if (!length(idx_valides)) {
    return(empty_df)
  }

  base_df <- data.frame(
    Mode_comparaison = rep(mode_comparaison, length(idx_valides)),
    Unite_depart = rep(unite_depart, length(idx_valides)),
    Unite_arrivee = rep(unite_arrivee, length(idx_valides)),
    Terme = names(contributions)[idx_valides],
    Frequence_relative_depart = as.numeric(prev_rel[idx_valides]),
    Frequence_relative_arrivee = as.numeric(cur_rel[idx_valides]),
    Difference_relative = as.numeric(diff_rel[idx_valides]),
    Contribution_Jensen_Shannon = as.numeric(contributions[idx_valides]),
    stringsAsFactors = FALSE
  )

  ord <- order(
    base_df$Contribution_Jensen_Shannon,
    abs(base_df$Difference_relative),
    decreasing = TRUE
  )
  base_df <- base_df[ord, , drop = FALSE]
  utils::head(base_df, top_n_terms)
}

detecter_ruptures_discursives_sante <- function(successive_df,
                                                contributions_df = NULL,
                                                seuil_z = 1) {
  empty_df <- data.frame(
    Unite_depart = character(0),
    Unite_arrivee = character(0),
    Divergence_Jensen_Shannon = numeric(0),
    Valeur_detection = numeric(0),
    Score_standardise = numeric(0),
    Pic_local = character(0),
    Rupture_detectee = character(0),
    Niveau_rupture = character(0),
    Termes_explicatifs = character(0),
    stringsAsFactors = FALSE
  )

  if (is.null(successive_df) || !is.data.frame(successive_df) || !nrow(successive_df)) {
    return(empty_df)
  }

  valeurs <- suppressWarnings(as.numeric(successive_df$Divergence_Jensen_Shannon))
  if (!length(valeurs) || !any(is.finite(valeurs))) {
    return(empty_df)
  }

  valeurs_detection <- valeurs

  moyenne <- base::mean(valeurs_detection, na.rm = TRUE)
  ecart_type <- stats::sd(valeurs_detection, na.rm = TRUE)
  if (!is.finite(ecart_type) || identical(ecart_type, 0)) {
    scores_z <- rep(0, length(valeurs_detection))
  } else {
    scores_z <- (valeurs_detection - moyenne) / ecart_type
  }

  seuil_quantile <- tryCatch(
    as.numeric(stats::quantile(valeurs_detection, probs = 0.75, na.rm = TRUE, names = FALSE, type = 7)),
    error = function(e) NA_real_
  )

  pics_locaux <- rep(FALSE, length(valeurs_detection))
  if (length(valeurs_detection) >= 3L) {
    for (i in 2:(length(valeurs_detection) - 1L)) {
      voisin_gauche <- valeurs_detection[[i - 1L]]
      voisin_droit <- valeurs_detection[[i + 1L]]
      pics_locaux[[i]] <- is.finite(valeurs_detection[[i]]) &&
        valeurs_detection[[i]] >= voisin_gauche &&
        valeurs_detection[[i]] >= voisin_droit
    }
  }

  detection_possible <- length(valeurs_detection) >= 3L && any(is.finite(valeurs_detection))
  rupture_detectee <- rep(FALSE, length(valeurs_detection))
  niveau_rupture <- rep("variation", length(valeurs_detection))

  if (detection_possible) {
    condition_quantile <- rep(FALSE, length(valeurs_detection))
    if (!is.na(seuil_quantile)) {
      condition_quantile <- valeurs_detection >= seuil_quantile & valeurs_detection > moyenne
    }
    rupture_detectee <- pics_locaux & is.finite(scores_z) & (
      scores_z >= seuil_z | condition_quantile
    )
    niveau_rupture[rupture_detectee & scores_z >= 1.5] <- "majeure"
    niveau_rupture[rupture_detectee & scores_z >= seuil_z & scores_z < 1.5] <- "moderee"
  } else {
    niveau_rupture[] <- "exploratoire"
  }

  termes_explicatifs <- rep("", length(valeurs))
  if (!is.null(contributions_df) && is.data.frame(contributions_df) && nrow(contributions_df)) {
    contributions_successives <- contributions_df[contributions_df$Mode_comparaison == "séance_précédente", , drop = FALSE]
    if (nrow(contributions_successives)) {
      termes_explicatifs <- vapply(seq_len(nrow(successive_df)), function(i) {
        sous_df <- contributions_successives[
          contributions_successives$Unite_depart == successive_df$Unite_depart[[i]] &
            contributions_successives$Unite_arrivee == successive_df$Unite_arrivee[[i]],
          ,
          drop = FALSE
        ]
        if (!nrow(sous_df)) {
          return("")
        }
        termes <- unique(trimws(as.character(sous_df$Terme)))
        termes <- termes[nzchar(termes)]
        if (!length(termes)) {
          return("")
        }
        paste(utils::head(termes, 6L), collapse = ", ")
      }, character(1))
    }
  }

  data.frame(
    Unite_depart = as.character(successive_df$Unite_depart),
    Unite_arrivee = as.character(successive_df$Unite_arrivee),
    Divergence_Jensen_Shannon = valeurs,
    Valeur_detection = as.numeric(valeurs_detection),
    Score_standardise = as.numeric(scores_z),
    Pic_local = ifelse(pics_locaux, "oui", "non"),
    Rupture_detectee = ifelse(rupture_detectee, "oui", "non"),
    Niveau_rupture = niveau_rupture,
    Termes_explicatifs = termes_explicatifs,
    stringsAsFactors = FALSE
  )
}

calculer_suivi_longitudinal_jsd <- function(filtered_corpus_ok,
                                            dfm_ok,
                                            tok_ok = NULL,
                                            variable_suivi = NULL,
                                            variable_filtre = NULL,
                                            modalite_filtre = NULL,
                                            modalites_selectionnees = character(0),
                                            ordre_chronologique = "asc",
                                            unite_lexicale = "unigramme",
                                            couche_analyse = "lexicale_brute",
                                            lexique_emotionnel = "feel",
                                            top_n_terms = 20L,
                                            logger = NULL) {
  if (is.null(filtered_corpus_ok) || is.null(dfm_ok)) {
    return(NULL)
  }

  log_suivi <- function(message) {
    if (is.function(logger)) logger(message)
  }

  dv <- tryCatch(
    as.data.frame(quanteda::docvars(filtered_corpus_ok), stringsAsFactors = FALSE),
    error = function(e) NULL
  )
  variable <- selectionner_variable_suivi_sante(dv, variable_suivi = variable_suivi)
  if (is.null(variable)) {
    log_suivi("Suivi longitudinal : aucune variable étoilée exploitable n'a été détectée.")
    return(NULL)
  }

  variable_filtre_resolue <- selectionner_variable_filtre_sante(dv, variable_filtre = variable_filtre)
  ordre_utilise <- normaliser_ordre_suivi_sante(ordre_chronologique)
  unite_lexicale_resolue <- normaliser_unite_lexicale_sante(unite_lexicale)
  couche_analyse_resolue <- normaliser_couche_analyse_sante(couche_analyse)
  lexique_emotionnel_resolu <- normaliser_lexique_emotionnel_sante(lexique_emotionnel)

  idx_keep <- rep(TRUE, quanteda::ndoc(filtered_corpus_ok))
  if (!is.null(variable_filtre_resolue) && nzchar(as.character(modalite_filtre %||% ""))) {
    valeurs_filtre <- trimws(as.character(dv[[variable_filtre_resolue]]))
    idx_keep <- idx_keep & !is.na(valeurs_filtre) & (valeurs_filtre == trimws(as.character(modalite_filtre)))
  }

  if (!any(idx_keep)) {
    log_suivi("Suivi longitudinal : le filtre choisi ne retient aucun entretien.")
    return(NULL)
  }

  corpus_suivi <- filtered_corpus_ok[idx_keep]
  dfm_suivi <- dfm_ok[idx_keep, ]
  tok_suivi <- if (!is.null(tok_ok)) tok_ok[idx_keep] else NULL
  dv_suivi <- dv[idx_keep, , drop = FALSE]

  unites <- trimws(as.character(dv_suivi[[variable]]))
  unites[is.na(unites)] <- ""
  idx_non_vides <- nzchar(unites)
  if (!any(idx_non_vides)) {
    log_suivi("Suivi longitudinal : aucune modalité exploitable n'est renseignée pour la variable de suivi.")
    return(NULL)
  }

  corpus_suivi <- corpus_suivi[idx_non_vides]
  dfm_suivi <- dfm_suivi[idx_non_vides, ]
  if (!is.null(tok_suivi)) tok_suivi <- tok_suivi[idx_non_vides]
  dv_suivi <- dv_suivi[idx_non_vides, , drop = FALSE]
  unites <- unites[idx_non_vides]

  unites_ordonnees <- ordonner_modalites_suivi_sante(unites, ordre = ordre_utilise)
  unites_selectionnees <- normaliser_modalites_selectionnees_sante(modalites_selectionnees, unites_ordonnees)
  if (length(unites_selectionnees) >= 2L) {
    idx_selected <- unites %in% unites_selectionnees
    corpus_suivi <- corpus_suivi[idx_selected]
    dfm_suivi <- dfm_suivi[idx_selected, ]
    if (!is.null(tok_suivi)) tok_suivi <- tok_suivi[idx_selected]
    dv_suivi <- dv_suivi[idx_selected, , drop = FALSE]
    unites <- unites[idx_selected]
    unites_ordonnees <- unites_selectionnees
  }

  if (length(unites_ordonnees) < 2L) {
    log_suivi("Suivi longitudinal : au moins deux entretiens distincts sont nécessaires.")
    return(NULL)
  }

  grouped_mat <- NULL
  rel_mat <- NULL
  profils_emotionnels_df <- data.frame(Unite = character(0), stringsAsFactors = FALSE)
  profils_valence_df <- data.frame(Unite = character(0), stringsAsFactors = FALSE)
  note_mode <- character(0)

  if (identical(couche_analyse_resolue, "emotionnelle")) {
    if (!identical(unite_lexicale_resolue, "unigramme")) {
      note_mode <- c(note_mode, "La trajectoire émotionnelle repose sur les mots/lemmes simples ; le paramètre bigramme a été ignoré.")
    }

    lexique_info <- charger_lexique_emotionnel_sante(
      source = lexique_emotionnel_resolu,
      repo_root = obtenir_repo_root_sante()
    )
    if (is.null(lexique_info$data) || !nrow(lexique_info$data)) {
      note <- lexique_info$note %||% "Le lexique émotionnel est indisponible."
      log_suivi(paste0("Trajectoire émotionnelle : ", note))
      return(creer_resultat_suivi_vide_sante(
        variable = variable,
        ordre_utilise = ordre_utilise,
        unite_lexicale = "unigramme",
        variable_filtre = variable_filtre_resolue,
        modalite_filtre = if (nzchar(as.character(modalite_filtre %||% ""))) as.character(modalite_filtre) else "",
        couche_analyse = couche_analyse_resolue,
        lexique_emotionnel = lexique_emotionnel_resolu,
        note = note
      ))
    }

    mat_emotion_info <- construire_matrice_emotionnelle_sante(dfm_suivi, lexique_info$data)
    doc_emotion_mat <- mat_emotion_info$doc_emotion_mat
    if (!is.matrix(doc_emotion_mat) || !nrow(doc_emotion_mat) || !ncol(doc_emotion_mat) || sum(doc_emotion_mat) <= 0) {
      note <- paste0(
        "Le lexique émotionnel ",
        toupper(lexique_emotionnel_resolu),
        " ne reconnaît aucune émotion dans le corpus après prétraitement."
      )
      log_suivi(paste0("Trajectoire émotionnelle : ", note))
      return(creer_resultat_suivi_vide_sante(
        variable = variable,
        ordre_utilise = ordre_utilise,
        unite_lexicale = "unigramme",
        variable_filtre = variable_filtre_resolue,
        modalite_filtre = if (nzchar(as.character(modalite_filtre %||% ""))) as.character(modalite_filtre) else "",
        couche_analyse = couche_analyse_resolue,
        lexique_emotionnel = lexique_emotionnel_resolu,
        note = note
      ))
    }

    doc_groups <- factor(unites, levels = unites_ordonnees)
    grouped_mat <- rowsum(doc_emotion_mat, group = doc_groups, reorder = FALSE)
    if (!is.matrix(grouped_mat)) {
      grouped_mat <- as.matrix(grouped_mat)
    }
    rownames(grouped_mat) <- levels(doc_groups)

    row_totals <- rowSums(grouped_mat)
    keep_rows <- row_totals > 0
    grouped_mat <- grouped_mat[keep_rows, , drop = FALSE]
    unites_ordonnees <- rownames(grouped_mat)

    if (length(unites_ordonnees) < 2L) {
      note <- "Moins de deux entretiens contiennent des émotions reconnues après regroupement."
      log_suivi(paste0("Trajectoire émotionnelle : ", note))
      return(creer_resultat_suivi_vide_sante(
        variable = variable,
        ordre_utilise = ordre_utilise,
        unite_lexicale = "unigramme",
        variable_filtre = variable_filtre_resolue,
        modalite_filtre = if (nzchar(as.character(modalite_filtre %||% ""))) as.character(modalite_filtre) else "",
        couche_analyse = couche_analyse_resolue,
        lexique_emotionnel = lexique_emotionnel_resolu,
        note = note
      ))
    }

    row_totals <- rowSums(grouped_mat)
    rel_mat <- grouped_mat
    rel_mat[] <- 0
    rel_mat[row_totals > 0, ] <- grouped_mat[row_totals > 0, , drop = FALSE] / row_totals[row_totals > 0]

    profils_emotionnels_df <- data.frame(
      Unite = rownames(rel_mat),
      rel_mat,
      check.names = FALSE,
      stringsAsFactors = FALSE
    )

    valence_mat <- construire_matrice_valence_sante(grouped_mat, mat_emotion_info$valence)
    if (is.matrix(valence_mat) && nrow(valence_mat) && ncol(valence_mat)) {
      valence_totals <- rowSums(valence_mat)
      valence_rel <- valence_mat
      valence_rel[] <- 0
      valence_rel[valence_totals > 0, ] <- valence_mat[valence_totals > 0, , drop = FALSE] / valence_totals[valence_totals > 0]
      profils_valence_df <- data.frame(
        Unite = rownames(valence_rel),
        valence_rel,
        check.names = FALSE,
        stringsAsFactors = FALSE
      )
    }
  } else {
    dfm_lexical <- tryCatch(
      construire_dfm_lexical_sante(
        dfm_obj = dfm_suivi,
        tok_obj = tok_suivi,
        unite_lexicale = unite_lexicale_resolue
      ),
      error = function(e) {
        log_suivi(paste0("Suivi longitudinal : impossible de préparer l'unité lexicale demandée (", e$message, ")."))
        NULL
      }
    )
    if (is.null(dfm_lexical) || !quanteda::ndoc(dfm_lexical) || !quanteda::nfeat(dfm_lexical)) {
      log_suivi("Suivi longitudinal : l'unité lexicale choisie ne produit aucun vocabulaire exploitable.")
      return(NULL)
    }

    grouped_dfm <- quanteda::dfm_group(dfm_lexical, groups = factor(unites, levels = unites_ordonnees))
    grouped_mat <- quanteda::convert(grouped_dfm, to = "matrix")
    if (!is.matrix(grouped_mat)) {
      grouped_mat <- as.matrix(grouped_mat)
    }

    rownames(grouped_mat) <- unites_ordonnees
    row_totals <- rowSums(grouped_mat)
    keep_rows <- row_totals > 0
    grouped_mat <- grouped_mat[keep_rows, , drop = FALSE]
    unites_ordonnees <- rownames(grouped_mat)
    if (length(unites_ordonnees) < 2L) {
      log_suivi("Suivi longitudinal : moins de deux entretiens contiennent du lexique exploitable.")
      return(NULL)
    }

    row_totals <- rowSums(grouped_mat)
    rel_mat <- grouped_mat
    rel_mat[] <- 0
    rel_mat[row_totals > 0, ] <- grouped_mat[row_totals > 0, , drop = FALSE] / row_totals[row_totals > 0]
  }

  indicateurs_rows <- lapply(unites_ordonnees, function(unit) {
    stats_unit <- calculer_entropie_lexicale_sante(grouped_mat[unit, ])
    data.frame(
      Ordre = match(unit, unites_ordonnees),
      Unite = unit,
      Tokens_total = stats_unit$nb_tokens,
      Types_total = stats_unit$nb_types,
      Entropie_lexicale = stats_unit$entropie_lexicale,
      Entropie_normalisee = stats_unit$entropie_normalisee,
      Redondance_relative = stats_unit$redondance_relative,
      stringsAsFactors = FALSE
    )
  })
  indicateurs_df <- do.call(rbind, indicateurs_rows)

  message_exploratoire <- construire_message_exploratoire_sante(length(unites_ordonnees), grouped_mat)
  if (length(note_mode)) {
    message_exploratoire <- paste(c(message_exploratoire, note_mode), collapse = " ")
  }
  if (nzchar(message_exploratoire)) {
    log_suivi(message_exploratoire)
  }

  successive_rows <- vector("list", 0)
  reference_rows <- vector("list", 0)
  terms_rows <- vector("list", 0)
  contributions_rows <- vector("list", 0)
  unite_reference <- unites_ordonnees[[1]]
  ref_rel <- rel_mat[unite_reference, ]

  for (i in 2:length(unites_ordonnees)) {
    prev_unit <- unites_ordonnees[[i - 1L]]
    cur_unit <- unites_ordonnees[[i]]
    prev_rel <- rel_mat[prev_unit, ]
    cur_rel <- rel_mat[cur_unit, ]

    successive_rows[[length(successive_rows) + 1L]] <- data.frame(
      Unite_depart = prev_unit,
      Unite_arrivee = cur_unit,
      Divergence_Jensen_Shannon = calculer_divergence_jensen_shannon_sante(prev_rel, cur_rel),
      stringsAsFactors = FALSE
    )

    reference_rows[[length(reference_rows) + 1L]] <- data.frame(
      Unite_reference = unite_reference,
      Unite_comparee = cur_unit,
      Divergence_Jensen_Shannon = calculer_divergence_jensen_shannon_sante(ref_rel, cur_rel),
      stringsAsFactors = FALSE
    )

    terms_rows[[length(terms_rows) + 1L]] <- extraire_termes_evolution_sante(
      prev_rel = prev_rel,
      cur_rel = cur_rel,
      unite_depart = prev_unit,
      unite_arrivee = cur_unit,
      mode_comparaison = "séance_précédente",
      top_n_terms = top_n_terms
    )
    contributions_rows[[length(contributions_rows) + 1L]] <- extraire_contributions_termes_jsd_sante(
      prev_rel = prev_rel,
      cur_rel = cur_rel,
      unite_depart = prev_unit,
      unite_arrivee = cur_unit,
      mode_comparaison = "séance_précédente",
      top_n_terms = top_n_terms
    )

    terms_rows[[length(terms_rows) + 1L]] <- extraire_termes_evolution_sante(
      prev_rel = ref_rel,
      cur_rel = cur_rel,
      unite_depart = unite_reference,
      unite_arrivee = cur_unit,
      mode_comparaison = "première_séance",
      top_n_terms = top_n_terms
    )
    contributions_rows[[length(contributions_rows) + 1L]] <- extraire_contributions_termes_jsd_sante(
      prev_rel = ref_rel,
      cur_rel = cur_rel,
      unite_depart = unite_reference,
      unite_arrivee = cur_unit,
      mode_comparaison = "première_séance",
      top_n_terms = top_n_terms
    )
  }

  successive_df <- if (length(successive_rows)) do.call(rbind, successive_rows) else data.frame()
  reference_df <- if (length(reference_rows)) do.call(rbind, reference_rows) else data.frame()
  terms_df <- if (length(terms_rows)) do.call(rbind, terms_rows) else data.frame()
  contributions_df <- if (length(contributions_rows)) do.call(rbind, contributions_rows) else data.frame()

  ruptures_df <- detecter_ruptures_discursives_sante(
    successive_df = successive_df,
    contributions_df = contributions_df,
    seuil_z = 1
  )

  jsd_mat <- matrix(0, nrow = length(unites_ordonnees), ncol = length(unites_ordonnees))
  rownames(jsd_mat) <- unites_ordonnees
  colnames(jsd_mat) <- unites_ordonnees
  for (i in seq_len(nrow(rel_mat))) {
    for (j in seq_len(nrow(rel_mat))) {
      jsd_mat[i, j] <- calculer_divergence_jensen_shannon_sante(rel_mat[i, ], rel_mat[j, ])
    }
  }

  list(
    variable = variable,
    ordre_utilise = ordre_utilise,
    unite_lexicale = if (identical(couche_analyse_resolue, "emotionnelle")) "unigramme" else unite_lexicale_resolue,
    couche_analyse = couche_analyse_resolue,
    lexique_emotionnel = if (identical(couche_analyse_resolue, "emotionnelle")) lexique_emotionnel_resolu else "",
    variable_filtre = variable_filtre_resolue,
    modalite_filtre = if (nzchar(as.character(modalite_filtre %||% ""))) as.character(modalite_filtre) else "",
    unites = unites_ordonnees,
    grouped_mat = grouped_mat,
    rel_mat = rel_mat,
    indicateurs_df = indicateurs_df,
    successive_df = successive_df,
    reference_df = reference_df,
    terms_df = terms_df,
    contributions_df = contributions_df,
    ruptures_df = ruptures_df,
    jsd_mat = jsd_mat,
    profils_emotionnels_df = profils_emotionnels_df,
    profils_valence_df = profils_valence_df,
    note = message_exploratoire,
    n_vocabulaire = ncol(grouped_mat)
  )
}
