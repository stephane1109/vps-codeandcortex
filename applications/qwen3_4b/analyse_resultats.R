# Croisement exploratoire entre une variable de corpus et un thème Qwen.
arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) < 3) {
  stop(
    "Utilisation : Rscript analyse_resultats.R ",
    "matrice_annotations_qwen.csv source_texte final_theme_1"
  )
}
donnees <- read.csv2(
  arguments[1], fileEncoding = "UTF-8-BOM", stringsAsFactors = FALSE
)
variable <- arguments[2]
categorie <- arguments[3]
if (!all(c(variable, categorie, "statut_codage") %in% names(donnees))) {
  stop("Colonne absente du fichier fourni.")
}
donnees <- donnees[donnees$statut_codage == "ok", , drop = FALSE]
tableau <- table(
  donnees[[variable]], donnees[[categorie]], useNA = "ifany"
)
print(tableau)
if (nrow(tableau) >= 2 && ncol(tableau) >= 2) {
  resultat <- suppressWarnings(chisq.test(tableau))
  print(resultat)
  if (any(resultat$expected < 5)) {
    message("Attention : certains effectifs théoriques sont inférieurs à 5.")
  }
}
