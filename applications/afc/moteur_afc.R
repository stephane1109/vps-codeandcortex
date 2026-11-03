# Calcul d'une AFC avec FactoMineR depuis l'interface Streamlit.
# Entrées : tableau de contingence TSV, dossier de sortie et paramètres.

arguments <- commandArgs(trailingOnly = TRUE)
if (length(arguments) < 7L) {
  stop("Arguments insuffisants pour le calcul AFC.")
}
chemin_tableau <- arguments[[1L]]
dossier_sortie <- arguments[[2L]]
variable_lignes <- arguments[[3L]]
variable_colonnes <- arguments[[4L]]
nom_source <- arguments[[5L]]
effectif_initial <- as.integer(arguments[[6L]])
effectif_final <- as.integer(arguments[[7L]])

if (!requireNamespace("FactoMineR", quietly = TRUE)) {
  stop("FactoMineR n'est pas installé dans l'environnement R.")
}
if (!dir.exists(dossier_sortie)) {
  dir.create(dossier_sortie, recursive = TRUE, showWarnings = FALSE)
}

# L'interface Python a déjà filtré les observations et compté les croisements.
tableau_importe <- read.delim(
  chemin_tableau,
  sep = "\t",
  row.names = 1L,
  header = TRUE,
  check.names = FALSE,
  stringsAsFactors = FALSE,
  fileEncoding = "UTF-8",
  na.strings = NULL,
  quote = "\""
)
tableau <- as.matrix(tableau_importe)
suppressWarnings(storage.mode(tableau) <- "numeric")
if (any(!is.finite(tableau)) || any(tableau < 0) ||
    any(tableau != floor(tableau))) {
  stop("Le tableau de contingence doit comporter des effectifs entiers positifs.")
}
if (nrow(tableau) < 2L || ncol(tableau) < 2L ||
    any(rowSums(tableau) == 0) || any(colSums(tableau) == 0)) {
  stop("L'AFC exige au moins deux lignes et deux colonnes actives, sans marge nulle.")
}
if (sum(tableau) < 2L) stop("Effectif total insuffisant.")

# Le modèle conserve au maximum cinq dimensions factorielles.
nombre_axes <- min(5L, nrow(tableau) - 1L, ncol(tableau) - 1L)
resultat <- FactoMineR::CA(
  as.data.frame(tableau, check.names = FALSE),
  ncp = nombre_axes,
  graph = FALSE
)

# Vérifier l'inertie directement dans les valeurs propres FactoMineR.
# Aucun test de significativité n'est calculé en dehors de FactoMineR.
if (sum(resultat$eig[, 1L]) < 1e-12) {
  stop("L'AFC FactoMineR ne présente aucune inertie à représenter.")
}
# Utiliser le résumé natif de FactoMineR pour les résultats globaux.
resume_factominer <- capture.output(
  summary(resultat, nbelements = Inf, ncp = nombre_axes)
)

# Toutes les matrices sont exportées dans un CSV lisible avec Excel en français.
exporter_matrice <- function(matrice, nom_fichier) {
  matrice <- as.matrix(matrice)
  tableau_export <- data.frame(
    modalite = rownames(matrice),
    as.data.frame(matrice, check.names = FALSE),
    row.names = NULL,
    check.names = FALSE
  )
  utils::write.csv2(
    tableau_export,
    file = file.path(dossier_sortie, nom_fichier),
    row.names = FALSE,
    fileEncoding = "UTF-8",
    na = ""
  )
}

exporter_matrice(tableau, "01_tableau_contingence.csv")
exporter_matrice(prop.table(tableau, 1L) * 100, "04_profils_lignes_pourcent.csv")
exporter_matrice(prop.table(tableau, 2L) * 100, "05_profils_colonnes_pourcent.csv")
exporter_matrice(resultat$eig, "06_valeurs_propres_inerties.csv")
exporter_matrice(resultat$row$coord, "07_coordonnees_lignes.csv")
exporter_matrice(resultat$col$coord, "08_coordonnees_colonnes.csv")
exporter_matrice(resultat$row$contrib, "09_contributions_lignes.csv")
exporter_matrice(resultat$col$contrib, "10_contributions_colonnes.csv")
exporter_matrice(resultat$row$cos2, "11_cos2_lignes.csv")
exporter_matrice(resultat$col$cos2, "12_cos2_colonnes.csv")

# Sélection statistique avec la méthode native de FactoMineR.
# descfreq() utilise un test hypergéométrique pour caractériser les
# associations entre les modalités de lignes et de colonnes.
# Une modalité est conservée si au moins une association a p <= 0,05.
# Cette significativité n'est pas celle d'une coordonnée factorielle.
caracterisations_lignes <- FactoMineR::descfreq(
  as.data.frame(tableau, check.names = FALSE), proba = 0.05
)
caracterisations_colonnes <- FactoMineR::descfreq(
  as.data.frame(t(tableau), check.names = FALSE), proba = 0.05
)

resumer_modalite <- function(type_modalite, indice, caracterisations) {
  if (type_modalite == "ligne") {
    nom_modalite <- rownames(tableau)[[indice]]
    nom_variable <- variable_lignes
    effectif <- as.integer(rowSums(tableau)[[indice]])
  } else {
    nom_modalite <- colnames(tableau)[[indice]]
    nom_variable <- variable_colonnes
    effectif <- as.integer(colSums(tableau)[[indice]])
  }
  caracterisation <- caracterisations[[indice]]
  if (is.null(caracterisation)) {
    p_values <- numeric(0)
    noms_associes <- character(0)
  } else {
    caracterisation <- as.matrix(caracterisation)
    p_values <- as.numeric(caracterisation[, "p.value"])
    noms_associes <- rownames(caracterisation)
  }
  retenues <- is.finite(p_values) & p_values <= 0.05
  p_minimale <- if (any(retenues)) min(p_values[retenues]) else NA_real_
  data.frame(
    variable = nom_variable,
    type_modalite = type_modalite,
    modalite = nom_modalite,
    effectif = effectif,
    p_value_min = p_minimale,
    associations_significatives = paste(noms_associes[retenues], collapse = " ; "),
    methode = "FactoMineR::descfreq (test hypergéométrique)",
    significative_005 = any(retenues),
    stringsAsFactors = FALSE
  )
}

significativite_modalites <- do.call(rbind, c(
  lapply(seq_len(nrow(tableau)), function(i) {
    resumer_modalite("ligne", i, caracterisations_lignes)
  }),
  lapply(seq_len(ncol(tableau)), function(i) {
    resumer_modalite("colonne", i, caracterisations_colonnes)
  })
))
nombre_significatives <- sum(significativite_modalites$significative_005)
# Exporter toutes les modalités, y compris celles masquées du plan.
utils::write.csv2(
  significativite_modalites,
  file.path(dossier_sortie, "significativite_modalites_factominer.csv"),
  row.names = FALSE, fileEncoding = "UTF-8", na = ""
)

# Mise en forme du plan factoriel, y compris si un seul axe est disponible.
limites_axes <- function(valeurs, proportion = 0.22) {
  bornes <- range(valeurs, finite = TRUE)
  amplitude <- diff(bornes)
  marge <- if (amplitude < 1e-9) 0.75 else amplitude * proportion
  bornes + c(-marge, marge)
}

dessiner_plan <- function() {
  lignes <- as.matrix(resultat$row$coord)
  colonnes <- as.matrix(resultat$col$coord)
  deux_axes <- ncol(lignes) >= 2L && ncol(colonnes) >= 2L
  abscisses_lignes <- lignes[, 1L]
  abscisses_colonnes <- colonnes[, 1L]
  ordonnees_lignes <- if (deux_axes) lignes[, 2L] else rep(0.12, nrow(lignes))
  ordonnees_colonnes <- if (deux_axes) colonnes[, 2L] else rep(-0.12, nrow(colonnes))
  inerties <- resultat$eig[, 2L]
  nom_x <- sprintf("Axe 1 (%.1f %% d'inertie)", inerties[[1L]])
  nom_y <- if (deux_axes) {
    sprintf("Axe 2 (%.1f %% d'inertie)", inerties[[2L]])
  } else {
    "Disposition illustrative (aucun axe 2)"
  }
  # La sélection ne porte que sur le plan à deux dimensions demandé.
  # Les coordonnées et les inerties proviennent toujours de l'AFC complète.
  visibles_lignes <- if (deux_axes) {
    significativite_modalites$significative_005[
      significativite_modalites$type_modalite == "ligne"
    ]
  } else {
    rep(TRUE, nrow(lignes))
  }
  visibles_colonnes <- if (deux_axes) {
    significativite_modalites$significative_005[
      significativite_modalites$type_modalite == "colonne"
    ]
  } else {
    rep(TRUE, nrow(colonnes))
  }
  x_visibles <- c(
    abscisses_lignes[visibles_lignes],
    abscisses_colonnes[visibles_colonnes]
  )
  y_visibles <- c(
    ordonnees_lignes[visibles_lignes],
    ordonnees_colonnes[visibles_colonnes]
  )
  # Aucun point significatif : conserver un plan lisible avec axes à l'origine.
  if (!length(x_visibles)) {
    x_visibles <- c(-1, 1)
    y_visibles <- c(-1, 1)
  }
  par(mar = c(6.5, 5, 4, 2))
  plot(
    NA_real_, NA_real_, type = "n",
    xlim = limites_axes(c(0, x_visibles)),
    ylim = limites_axes(c(0, y_visibles), 0.3),
    xlab = nom_x, ylab = nom_y,
    main = paste("AFC :", variable_lignes, "x", variable_colonnes)
  )
  abline(h = 0, v = 0, col = "grey75", lty = 2)
  if (any(visibles_lignes)) {
    points(abscisses_lignes[visibles_lignes], ordonnees_lignes[visibles_lignes],
           col = "#2166AC", pch = 16, cex = 1.2)
    text(abscisses_lignes[visibles_lignes], ordonnees_lignes[visibles_lignes],
         rownames(lignes)[visibles_lignes], pos = 3, cex = 0.75,
         col = "#2166AC", xpd = TRUE)
  }
  if (any(visibles_colonnes)) {
    points(abscisses_colonnes[visibles_colonnes],
           ordonnees_colonnes[visibles_colonnes],
           col = "#B2182B", pch = 17, cex = 1.25)
    text(abscisses_colonnes[visibles_colonnes],
         ordonnees_colonnes[visibles_colonnes],
         rownames(colonnes)[visibles_colonnes],
         pos = if (deux_axes) 3 else 1, cex = 0.75,
         col = "#B2182B", xpd = TRUE)
  }
  if (any(visibles_lignes) || any(visibles_colonnes)) {
    legend("topright", c("Modalités en lignes", "Modalités en colonnes"),
           pch = c(16, 17), col = c("#2166AC", "#B2182B"), bty = "n")
  }
  if (deux_axes) {
    mtext(
      paste0("Modalités affichées : p <= 0,05 (",
             nombre_significatives, "/", nrow(significativite_modalites),
             "). FactoMineR::descfreq (hypergéométrique)."),
      side = 1, line = 4.3, cex = 0.7
    )
    if (!nombre_significatives) {
      text(0, 0, "Aucune modalité significative (p <= 0,05)",
           pos = 3, cex = 0.9, col = "grey35")
    }
  } else {
    mtext("Un seul axe : les modalités ne sont pas filtrées ; décalage vertical artificiel.",
          side = 1, line = 4.3, cex = 0.7)
  }
}

dessiner_inerties <- function() {
  inerties <- resultat$eig[, 2L]
  par(mar = c(5, 5, 4, 2))
  barplot(inerties, names.arg = paste("Axe", seq_along(inerties)),
          col = "grey55", ylim = c(0, 105),
          ylab = "Pourcentage d'inertie", main = "Inertie des axes factoriels")
}

gg <- function(nom, action) {
  grDevices::png(file.path(dossier_sortie, nom), width = 1600, height = 1100, res = 160)
  tryCatch(action(), finally = grDevices::dev.off())
}
gg("13_plan_factoriel.png", dessiner_plan)
grDevices::pdf(file.path(dossier_sortie, "14_plan_factoriel.pdf"), width = 12, height = 8.5)
tryCatch(dessiner_plan(), finally = grDevices::dev.off())
gg("15_inerties.png", dessiner_inerties)

# Indicateurs issus des résultats FactoMineR, sans nouveau test.
statistiques <- data.frame(
  indicateur = c(
    "Source", "Variable en lignes", "Variable en colonnes",
    "Observations initiales", "Observations analysées",
    "Modalités lignes", "Modalités colonnes", "Axes factoriels",
    "Inertie totale (FactoMineR)",
    "Modalités significatives (p <= 0,05)", "Modalités au total",
    "Méthode de significativité des modalités"
  ),
  valeur = c(
    nom_source, variable_lignes, variable_colonnes,
    as.character(effectif_initial), as.character(effectif_final),
    as.character(nrow(tableau)), as.character(ncol(tableau)),
    as.character(nombre_axes),
    format(sum(resultat$eig[, 1L]), digits = 9),
    as.character(nombre_significatives),
    as.character(nrow(significativite_modalites)),
    "FactoMineR::descfreq, test hypergéométrique, seuil p <= 0,05"
  ),
  stringsAsFactors = FALSE
)
utils::write.csv2(statistiques,
  file.path(dossier_sortie, "16_resultats_statistiques.csv"),
  row.names = FALSE, fileEncoding = "UTF-8")

rapport <- c(
  "ANALYSE FACTORIELLE DES CORRESPONDANCES — FactoMineR",
  paste("Source :", nom_source),
  paste("Variables :", variable_lignes, "x", variable_colonnes),
  paste("Observations initiales :", effectif_initial),
  paste("Observations analysées :", effectif_final),
  paste("Dimensions du tableau :", nrow(tableau), "x", ncol(tableau)),
  paste("Inertie totale FactoMineR :", signif(sum(resultat$eig[, 1L]), 7)),
  paste("Modalités significatives (p <= 0,05) :", nombre_significatives,
        "/", nrow(significativite_modalites)),
  "Modalités retenues par FactoMineR::descfreq (test hypergéométrique, p <= 0,05).",
  "Le seuil porte sur l'association entre modalités, pas sur leur position factorielle.",
  "La p-value minimale est celle des associations significatives renvoyées par FactoMineR.",
  "Aucune correction Benjamini-Hochberg ni test Chi-deux par modalité ajouté.",
  "Fichier significativite_modalites_factominer.csv : toutes les modalités.",
  "",
  "VALEURS PROPRES ET INERTIES (%)",
  capture.output(print(round(resultat$eig, 4))),
  "",
  "RÉSUMÉ NATIF DE L'AFC PAR FACTOMINER",
  resume_factominer,
  "",
  "AVERTISSEMENTS METHODOLOGIQUES",
  "L'AFC décrit des associations entre variables catégorielles sans établir de causalité.",
  "La position des modalités de groupes différents n'est pas une mesure directe de leur proximité.",
  "Lire les contributions, cos2 et profils avant de conclure.",
  "Vues et taux d'engagement partagent un dénominateur : association mécanique possible.",
  if (effectif_final < 30) "Effectif inférieur à 30 : interprétation exploratoire uniquement." else "",
  if (nombre_axes == 1L) "Un seul axe existe : le décalage vertical du graphique est illustratif." else ""
)
writeLines(rapport, file.path(dossier_sortie, "00_rapport_afc.txt"), useBytes = TRUE)
cat("AFC FactoMineR terminée. ", effectif_final, " observations analysées.\n", sep = "")
