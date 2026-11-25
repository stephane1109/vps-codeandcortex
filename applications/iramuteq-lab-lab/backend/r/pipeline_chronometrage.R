# Mesures des durées du pipeline, sans modifier les calculs scientifiques.
# Les lignes agrégées recouvrent les sous-étapes : ne pas additionner ces valeurs.

creer_chronometre_pipeline <- function(chemin_csv, journal = NULL) {
  actives <- list()
  mesures <- data.frame(
    phase = character(), code = character(), etape = character(),
    debut_utc = character(), fin_utc = character(),
    duree_secondes = numeric(), cpu_utilisateur_secondes = numeric(),
    cpu_systeme_secondes = numeric(), statut = character()
  )
  signaler <- function(texte) {
    if (is.function(journal)) try(journal(texte), silent = TRUE)
    invisible(NULL)
  }
  sauvegarder <- function() {
    dir.create(dirname(chemin_csv), recursive = TRUE, showWarnings = FALSE)
    temporaire <- tempfile("durees-", tmpdir = dirname(chemin_csv), fileext = ".csv")
    on.exit(unlink(temporaire), add = TRUE)
    utils::write.csv(mesures, temporaire, row.names = FALSE, fileEncoding = "UTF-8")
    if (!file.rename(temporaire, chemin_csv) &&
        !file.copy(temporaire, chemin_csv, overwrite = TRUE)) {
      signaler("[Durée] Écriture du fichier de performances impossible.")
    }
    invisible(NULL)
  }
  demarrer <- function(code, etape, phase = "post_chd") {
    if (!is.null(actives[[code]])) stop(paste0("Chronomètre déjà démarré : ", code))
    actives[[code]] <<- list(
      etape = etape, phase = phase, debut = Sys.time(), cpu = proc.time()
    )
    signaler(paste0("[Durée] Début : ", etape))
    invisible(NULL)
  }
  terminer <- function(code, statut = "terminee") {
    depart <- actives[[code]]
    if (is.null(depart)) stop(paste0("Chronomètre non démarré : ", code))
    fin <- Sys.time()
    cpu <- proc.time()
    secondes <- max(0, as.numeric(difftime(fin, depart$debut, units = "secs")))
    utilisateur <- max(0, as.numeric(cpu[["user.self"]] - depart$cpu[["user.self"]]))
    systeme <- max(0, as.numeric(cpu[["sys.self"]] - depart$cpu[["sys.self"]]))
    horodatage <- function(x) format(x, "%Y-%m-%dT%H:%M:%OS3Z", tz = "UTC")
    actives[[code]] <<- NULL
    mesures <<- rbind(mesures, data.frame(
      phase = depart$phase, code = code, etape = depart$etape,
      debut_utc = horodatage(depart$debut), fin_utc = horodatage(fin),
      duree_secondes = round(secondes, 4),
      cpu_utilisateur_secondes = round(utilisateur, 4),
      cpu_systeme_secondes = round(systeme, 4), statut = statut
    ))
    tryCatch(sauvegarder(), error = function(e) {
      signaler(paste0("[Durée] Erreur CSV : ", conditionMessage(e)))
    })
    signaler(sprintf(
      "[Durée] Fin : %s | %.3f s écoulées | CPU utilisateur %.3f s | CPU système %.3f s | %s",
      depart$etape, secondes, utilisateur, systeme, statut
    ))
    invisible(secondes)
  }
  fermer <- function() {
    for (code in rev(names(actives))) {
      try(terminer(code, "interrompue"), silent = TRUE)
    }
    invisible(NULL)
  }
  sauvegarder()
  list(demarrer = demarrer, terminer = terminer, fermer = fermer, chemin = chemin_csv)
}
