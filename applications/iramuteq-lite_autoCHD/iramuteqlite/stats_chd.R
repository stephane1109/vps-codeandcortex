# Rôle du fichier: stats_chd.R centralise la table des statistiques CHD pour le mode IRaMuTeQ-like.

formatter_6_decimales_chd <- function(x) {
  ifelse(is.na(x), NA_character_, formatC(as.numeric(x), format = "f", digits = 6))
}

.normaliser_type_terme_iramuteq <- function(type_vals) {
  types <- tolower(trimws(as.character(type_vals)))
  types[is.na(types)] <- ""
  types[types %in% c("", "na", "nan", "null")] <- ""
  types
}
construire_type_lexique_fr <- function(termes, lexique_fr_df) {
  termes_chr <- tolower(trimws(as.character(termes)))
  termes_chr[is.na(termes_chr)] <- ""

  if (is.null(lexique_fr_df) || !is.data.frame(lexique_fr_df) || nrow(lexique_fr_df) == 0) {
    return(rep("", length(termes_chr)))
  }

  colonnes_requises <- c("c_mot", "c_lemme", "c_morpho")
  if (!all(colonnes_requises %in% names(lexique_fr_df))) {
    return(rep("", length(termes_chr)))
  }

  lex <- lexique_fr_df[, colonnes_requises, drop = FALSE]
  lex$c_mot <- tolower(trimws(as.character(lex$c_mot)))
  lex$c_lemme <- tolower(trimws(as.character(lex$c_lemme)))
  lex$c_morpho <- .normaliser_type_terme_iramuteq(lex$c_morpho)
  lex <- lex[nzchar(lex$c_morpho), , drop = FALSE]

  indexer <- function(cles, valeurs) {
    cles <- tolower(trimws(as.character(cles)))
    cles[is.na(cles)] <- ""
    valeurs <- .normaliser_type_terme_iramuteq(valeurs)
    idx <- nzchar(cles) & nzchar(valeurs)
    if (!any(idx)) return(character(0))

    split_vals <- split(valeurs[idx], cles[idx])
    agreges <- vapply(
      split_vals,
      function(v) paste(sort(unique(v[nzchar(v)])), collapse = "|"),
      character(1),
      USE.NAMES = TRUE
    )
    agreges[nzchar(agreges)]
  }

  map_mot <- indexer(lex$c_mot, lex$c_morpho)
  map_lemme <- indexer(lex$c_lemme, lex$c_morpho)

  out <- unname(map_mot[termes_chr])
  out[is.na(out)] <- ""

  idx_manquant <- !nzchar(out)
  if (any(idx_manquant)) {
    out[idx_manquant] <- unname(map_lemme[termes_chr[idx_manquant]])
  }

  out[is.na(out)] <- ""
  .normaliser_type_terme_iramuteq(out)
}


extraire_stats_chd_classe <- function(res_stats_df,
                                      classe,
                                      n_max = NULL,
                                      show_negative = FALSE,
                                      max_p = 1,
                                      seuil_p_significativite = 0.05,
                                      style = c("iramuteq_clone", "legacy")) {
  style <- match.arg(style)
  max_p_num <- suppressWarnings(as.numeric(max_p))
  if (!length(max_p_num) || !is.finite(max_p_num[[1]]) || is.na(max_p_num[[1]])) {
    max_p_num <- 1
  } else {
    max_p_num <- max_p_num[[1]]
  }

  seuil_sig <- suppressWarnings(as.numeric(seuil_p_significativite))
  if (!length(seuil_sig) || !is.finite(seuil_sig[[1]]) || is.na(seuil_sig[[1]])) {
    seuil_sig <- 0.05
  } else {
    seuil_sig <- seuil_sig[[1]]
  }

  if (is.null(res_stats_df) || nrow(res_stats_df) == 0) {
    return(data.frame(Message = "Statistiques indisponibles.", stringsAsFactors = FALSE))
  }

  cl <- suppressWarnings(as.numeric(classe))
  df <- res_stats_df
  if (is.finite(cl) && !is.na(cl) && "Classe" %in% names(df)) {
    df <- df[suppressWarnings(as.numeric(df$Classe)) == cl, , drop = FALSE]
  }

  colonnes_possibles <- intersect(
    c("Terme", "chi2", "lr", "frequency", "docprop", "eff_st", "eff_total", "pourcentage", "p", "p_value", "p_value_filter", "Type", "type", "pos", "POS"),
    names(df)
  )
  df <- df[, colonnes_possibles, drop = FALSE]

  if ("p" %in% names(df) && is.finite(max_p_num) && !is.na(max_p_num) && max_p_num < 1) {
    df <- df[suppressWarnings(as.numeric(df$p)) <= max_p_num, , drop = FALSE]
  }

  if ("chi2" %in% names(df)) {
    chi2_vals <- suppressWarnings(as.numeric(df$chi2))
    if (!isTRUE(show_negative)) {
      df <- df[is.finite(chi2_vals) & chi2_vals > 0, , drop = FALSE]
      chi2_vals <- suppressWarnings(as.numeric(df$chi2))
    }

    frequency_vals <- rep(-Inf, nrow(df))
    if ("frequency" %in% names(df)) {
      frequency_vals <- suppressWarnings(as.numeric(df$frequency))
      frequency_vals[!is.finite(frequency_vals)] <- -Inf
    }

    chi2_sort <- chi2_vals
    chi2_sort[!is.finite(chi2_sort)] <- -Inf
    df <- df[order(-chi2_sort, -frequency_vals), , drop = FALSE]
  }

  if (nrow(df) == 0) {
    return(data.frame(Message = "Aucun terme disponible pour cette classe avec les filtres actuels.", stringsAsFactors = FALSE))
  }

  n_max_num <- suppressWarnings(as.numeric(n_max))
  if (is.null(n_max) || !length(n_max_num) || !is.finite(n_max_num[[1]]) || is.na(n_max_num[[1]])) {
    n_max_use <- nrow(df)
  } else {
    n_max_use <- as.integer(n_max_num[[1]])
    if (!is.finite(n_max_use) || is.na(n_max_use) || n_max_use < 1) {
      n_max_use <- nrow(df)
    }
  }
  df <- utils::head(df, n_max_use)

  if (identical(style, "iramuteq_clone")) {
    eff_st <- if ("eff_st" %in% names(df)) suppressWarnings(as.numeric(df$eff_st)) else round(suppressWarnings(as.numeric(df$docprop)) * suppressWarnings(as.numeric(df$eff_total)))
    eff_total <- if ("eff_total" %in% names(df)) suppressWarnings(as.numeric(df$eff_total)) else suppressWarnings(as.numeric(df$frequency))
    pourcentage <- if ("pourcentage" %in% names(df)) suppressWarnings(as.numeric(df$pourcentage)) else ifelse(eff_total > 0, 100 * eff_st / eff_total, NA_real_)
    chi2_vals <- if ("chi2" %in% names(df)) suppressWarnings(as.numeric(df$chi2)) else NA_real_
    p_vals <- if ("p" %in% names(df)) suppressWarnings(as.numeric(df$p)) else if ("p_value" %in% names(df)) suppressWarnings(as.numeric(df$p_value)) else NA_real_
    formes <- if ("Terme" %in% names(df)) as.character(df$Terme) else rep("", nrow(df))
    type_source <- if ("Type" %in% names(df)) df$Type else if ("type" %in% names(df)) df$type else if ("pos" %in% names(df)) df$pos else if ("POS" %in% names(df)) df$POS else rep("", nrow(df))
    types <- .normaliser_type_terme_iramuteq(type_source)

    out <- data.frame(
      num = seq_len(nrow(df)) - 1L,
      forme = formes,
      `eff. s.t.` = as.integer(round(eff_st)),
      `eff. total` = as.integer(round(eff_total)),
      pourcentage = ifelse(is.na(pourcentage), NA_character_, formatC(pourcentage, format = "f", digits = 2)),
      chi2 = ifelse(is.na(chi2_vals), NA_character_, formatC(chi2_vals, format = "f", digits = 3)),
      `p.value` = ifelse(is.na(p_vals), NA_character_, formatC(p_vals, format = "f", digits = 6)),
      Type = types,
      check.names = FALSE,
      stringsAsFactors = FALSE
    )

    if (is.finite(seuil_sig) && !is.na(seuil_sig) && nrow(out) > 0) {
      idx_non_signif <- !is.na(p_vals) & p_vals > seuil_sig
      if (any(idx_non_signif)) {
        colonnes_colorables <- names(out)
        out[idx_non_signif, colonnes_colorables] <- lapply(out[idx_non_signif, colonnes_colorables, drop = FALSE], function(col_vals) {
          ifelse(
            is.na(col_vals),
            NA_character_,
            sprintf("<span style='color:#842029;'>%s</span>", as.character(col_vals))
          )
        })
      }
    }

    return(out)
  }

  colonnes_num <- intersect(c("chi2", "lr", "docprop", "p", "p_value"), names(df))
  for (col in colonnes_num) {
    df[[col]] <- formatter_6_decimales_chd(df[[col]])
  }

  if ("frequency" %in% names(df)) {
    df$frequency <- ifelse(is.na(df$frequency), NA_character_, formatC(as.numeric(df$frequency), format = "f", digits = 6))
  }

  df
}
