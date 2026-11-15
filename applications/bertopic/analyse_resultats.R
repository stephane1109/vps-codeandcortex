# Croisement des thèmes BERTopic et des métadonnées IRaMuTeQ.
# Exemple : Rscript analyse_resultats.R documents_themes.csv variable_profil
arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) < 2) {
  stop("Utilisation : Rscript analyse_resultats.R documents_themes.csv variable_profil [sortie.csv]")
}
chemin <- arguments[1]
variable <- arguments[2]
donnees <- read.csv2(chemin, fileEncoding = "UTF-8-BOM",
                      stringsAsFactors = FALSE, check.names = FALSE)
if (!variable %in% names(donnees)) {
  stop(paste("Variable absente :", variable))
}
colonnes_requises <- c("theme_dominant", "statut_analyse")
if (!all(colonnes_requises %in% names(donnees))) {
  stop("Colonnes de résultats BERTopic manquantes.")
}
valides <- donnees[donnees$statut_analyse != "non_analyse", , drop = FALSE]
if (nrow(valides) == 0) {
  stop("Aucun texte analysé.")
}
modalites <- as.character(valides[[variable]])
modalites[is.na(modalites) | modalites == ""] <- "(absent)"
tableau <- table(modalites, valides$theme_dominant)
print(tableau)
pourcentages <- round(100 * prop.table(tableau, 1), 2)
print(pourcentages)
if (length(arguments) >= 3) {
  write.csv2(as.data.frame.matrix(tableau), arguments[3], row.names = TRUE,
             fileEncoding = "UTF-8")
}
if (nrow(tableau) >= 2 && ncol(tableau) >= 2) {
  test <- suppressWarnings(chisq.test(tableau))
  print(test)
  if (any(test$expected < 5)) {
    warning("Certaines fréquences théoriques sont inférieures à 5.")
  }
  effectif <- sum(tableau)
  v_cramer <- sqrt(as.numeric(test$statistic) /
                   (effectif * min(nrow(tableau) - 1, ncol(tableau) - 1)))
  cat("V de Cramér :", round(v_cramer, 3), "\n")
}
