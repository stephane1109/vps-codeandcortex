# Spécificités lexicales de toutes les formes selon une variable étoilée.
# Ce module complète le calcul unitaire sans en modifier les fonctions.

ecrire_specificites_lexicales_variables <- function(source, variable, index, output_dir) {
  # La classe dgCMatrix nécessite les méthodes de sous-indexation du package Matrix.
  # Ne dépendre ni du contexte de la CHD ni de l'ordre de chargement des modules R.
  if (!requireNamespace("Matrix", quietly = TRUE)) {
    stop("Le package Matrix est nécessaire aux spécificités par variables étoilées.")
  }
  if (!"package:Matrix" %in% search()) {
    suppressPackageStartupMessages(library(Matrix))
  }
  if (!is.character(variable) || length(variable) != 1L ||
      !startsWith(variable, "*")) {
    stop("Sélectionnez une variable étoilée, par exemple *source.")
  }
  if (!index %in% c("hypergeo", "chi2")) {
    stop("Indice de spécificité non reconnu.")
  }
  options <- variables_specificites_disponibles(source)
  ids <- vapply(options, function(option) as.character(option$id), character(1))
  if (!variable %in% ids) stop("Cette variable étoilée ne contient pas deux modalités valides.")

  tableau <- table_lexicale_par_modalite(source, variable)
  effectifs <- as.matrix(tableau)
  if (!nrow(effectifs) || ncol(effectifs) < 2L) {
    stop("La comparaison exige des formes lexicales et deux modalités.")
  }
  totaux_modalites <- as.numeric(colSums(effectifs))
  total <- sum(totaux_modalites)
  if (!is.finite(total) || total <= 0) stop("Le corpus lexical est vide.")

  calcul <- if (identical(index, "chi2")) {
    calculer_scores_chi2_specificites(tableau)
  } else {
    calculer_scores_hypergeometriques(tableau)
  }
  totaux_formes <- rowSums(effectifs)
  resultats <- lapply(seq_len(ncol(effectifs)), function(j) {
    observees <- as.numeric(effectifs[, j])
    attendues <- totaux_formes * totaux_modalites[[j]] / total
    probabilites <- exp(calcul$log_p[, j])
    probabilites[!is.finite(probabilites)] <- 0
    score <- as.numeric(calcul$scores[, j])
    p_ajustee <- stats::p.adjust(probabilites, method = "BH")
    data.frame(
      variable = sub("^\\*", "", variable),
      modalite = colnames(effectifs)[[j]],
      forme = rownames(effectifs),
      occurrences_modalite = as.integer(observees),
      occurrences_attendues = round(attendues, 4),
      occurrences_totales_forme = as.integer(totaux_formes),
      total_occurrences_modalite = as.integer(totaux_modalites[[j]]),
      score_specificite = round(score, 5),
      p_value = probabilites,
      p_ajustee_bh = p_ajustee,
      interpretation = ifelse(observees > attendues, "surreprésenté",
                              ifelse(observees < attendues, "sous-représenté", "attendu")),
      stringsAsFactors = FALSE,
      check.names = FALSE
    )
  })
  donnees <- do.call(rbind, resultats)
  donnees <- donnees[order(donnees$modalite, -abs(donnees$score_specificite),
                           donnees$forme), , drop = FALSE]
  rownames(donnees) <- NULL

  dir.create(output_dir, recursive = TRUE, showWarnings = FALSE)
  ecrire_csv_utf8_specificites(
    donnees, file.path(output_dir, "specificites_formes_variables.csv")
  )
  resume <- list(
    type = "formes_par_variable_etoilee",
    variable = variable,
    variable_label = sub("^\\*", "", variable),
    index = index,
    index_label = if (identical(index, "chi2")) "χ²" else "Loi hypergéométrique (Lafon)",
    n_modalities = ncol(effectifs),
    n_forms = nrow(effectifs),
    n_comparisons = nrow(donnees),
    corpus_tokens = total,
    modalities = colnames(effectifs),
    method = paste(
      "Comparaison de toutes les formes lexicales entre les modalités de",
      "la variable étoilée ; fréquences observées et attendues,",
      "score signé, p unilatérale et correction de Benjamini-Hochberg",
      "effectuée séparément dans chaque modalité."
    )
  )
  jsonlite::write_json(resume, file.path(output_dir, "resume_specificites_variables.json"),
                       auto_unbox = TRUE, pretty = TRUE)
  jsonlite::write_json(
    list(variable = variable, index = index, mode = "variables",
         format = "une ligne par forme et modalité",
         correction = "Benjamini-Hochberg par modalité"),
    file.path(output_dir, "configuration_specificites_variables.json"),
    auto_unbox = TRUE, pretty = TRUE
  )
  list(summary = resume, result = utils::head(donnees, 20L))
}
