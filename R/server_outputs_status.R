# Module server - sorties de statut global
# Ce fichier enregistre les sorties Shiny de statut transversal (logs, statut,
# barre de progression, table de classes) pour alléger `app.R` sans changer la logique.

register_outputs_status <- function(input, output, session, rv) {
    output$logs <- renderText(rv$logs)
    output$statut <- renderText(rv$statut)

    output$barre_progression <- renderUI({
      p <- max(0, min(100, rv$progression))
      tags$div(
        style = "width: 100%; border: 1px solid #999; height: 20px; position: relative;",
        tags$div(style = paste0("width: ", p, "%; height: 100%; background-color: #4C9AFF;")),
        tags$div(
          style = "position: absolute; top: 0; left: 0; width: 100%; height: 100%; text-align: center; line-height: 20px; font-size: 12px;",
          paste0(p, "%")
        )
      )
    })

    output$table_classes <- renderTable({
      req(rv$filtered_corpus)
      tb <- table(docvars(rv$filtered_corpus)$Classes, useNA = "ifany")
      data.frame(Classe = names(tb), Effectif = as.integer(tb), stringsAsFactors = FALSE)
    }, rownames = FALSE)
}
