# Lecture des résultats DARTopic et croisement avec une variable IRaMuTeQ.
arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) < 2) {
  stop("Utilisation : Rscript analyse_resultats.R documents_themes.csv variable_profil")
}
chemin <- arguments[1]
variable <- arguments[2]
donnees <- read.csv2(chemin, fileEncoding = "UTF-8-BOM", stringsAsFactors = FALSE)
if (!variable %in% names(donnees)) stop("Variable absente dans le CSV")
tableau <- table(donnees[[variable]], donnees$theme_dominant, useNA = "ifany")
print(tableau)
if (nrow(tableau) >= 2 && ncol(tableau) >= 2) {
  resultat <- suppressWarnings(chisq.test(tableau))
  print(resultat)
  if (any(resultat$expected < 5)) {
    message("Attention : certains effectifs théoriques sont inférieurs à 5.")
  }
}
