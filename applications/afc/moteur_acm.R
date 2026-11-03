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
lire_indices_supplementaires <- function(texte) {
  if (!nzchar(texte)) return(integer(0))
  indices <- as.integer(strsplit(texte, ",", fixed = TRUE)[[1L]])
  if (anyNA(indices) || anyDuplicated(indices)) {
    stop("Indices des variables supplémentaires invalides.")
  }
  indices
}
indices_quali_sup <- if (length(arguments) >= 7L) {
  lire_indices_supplementaires(arguments[[7L]])
} else {
  integer(0)
}
indices_quanti_sup <- if (length(arguments) >= 8L) {
  lire_indices_supplementaires(arguments[[8L]])
} else {
  integer(0)
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
indices_non_actifs <- c(indices_quali_sup, indices_quanti_sup)
if (anyDuplicated(indices_non_actifs) ||
    any(indices_non_actifs < 1L | indices_non_actifs > ncol(donnees))) {
  stop("Indices des variables supplémentaires incompatibles avec le CSV.")
}
indices_actifs <- setdiff(seq_len(ncol(donnees)), indices_non_actifs)
if (length(indices_actifs) < 3L || nrow(donnees) < 3L) {
  stop("L'ACM nécessite trois variables actives et trois observations.")
}
for (indice in c(indices_actifs, indices_quali_sup)) {
  donnees[[indice]] <- factor(donnees[[indice]])
}
for (indice in indices_quanti_sup) {
  valeurs <- as.character(donnees[[indice]])
  valeurs[!nzchar(valeurs) | valeurs == "NA"] <- NA_character_
  nombres <- suppressWarnings(as.numeric(valeurs))
  if (any(!is.na(valeurs) & is.na(nombres))) {
    stop("Variable quantitative supplémentaire non numérique : ",
         colnames(donnees)[[indice]])
  }
  if (sum(is.finite(nombres)) < 3L || length(unique(nombres[is.finite(nombres)])) < 2L) {
    stop("Variable quantitative supplémentaire sans dispersion suffisante : ",
         colnames(donnees)[[indice]])
  }
  donnees[[indice]] <- nombres
}
donnees_actives <- donnees[, indices_actifs, drop = FALSE]
nombre_modalites <- vapply(donnees_actives, nlevels, integer(1))
if (any(nombre_modalites < 2L)) {
  stop("Chaque variable active de l'ACM doit avoir au moins deux modalités.")
}
nombre_axes <- min(
  5L, nrow(donnees) - 1L,
  sum(nombre_modalites) - ncol(donnees_actives)
)
resultat <- FactoMineR::MCA(
  donnees, ncp = nombre_axes, graph = FALSE, method = methode_calcul,
  quali.sup = if (length(indices_quali_sup)) indices_quali_sup else NULL,
  quanti.sup = if (length(indices_quanti_sup)) indices_quanti_sup else NULL
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

# Les variables supplémentaires sont projetées nativement par MCA().
# Aucune contribution aux axes n'est calculée pour ces variables.
if (length(indices_quali_sup)) {
  exporter_matrice(
    resultat$quali.sup$coord,
    "21_coordonnees_qualitatives_supplementaires.csv"
  )
  exporter_matrice(
    resultat$quali.sup$cos2,
    "22_cos2_qualitatives_supplementaires.csv"
  )
  exporter_matrice(
    resultat$quali.sup$v.test,
    "23_vtest_qualitatives_supplementaires.csv"
  )
  exporter_matrice(
    resultat$quali.sup$eta2,
    "24_eta2_qualitatives_supplementaires.csv", "variable"
  )
}
if (length(indices_quanti_sup)) {
  exporter_matrice(
    resultat$quanti.sup$coord,
    "25_coordonnees_quantitatives_supplementaires.csv", "variable"
  )
}

# Exporter les deux représentations du corpus lorsque leur volume le permet.
# Ces tableaux ne remplacent jamais l'analyse native FactoMineR::MCA().
nombre_colonnes_tdc <- sum(nombre_modalites)
export_tdc <- as.double(nrow(donnees)) * nombre_colonnes_tdc <= 2000000
export_burt <- as.double(nombre_colonnes_tdc)^2 <= 1000000
if (export_tdc || export_burt) {
  tableau_tdc <- FactoMineR::tab.disjonctif(donnees_actives)
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
# FactoMineR conserve le regroupement des modalités dans l'ordre des
# variables actives. Le nombre de modalités provient de son propre
# tableau factoriel, pour ne pas associer de mauvaises couleurs en cas
# de modalités portant le même nom dans plusieurs variables.
variables_actives <- resultat$call$X[, resultat$call$quali, drop = FALSE]
noms_variables_actives <- names(variables_actives)
effectifs_modalites <- vapply(variables_actives, nlevels, integer(1))
variables_modalites <- rep(
  noms_variables_actives, times = effectifs_modalites
)
if (length(variables_modalites) != nrow(coordonnees)) {
  stop(
    "Impossible d'associer les modalités aux variables de FactoMineR : ",
    "le nombre de modalités ne correspond pas aux coordonnées."
  )
}

# Une couleur par variable, commune à toutes ses modalités et conservée
# sur les plans complets et filtrés. La palette est déterministe.
couleurs_variables <- stats::setNames(
  grDevices::hcl.colors(
    length(noms_variables_actives), palette = "Dark 3"
  ),
  noms_variables_actives
)
couleurs_modalites <- unname(couleurs_variables[variables_modalites])
if (anyNA(couleurs_modalites)) {
  stop("Une modalité active ne possède pas de couleur de variable.")
}
tableau_couleurs <- data.frame(
  variable = noms_variables_actives,
  couleur_hex = unname(couleurs_variables),
  nombre_modalites = unname(as.integer(effectifs_modalites)),
  stringsAsFactors = FALSE
)
utils::write.csv2(
  tableau_couleurs,
  file.path(dossier_sortie, "19_couleurs_variables.csv"),
  row.names = FALSE, fileEncoding = "UTF-8"
)

deux_axes <- ncol(coordonnees) >= 2L
axes_description <- seq_len(min(2L, ncol(coordonnees)))

# Coordonnées natives des variables illustratives : elles n'interviennent
# ni dans les valeurs propres ni dans le calcul de la significativité
# des modalités actives.
coordonnees_quali_sup <- if (length(indices_quali_sup)) {
  as.matrix(resultat$quali.sup$coord)
} else {
  NULL
}
coordonnees_quanti_sup <- if (length(indices_quanti_sup)) {
  as.matrix(resultat$quanti.sup$coord)
} else {
  NULL
}

# Utiliser exclusivement les p-values produites par FactoMineR::dimdesc().
# La fonction native condes(), appelée par dimdesc(), nomme les catégories
# "variable=modalité". Les noms des coordonnées MCA peuvent se limiter à
# la modalité (avec adaptation des réponses y/n). La correspondance est donc
# établie à partir de la variable et de son niveau, jamais par rapprochement
# approximatif de chaînes ni par recalcul de statistiques.
#
# proba = 1 fournit toutes les p-values natives pour le diagnostic ;
# proba = 0.05 fournit la description native au seuil pour le rapport.
description_complete <- FactoMineR::dimdesc(
  resultat, axes = axes_description, proba = 1
)
description <- FactoMineR::dimdesc(
  resultat, axes = axes_description, proba = 0.05
)
noms_modalites <- rownames(coordonnees)
niveaux_modalites <- unlist(
  lapply(variables_actives, levels), use.names = FALSE
)
if (length(niveaux_modalites) != length(noms_modalites)) {
  stop(
    "Le nombre de niveaux des variables actives ne correspond pas ",
    "au nombre de coordonnées des modalités FactoMineR."
  )
}
identifiants_dimdesc <- paste0(
  variables_modalites, "=", niveaux_modalites
)
if (anyDuplicated(identifiants_dimdesc)) {
  stop(
    "Identifiants de modalités non uniques : impossible de lire ",
    "les p-values natives de FactoMineR de façon univoque."
  )
}

# Conserver également les valeurs-tests natives, sans en déduire de
# nouvelles p-values. Elles sont utiles pour le contrôle méthodologique.
matrice_vtest <- as.matrix(resultat$var$v.test)
if (is.null(rownames(matrice_vtest)) ||
    anyDuplicated(rownames(matrice_vtest)) ||
    !setequal(rownames(matrice_vtest), noms_modalites)) {
  stop("Les valeurs-tests natives et les coordonnées ACM ne concordent pas.")
}
valeurs_vtest <- matrice_vtest[
  match(noms_modalites, rownames(matrice_vtest)),
  axes_description, drop = FALSE
]
v_axe_1 <- as.numeric(valeurs_vtest[, 1L])
v_axe_2 <- if (deux_axes) {
  as.numeric(valeurs_vtest[, 2L])
} else {
  rep(NA_real_, length(noms_modalites))
}

# Affecter les résultats natifs à chaque modalité par sa clé unique.
p_axe_1 <- rep(NA_real_, length(noms_modalites))
p_axe_2 <- rep(NA_real_, length(noms_modalites))
liste_p <- list(p_axe_1, p_axe_2)
for (i in seq_along(axes_description)) {
  caracteristiques <- description_complete[[i]]$category
  if (is.null(caracteristiques) || nrow(as.matrix(caracteristiques)) == 0L) {
    next
  }
  caracteristiques <- as.matrix(caracteristiques)
  if (!("p.value" %in% colnames(caracteristiques))) {
    stop("FactoMineR::dimdesc ne fournit pas de colonne p.value.")
  }
  cles <- rownames(caracteristiques)
  if (is.null(cles) || anyDuplicated(cles)) {
    stop("FactoMineR::dimdesc renvoie des catégories sans clé unique.")
  }
  indices <- match(cles, identifiants_dimdesc)
  if (anyNA(indices)) {
    stop(
      "Impossible de relier certaines catégories de dimdesc() aux modalités ",
      "de l'ACM : ",
      paste(cles[is.na(indices)], collapse = " ; ")
    )
  }
  liste_p[[i]][indices] <- as.numeric(
    caracteristiques[, "p.value"]
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
nombre_p_valides <- sum(is.finite(p_minimale))
if (nombre_p_valides == 0L) {
  stop(
    "FactoMineR::dimdesc n'a fourni aucune p-value exploitable. ",
    "Vérifier les catégories et le rapport méthodologique."
  )
}
tableau_significativite <- data.frame(
  variable = variables_modalites,
  modalite = noms_modalites,
  identifiant_dimdesc = identifiants_dimdesc,
  v_test_axe_1 = v_axe_1,
  p_value_axe_1 = p_axe_1,
  v_test_axe_2 = v_axe_2,
  p_value_axe_2 = p_axe_2,
  p_value_min = p_minimale,
  significative_005 = est_significative,
  methode = "FactoMineR::dimdesc, p.value native",
  stringsAsFactors = FALSE
)
utils::write.csv2(
  tableau_significativite,
  file.path(dossier_sortie, "significativite_modalites_factominer.csv"),
  row.names = FALSE, fileEncoding = "UTF-8", na = ""
)

p_minimale_globale <- min(p_minimale[is.finite(p_minimale)])
diagnostic_filtre <- data.frame(
  indicateur = c(
    "Méthode", "Observations analysées", "Modalités sur le plan",
    "Modalités avec p-value valide", "Modalités à p <= 0,05",
    "p-value minimale", "Axes utilisés"
  ),
  valeur = c(
    "FactoMineR::dimdesc, p.value native, axes 1 et 2",
    as.character(effectif_final),
    as.character(length(noms_modalites)),
    as.character(nombre_p_valides),
    as.character(sum(est_significative)),
    format(p_minimale_globale, digits = 9),
    paste(axes_description, collapse = " ; ")
  ),
  stringsAsFactors = FALSE
)
utils::write.csv2(
  diagnostic_filtre,
  file.path(dossier_sortie, "20_diagnostic_filtre_pvalue.csv"),
  row.names = FALSE, fileEncoding = "UTF-8"
)

# Éviter les avertissements mbcsToSbcs du moteur graphique en locale C.
# La translittération concerne seulement les légendes ; le corpus, les
# coordonnées et les exports conservent les intitulés UTF-8 d'origine.
libelles_graphiques <- function(texte) {
  valeurs <- iconv(
    enc2utf8(as.character(texte)),
    from = "UTF-8",
    to = "ASCII//TRANSLIT",
    sub = "?"
  )
  valeurs[is.na(valeurs)] <- "?"
  valeurs
}
titre_graphique <- sprintf(
  "ACM - %s (%d variables actives)",
  if (methode_calcul == "Burt") "Burt" else "TDC",
  ncol(donnees_actives)
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
  x_sup <- if (!is.null(coordonnees_quali_sup)) {
    coordonnees_quali_sup[, 1L]
  } else {
    numeric(0)
  }
  y_sup <- if (!is.null(coordonnees_quali_sup)) {
    if (deux_axes) coordonnees_quali_sup[, 2L] else {
      rep(0, nrow(coordonnees_quali_sup))
    }
  } else {
    numeric(0)
  }
  if (!any(visibles) && !length(x_sup)) {
    xlim <- c(-1, 1)
    ylim <- c(-1, 1)
  } else {
    xlim <- limites_axes(c(0, x[visibles], x_sup))
    ylim <- limites_axes(c(0, y[visibles], y_sup), 0.3)
  }
  inerties <- resultat$eig[, 2L]
  etiquette_x <- sprintf("Axe 1 (%.1f %% d'inertie)", inerties[[1L]])
  etiquette_y <- if (deux_axes) {
    sprintf("Axe 2 (%.1f %% d'inertie)", inerties[[2L]])
  } else {
    "Aucun axe 2"
  }
  # Préserver une zone exclusivement réservée à la légende des variables :
  # celle-ci ne recouvre ni les points ni les étiquettes des modalités.
  graphics::layout(
    matrix(c(1L, 2L), nrow = 1L), widths = c(3.8, 1.9)
  )
  par(mar = c(6.5, 5, 4, 1))
  plot(
    NA_real_, NA_real_, type = "n", xlim = xlim, ylim = ylim,
    xlab = etiquette_x, ylab = etiquette_y,
    main = titre_graphique
  )
  abline(h = 0, v = 0, col = "grey75", lty = 2)
  if (any(visibles)) {
    points(
      x[visibles], y[visibles], pch = 16,
      col = couleurs_modalites[visibles], cex = 1.1
    )
    text(
      x[visibles], y[visibles],
      libelles_graphiques(noms_modalites[visibles]),
      pos = 3, cex = 0.72,
      col = couleurs_modalites[visibles], xpd = TRUE
    )
  }
  # Les modalités supplémentaires restent visibles dans les deux plans :
  # le seuil de p-value est réservé aux seules modalités actives.
  if (length(x_sup)) {
    points(
      x_sup, y_sup, pch = 17, cex = 1.25,
      col = "#7A1FA2"
    )
    text(
      x_sup, y_sup,
      libelles_graphiques(rownames(coordonnees_quali_sup)),
      pos = 1, cex = 0.7, col = "#7A1FA2", xpd = TRUE
    )
  }
  if (filtrer_modalites && deux_axes) {
    mtext(
      sprintf(
        "Modalites axes 1/2 : p <= 0,05 (%d/%d), FactoMineR::dimdesc.",
        sum(visibles), length(visibles)
      ), side = 1, line = 4.3, cex = 0.7
    )
    if (!any(visibles)) {
      text(0, 0, "Aucune modalite significative (p <= 0,05)",
           pos = 3, cex = 0.85, col = "grey35")
    }
  } else if (!deux_axes) {
    mtext("Un seul axe factoriel : aucun filtre applique.",
          side = 1, line = 4.3, cex = 0.7)
  } else {
    mtext("Plan complet : toutes les modalites actives sont affichees.",
          side = 1, line = 4.3, cex = 0.7)
  }

  # Conserver dans les deux plans la même association variable/couleur.
  par(mar = c(6.5, 0.5, 4, 0.5))
  plot.new()
  taille_legende <- if (length(noms_variables_actives) > 20L) {
    0.54
  } else if (length(noms_variables_actives) > 12L) {
    0.66
  } else {
    0.82
  }
  legend(
    "topleft",
    legend = libelles_graphiques(noms_variables_actives),
    col = unname(couleurs_variables),
    pch = 16, bty = "n", cex = taille_legende,
    title = "Variables actives"
  )
  if (length(indices_quali_sup)) {
    legend(
      "bottomleft",
      legend = libelles_graphiques(
        paste("Supplementaire :", colnames(donnees)[indices_quali_sup])
      ),
      col = rep("#7A1FA2", length(indices_quali_sup)),
      pch = 17, bty = "n", cex = taille_legende,
      title = "Variables illustratives"
    )
  }
}
dessiner_quanti_sup <- function() {
  # Corrélations calculées par FactoMineR : projection séparée des
  # modalités actives car les deux familles n'ont pas la même échelle.
  if (is.null(coordonnees_quanti_sup)) return(invisible(NULL))
  graphics::layout(1L)
  par(mar = c(5, 5, 4, 2))
  plot(
    NA_real_, NA_real_, type = "n",
    xlim = c(-1.15, 1.15), ylim = c(-1.15, 1.15),
    asp = 1,
    xlab = "Axe 1 (correlation)",
    ylab = "Axe 2 (correlation)",
    main = "Variables quantitatives supplementaires"
  )
  symbols(
    0, 0, circles = 1, add = TRUE, inches = FALSE,
    fg = "grey60"
  )
  abline(h = 0, v = 0, col = "grey75", lty = 2)
  xs <- coordonnees_quanti_sup[, 1L]
  ys <- if (deux_axes) {
    coordonnees_quanti_sup[, 2L]
  } else {
    rep(0, nrow(coordonnees_quanti_sup))
  }
  valides <- is.finite(xs) & is.finite(ys)
  if (any(valides)) {
    arrows(
      0, 0, xs[valides], ys[valides],
      col = "#087E8B", length = 0.09, lwd = 1.5
    )
    text(
      xs[valides], ys[valides],
      libelles_graphiques(rownames(coordonnees_quanti_sup)[valides]),
      pos = 3, col = "#087E8B", cex = 0.85
    )
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
    width = 1900, height = 1100, res = 160
  )
  tryCatch(action(), finally = grDevices::dev.off())
}
dessiner_png("13_plan_factoriel.png", function() dessiner_plan(FALSE))
grDevices::pdf(
  file.path(dossier_sortie, "14_plan_factoriel.pdf"), width = 14, height = 8.5
)
tryCatch(dessiner_plan(FALSE), finally = grDevices::dev.off())
dessiner_png(
  "13_plan_factoriel_significatif.png", function() dessiner_plan(TRUE)
)
grDevices::pdf(
  file.path(dossier_sortie, "14_plan_factoriel_significatif.pdf"),
  width = 14, height = 8.5
)
tryCatch(dessiner_plan(TRUE), finally = grDevices::dev.off())
dessiner_png("15_inerties.png", dessiner_inerties)
if (length(indices_quanti_sup)) {
  dessiner_png(
    "26_plan_quantitatives_supplementaires.png", dessiner_quanti_sup
  )
  grDevices::pdf(
    file.path(dossier_sortie, "27_plan_quantitatives_supplementaires.pdf"),
    width = 10, height = 8.5
  )
  tryCatch(dessiner_quanti_sup(), finally = grDevices::dev.off())
}

statistiques <- data.frame(
  indicateur = c(
    "Source", "Méthode", "Variables actives", "Observations initiales",
    "Observations analysées", "Nombre de variables",
    "Modalités actives", "Axes factoriels",
    "Inertie totale (FactoMineR)",
    "Modalités significatives (p <= 0,05)",
    "Modalités au total", "p-value minimale",
    "Méthode de significativité des modalités"
  ),
  valeur = c(
    nom_source, paste0("ACM — ", libelle_methode, " (FactoMineR::MCA)"),
    paste(colnames(donnees_actives), collapse = " ; "),
    as.character(effectif_initial), as.character(effectif_final),
    as.character(ncol(donnees_actives)), as.character(nrow(coordonnees)),
    as.character(ncol(coordonnees)),
    format(sum(resultat$eig[, 1L]), digits = 9),
    as.character(sum(est_significative)), as.character(nrow(coordonnees)),
    format(p_minimale_globale, digits = 9),
    "FactoMineR::dimdesc, p-values natives, axes 1 et 2"
  ),
  stringsAsFactors = FALSE
)
utils::write.csv2(
  statistiques,
  file.path(dossier_sortie, "16_resultats_statistiques.csv"),
  row.names = FALSE, fileEncoding = "UTF-8"
)

# Arrondir uniquement les colonnes numériques pour le rapport texte.
# La colonne "axe" contient les libellés "dim 1", "dim 2", etc. :
# round() appliqué au data.frame entier déclenche Math.data.frame.
comparaison_formatee <- comparaison_inerties
colonnes_numeriques <- vapply(comparaison_formatee, is.numeric, logical(1))
comparaison_formatee[colonnes_numeriques] <- lapply(
  comparaison_formatee[colonnes_numeriques],
  function(colonne) round(colonne, digits = 4L)
)

rapport <- c(
  "ANALYSE DES CORRESPONDANCES MULTIPLES — FactoMineR",
  paste("Source :", nom_source),
  paste("Méthode de calcul :", libelle_methode),
  paste("Appel natif : FactoMineR::MCA(method =", methode_calcul, ")"),
  paste("Variables actives :", paste(colnames(donnees_actives), collapse = " ; ")),
  paste(
    "Variables qualitatives supplémentaires :",
    if (length(indices_quali_sup)) paste(
      colnames(donnees)[indices_quali_sup], collapse = " ; "
    ) else "Aucune"
  ),
  paste(
    "Variables quantitatives supplémentaires :",
    if (length(indices_quanti_sup)) paste(
      colnames(donnees)[indices_quanti_sup], collapse = " ; "
    ) else "Aucune"
  ),
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
  capture.output(print(comparaison_formatee, row.names = FALSE)),
  "",
  "REPRÉSENTATIONS EXPORTÉES",
  if (export_tdc) "Tableau disjonctif complet : tdc.csv." else
    "TDC non exporté : plus de 2 000 000 cellules.",
  if (export_burt) "Tableau de Burt : burt.csv." else
    "Burt non exporté : plus de 1 000 000 cellules.",
  "",
  "FILTRE DES MODALITES - p-values natives de FactoMineR::dimdesc",
  "dimdesc(proba=1) : p-values de toutes les modalités.",
  paste("Modalités avec p-value valide :", nombre_p_valides),
  paste("Modalités à p <= 0,05 :", sum(est_significative)),
  paste("p-value minimale :", signif(p_minimale_globale, 7)),
  "Fichiers : significativite_modalites_factominer.csv et 20_diagnostic_filtre_pvalue.csv.",
  "",
  "DESCRIPTION DES AXES PAR FactoMineR::dimdesc (p <= 0,05)",
  capture.output(print(description)),
  "",
  "AVERTISSEMENTS MÉTHODOLOGIQUES",
  "L'ACM repose exclusivement sur les variables qualitatives actives.",
  "Les inerties TDC et Burt ne se comparent pas comme deux estimations d'une même proportion.",
  "Le filtre concerne les modalités avec p native <= 0,05 sur l'axe 1 ou 2.",
  "Les p-values proviennent directement de FactoMineR::dimdesc.",
  "Ces p-values exploratoires ne sont pas corrigées pour comparaisons multiples.",
  "Les deux versions du plan utilisent les mêmes coordonnées FactoMineR.",
  "Toutes les modalités d'une variable partagent une couleur sur les deux plans.",
  "Correspondance variable / couleur : 19_couleurs_variables.csv.",
  "Les variables supplementaires utilisent les parametres quali.sup et quanti.sup natifs.",
  "Les modalites qualitatives supplementaires figurent en triangles violets sur les plans.",
  "Les variables quantitatives supplementaires sont projetees sur un plan de correlations distinct.",
  "Elles n'interviennent pas dans la construction des axes ni dans les inerties."
)
writeLines(
  rapport, file.path(dossier_sortie, "00_rapport_acm.txt"), useBytes = TRUE
)
cat(
  "ACM FactoMineR terminée. ", effectif_final,
  " observations analysées.\n", sep = ""
)
