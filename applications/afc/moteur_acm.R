# Analyse des correspondances multiples avec le seul moteur FactoMineR.
# Entrées : données catégorielles TSV, répertoire de sortie et métadonnées.
arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) < 5L) {
  stop("Arguments insuffisants pour le calcul de l'ACM.")
}
chemin_donnees <- arguments[[1L]]
dossier_sortie <- arguments[[2L]]
nom_source <- arguments[[3L]]
effectif_initial <- as.integer(arguments[[4L]])
effectif_final <- as.integer(arguments[[5L]])
methode_calcul <- if (length(arguments) >= 6L) arguments[[6L]] else "Indicator"
if (!(methode_calcul %in% c("Indicator", "Burt"))) {
  stop("Méthode ACM invalide : utiliser Indicator ou Burt.")
}
libelle_methode <- if (methode_calcul == "Indicator") {
  "Tableau disjonctif complet (TDC)"
} else {
  "Tableau de Burt"
}

if (!requireNamespace("FactoMineR", quietly = TRUE)) {
  stop("FactoMineR n'est pas installé dans l'environnement R.")
}
if (!dir.exists(dossier_sortie)) {
  dir.create(dossier_sortie, recursive = TRUE, showWarnings = FALSE)
}

# Chaque ligne représente un individu et chaque colonne une variable active.
donnees <- read.delim(
  chemin_donnees, sep = "\t", header = TRUE, check.names = FALSE,
  stringsAsFactors = FALSE, fileEncoding = "UTF-8",
  na.strings = NULL, quote = "\""
)
if (ncol(donnees) < 3L || nrow(donnees) < 3L) {
  stop("L'ACM nécessite trois variables et trois observations au minimum.")
}
for (nom in colnames(donnees)) {
  donnees[[nom]] <- factor(donnees[[nom]])
}
nombre_modalites <- vapply(donnees, nlevels, integer(1))
if (any(nombre_modalites < 2L)) {
  stop("Chaque variable active de l'ACM doit avoir au moins deux modalités.")
}
nombre_axes <- min(
  5L, nrow(donnees) - 1L, sum(nombre_modalites) - ncol(donnees)
)
resultat <- FactoMineR::MCA(
  donnees, ncp = nombre_axes, graph = FALSE, method = methode_calcul
)
if (sum(resultat$eig[, 1L]) < 1e-12) {
  stop("Aucune inertie ne peut être représentée dans cette ACM.")
}

# Conserver les matrices natives : aucune autre méthode statistique n'est appelée.
exporter_matrice <- function(matrice, nom_fichier, nom_identifiant = "modalite") {
  if (is.null(matrice)) return(invisible(NULL))
  matrice <- as.matrix(matrice)
  tableau_export <- data.frame(
    identifiant = rownames(matrice),
    as.data.frame(matrice, check.names = FALSE),
    row.names = NULL, check.names = FALSE
  )
  names(tableau_export)[1L] <- nom_identifiant
  utils::write.csv2(
    tableau_export, file.path(dossier_sortie, nom_fichier),
    row.names = FALSE, fileEncoding = "UTF-8", na = ""
  )
}
utils::write.csv2(
  donnees, file.path(dossier_sortie, "01_donnees_acm_filtrees.csv"),
  row.names = FALSE, fileEncoding = "UTF-8"
)
exporter_matrice(resultat$eig, "06_valeurs_propres_inerties.csv")
exporter_matrice(resultat$var$coord, "07_coordonnees_modalites.csv")
exporter_matrice(resultat$var$contrib, "08_contributions_modalites.csv")
exporter_matrice(resultat$var$cos2, "09_cos2_modalites.csv")
exporter_matrice(resultat$var$v.test, "10_vtest_modalites.csv")
exporter_matrice(resultat$var$eta2, "11_rapports_correlation_variables.csv", "variable")
exporter_matrice(resultat$ind$coord, "12_coordonnees_individus.csv", "individu")

# Exporter les deux représentations du corpus lorsque leur volume le permet.
# Ces tableaux ne remplacent jamais l'analyse native FactoMineR::MCA().
nombre_colonnes_tdc <- sum(nombre_modalites)
export_tdc <- as.double(nrow(donnees)) * nombre_colonnes_tdc <= 2000000
export_burt <- as.double(nombre_colonnes_tdc)^2 <= 1000000
if (export_tdc || export_burt) {
  tableau_tdc <- FactoMineR::tab.disjonctif(donnees)
  if (export_tdc) {
    utils::write.csv2(
      as.data.frame(tableau_tdc, check.names = FALSE),
      file.path(dossier_sortie, "tdc.csv"),
      row.names = FALSE, fileEncoding = "UTF-8"
    )
  }
  if (export_burt) {
    tableau_burt <- crossprod(as.matrix(tableau_tdc))
    exporter_matrice(tableau_burt, "burt.csv")
  }
}

# FactoMineR définit les valeurs propres du tableau de Burt comme les
# carrés de celles du tableau disjonctif. Montrer les deux conventions
# sans effectuer de second test statistique ni recalculer les axes.
valeurs_propres_tdc <- as.numeric(resultat$eig[, 1L])
if (methode_calcul == "Burt") {
  valeurs_propres_tdc <- sqrt(pmax(valeurs_propres_tdc, 0))
}
valeurs_propres_burt <- valeurs_propres_tdc^2
pourcentages_tdc <- 100 * valeurs_propres_tdc / sum(valeurs_propres_tdc)
pourcentages_burt <- 100 * valeurs_propres_burt / sum(valeurs_propres_burt)
comparaison_inerties <- data.frame(
  axe = rownames(resultat$eig),
  valeur_propre_tdc = valeurs_propres_tdc,
  inertie_tdc_pourcentage = pourcentages_tdc,
  inertie_tdc_cumulee = cumsum(pourcentages_tdc),
  valeur_propre_burt = valeurs_propres_burt,
  inertie_burt_pourcentage = pourcentages_burt,
  inertie_burt_cumulee = cumsum(pourcentages_burt),
  stringsAsFactors = FALSE
)
utils::write.csv2(
  comparaison_inerties,
  file.path(dossier_sortie, "18_comparaison_inerties_tdc_burt.csv"),
  row.names = FALSE, fileEncoding = "UTF-8"
)

coordonnees <- as.matrix(resultat$var$coord)
if (is.null(rownames(coordonnees))) {
  stop("FactoMineR ne fournit pas les noms des modalités actives.")
}
deux_axes <- ncol(coordonnees) >= 2L
axes_description <- seq_len(min(2L, ncol(coordonnees)))

# Les p-values proviennent exclusivement de FactoMineR::dimdesc().
# L'ACM n'effectue aucune sélection par défaut : le plan complet est prioritaire.
description <- FactoMineR::dimdesc(
  resultat, axes = axes_description, proba = 0.05
)
noms_modalites <- rownames(coordonnees)
p_axe_1 <- rep(NA_real_, length(noms_modalites))
p_axe_2 <- rep(NA_real_, length(noms_modalites))
liste_p <- list(p_axe_1, p_axe_2)
for (i in seq_along(axes_description)) {
  caracteristiques <- description[[i]]$category
  if (is.null(caracteristiques) || !nrow(as.matrix(caracteristiques))) next
  caracteristiques <- as.matrix(caracteristiques)
  if (!"p.value" %in% colnames(caracteristiques)) {
    stop("La description native de FactoMineR ne contient pas p.value.")
  }
  identifiants <- match(rownames(caracteristiques), noms_modalites)
  valides <- !is.na(identifiants)
  liste_p[[i]][identifiants[valides]] <- as.numeric(
    caracteristiques[valides, "p.value"]
  )
}
p_axe_1 <- liste_p[[1L]]
p_axe_2 <- liste_p[[2L]]
p_minimale <- apply(
  cbind(p_axe_1, p_axe_2), 1L,
  function(ligne) {
    valides <- ligne[is.finite(ligne)]
    if (length(valides)) min(valides) else NA_real_
  }
)
est_significative <- is.finite(p_minimale) & p_minimale <= 0.05
tableau_significativite <- data.frame(
  modalite = noms_modalites,
  p_value_axe_1 = p_axe_1,
  p_value_axe_2 = p_axe_2,
  p_value_min = p_minimale,
  significative_005 = est_significative,
  methode = "FactoMineR::dimdesc (axes représentés)",
  stringsAsFactors = FALSE
)
utils::write.csv2(
  tableau_significativite,
  file.path(dossier_sortie, "significativite_modalites_factominer.csv"),
  row.names = FALSE, fileEncoding = "UTF-8", na = ""
)

# Dessiner les modalités de toutes les variables actives sur les mêmes axes.
limites_axes <- function(valeurs, proportion = 0.22) {
  bornes <- range(valeurs, finite = TRUE)
  amplitude <- diff(bornes)
  marge <- if (amplitude < 1e-9) 0.75 else amplitude * proportion
  bornes + c(-marge, marge)
}
dessiner_plan <- function(filtrer_modalites = FALSE) {
  x <- coordonnees[, 1L]
  y <- if (deux_axes) coordonnees[, 2L] else rep(0, nrow(coordonnees))
  visibles <- if (deux_axes && filtrer_modalites) {
    tableau_significativite$significative_005
  } else {
    rep(TRUE, nrow(coordonnees))
  }
  if (!any(visibles)) {
    xlim <- c(-1, 1)
    ylim <- c(-1, 1)
  } else {
    xlim <- limites_axes(c(0, x[visibles]))
    ylim <- limites_axes(c(0, y[visibles]), 0.3)
  }
  inerties <- resultat$eig[, 2L]
  etiquette_x <- sprintf("Axe 1 (%.1f %% d'inertie)", inerties[[1L]])
  etiquette_y <- if (deux_axes) {
    sprintf("Axe 2 (%.1f %% d'inertie)", inerties[[2L]])
  } else {
    "Aucun axe 2"
  }
  par(mar = c(6.5, 5, 4, 2))
  plot(
    NA_real_, NA_real_, type = "n", xlim = xlim, ylim = ylim,
    xlab = etiquette_x, ylab = etiquette_y,
    main = paste("ACM —", libelle_methode, ":",
                 paste(colnames(donnees), collapse = " × "))
  )
  abline(h = 0, v = 0, col = "grey75", lty = 2)
  if (any(visibles)) {
    points(x[visibles], y[visibles], pch = 16, col = "#2166AC", cex = 1.1)
    text(x[visibles], y[visibles], noms_modalites[visibles],
         pos = 3, cex = 0.72, col = "#2166AC", xpd = TRUE)
  }
  if (filtrer_modalites && deux_axes) {
    mtext(
      sprintf(
        "Modalités caractéristiques des axes 1 et 2 : p <= 0,05 (%d/%d). FactoMineR::dimdesc.",
        sum(visibles), length(visibles)
      ), side = 1, line = 4.3, cex = 0.7
    )
    if (!any(visibles)) {
      text(0, 0, "Aucune modalité significative (p <= 0,05)",
           pos = 3, cex = 0.85, col = "grey35")
    }
  } else if (!deux_axes) {
    mtext("Un seul axe factoriel : aucune sélection de modalités appliquée.",
          side = 1, line = 4.3, cex = 0.7)
  } else {
    mtext("Plan complet : toutes les modalités actives des variables sont affichées.",
          side = 1, line = 4.3, cex = 0.7)
  }
}
dessiner_inerties <- function() {
  inerties <- resultat$eig[, 2L]
  par(mar = c(5, 5, 4, 2))
  barplot(
    inerties, names.arg = paste("Axe", seq_along(inerties)),
    col = "grey55", ylim = c(0, 105),
    ylab = "Pourcentage d'inertie", main = "Inertie des axes de l'ACM"
  )
}
dessiner_png <- function(nom, action) {
  grDevices::png(
    file.path(dossier_sortie, nom),
    width = 1600, height = 1100, res = 160
  )
  tryCatch(action(), finally = grDevices::dev.off())
}
dessiner_png("13_plan_factoriel.png", function() dessiner_plan(FALSE))
grDevices::pdf(
  file.path(dossier_sortie, "14_plan_factoriel.pdf"), width = 12, height = 8.5
)
tryCatch(dessiner_plan(FALSE), finally = grDevices::dev.off())
dessiner_png(
  "13_plan_factoriel_significatif.png", function() dessiner_plan(TRUE)
)
grDevices::pdf(
  file.path(dossier_sortie, "14_plan_factoriel_significatif.pdf"),
  width = 12, height = 8.5
)
tryCatch(dessiner_plan(TRUE), finally = grDevices::dev.off())
dessiner_png("15_inerties.png", dessiner_inerties)

statistiques <- data.frame(
  indicateur = c(
    "Source", "Méthode", "Variables actives", "Observations initiales",
    "Observations analysées", "Nombre de variables",
    "Modalités actives", "Axes factoriels",
    "Inertie totale (FactoMineR)",
    "Modalités significatives (p <= 0,05)",
    "Modalités au total", "Méthode de significativité des modalités"
  ),
  valeur = c(
    nom_source, paste0("ACM — ", libelle_methode, " (FactoMineR::MCA)"),
    paste(colnames(donnees), collapse = " ; "),
    as.character(effectif_initial), as.character(effectif_final),
    as.character(ncol(donnees)), as.character(nrow(coordonnees)),
    as.character(ncol(coordonnees)),
    format(sum(resultat$eig[, 1L]), digits = 9),
    as.character(sum(est_significative)), as.character(nrow(coordonnees)),
    "FactoMineR::dimdesc, modalités caractéristiques des axes 1 et 2"
  ),
  stringsAsFactors = FALSE
)
utils::write.csv2(
  statistiques,
  file.path(dossier_sortie, "16_resultats_statistiques.csv"),
  row.names = FALSE, fileEncoding = "UTF-8"
)

rapport <- c(
  "ANALYSE DES CORRESPONDANCES MULTIPLES — FactoMineR",
  paste("Source :", nom_source),
  paste("Méthode de calcul :", libelle_methode),
  paste("Appel natif : FactoMineR::MCA(method =", methode_calcul, ")"),
  paste("Variables actives :", paste(colnames(donnees), collapse = " ; ")),
  paste("Observations initiales :", effectif_initial),
  paste("Observations analysées :", effectif_final),
  paste("Modalités actives :", nrow(coordonnees)),
  paste("Inertie totale :", signif(sum(resultat$eig[, 1L]), 7)),
  "",
  "VALEURS PROPRES ET INERTIES (%)",
  capture.output(print(round(resultat$eig, 4))),
  "",
  "COMPARAISON DES INERTIES — TDC ET BURT",
  "Les valeurs propres de Burt sont les carrés des valeurs propres du TDC.",
  "Les pourcentages d'inertie ont donc des dénominateurs différents.",
  capture.output(print(round(comparaison_inerties, 4))),
  "",
  "REPRÉSENTATIONS EXPORTÉES",
  if (export_tdc) "Tableau disjonctif complet : tdc.csv." else
    "TDC non exporté : plus de 2 000 000 cellules.",
  if (export_burt) "Tableau de Burt : burt.csv." else
    "Burt non exporté : plus de 1 000 000 cellules.",
  "",
  "DESCRIPTION DES AXES PAR FactoMineR::dimdesc (p <= 0,05)",
  capture.output(print(description)),
  "",
  "AVERTISSEMENTS MÉTHODOLOGIQUES",
  "L'ACM repose exclusivement sur les variables qualitatives actives.",
  "Les inerties TDC et Burt ne se comparent pas comme deux estimations d'une même proportion.",
  "Le filtre optionnel concerne les modalités caractéristiques des axes 1 et 2.",
  "Les deux versions du plan utilisent les mêmes coordonnées FactoMineR."
)
writeLines(
  rapport, file.path(dossier_sortie, "00_rapport_acm.txt"), useBytes = TRUE
)
cat(
  "ACM FactoMineR terminée. ", effectif_final,
  " observations analysées.\n", sep = ""
)
