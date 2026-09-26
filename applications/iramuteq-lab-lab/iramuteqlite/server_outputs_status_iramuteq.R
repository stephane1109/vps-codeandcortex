# Rôle du fichier: server_outputs_status_iramuteq.R centralise les sorties de statut global.
# Ce module évite un crash de session si l'enregistrement des sorties n'est pas disponible.

register_outputs_status <- function(input, output, session, rv) {
  output$statut <- renderText({
    statut <- rv$statut
    if (is.null(statut) || !length(statut) || all(is.na(statut)) || !any(nzchar(statut))) {
      return("En attente.")
    }
    paste(statut[!is.na(statut) & nzchar(statut)], collapse = "\n")
  })

  output$logs <- renderPrint({
    logs <- rv$logs
    if (is.null(logs) || !length(logs) || all(is.na(logs)) || !any(nzchar(logs))) {
      cat("Aucun événement pour le moment.")
      return(invisible(NULL))
    }
    cat(paste(logs[!is.na(logs) & nzchar(logs)], collapse = "\n"))
  })
}
