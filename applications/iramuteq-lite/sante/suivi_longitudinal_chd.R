if (!exists("%||%", mode = "function")) {
  `%||%` <- function(x, y) {
    if (is.null(x) || length(x) == 0) y else x
  }
}

# Ce fichier reste le point d'entrée historique pour éviter de casser le pipeline.
sante_repo_root <- if (exists("repo_root", inherits = TRUE)) {
  get("repo_root", inherits = TRUE)
} else {
  normalizePath(getwd(), winslash = "/", mustWork = FALSE)
}

source(file.path(sante_repo_root, "sante", "jsd.R"), local = TRUE)
source(file.path(sante_repo_root, "sante", "jsd_rendus.R"), local = TRUE)

generer_exports_suivi_longitudinal_chd <- function(filtered_corpus_ok,
                                                   dfm_ok,
                                                   tok_ok = NULL,
                                                   classes_ok = NULL,
                                                   output_dir,
                                                   textes_indexation = NULL,
                                                   variable_suivi = NULL,
                                                   variable_filtre = NULL,
                                                   modalite_filtre = NULL,
                                                   modalites_selectionnees = character(0),
                                                   ordre_chronologique = "asc",
                                                   unite_lexicale = "unigramme",
                                                   couche_analyse = "lexicale_brute",
                                                   lexique_emotionnel = "feel",
                                                   top_n_terms = 12L,
                                                   amplification_signal = 1,
                                                   pretraitement_label = NULL,
                                                   source_dictionnaire = "lexique_fr",
                                                   filtrage_morpho = FALSE,
                                                   pos_lexique_a_conserver = character(0),
                                                   morpho_exclure_etre = FALSE,
                                                   morpho_conserver_hors_lexique = TRUE,
                                                   logger = NULL) {
  generer_exports_suivi_longitudinal_jsd(
    filtered_corpus_ok = filtered_corpus_ok,
    dfm_ok = dfm_ok,
    tok_ok = tok_ok,
    output_dir = output_dir,
    textes_indexation = textes_indexation,
    variable_suivi = variable_suivi,
    variable_filtre = variable_filtre,
    modalite_filtre = modalite_filtre,
    modalites_selectionnees = modalites_selectionnees,
    ordre_chronologique = ordre_chronologique,
    unite_lexicale = unite_lexicale,
    couche_analyse = couche_analyse,
    lexique_emotionnel = lexique_emotionnel,
    top_n_terms = top_n_terms,
    amplification_signal = amplification_signal,
    pretraitement_label = pretraitement_label,
    source_dictionnaire = source_dictionnaire,
    filtrage_morpho = filtrage_morpho,
    pos_lexique_a_conserver = pos_lexique_a_conserver,
    morpho_exclure_etre = morpho_exclure_etre,
    morpho_conserver_hors_lexique = morpho_conserver_hors_lexique,
    logger = logger
  )
}
