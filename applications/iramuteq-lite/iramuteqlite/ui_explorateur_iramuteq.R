# Rôle du fichier: composant explorateur (Phase 2) pour naviguer corpus/analyses.

ui_explorateur_iramuteq <- function(id) {
  ns <- shiny::NS(id)

  bslib::card(
    full_screen = TRUE,
    bslib::card_header(tags$strong("Explorateur")),
    bslib::card_body(uiOutput(ns("tree")))
  )
}

server_explorateur_iramuteq <- function(id, rv, nom_corpus_reactif) {
  moduleServer(id, function(input, output, session) {
    output$tree <- renderUI({
      nom_corpus <- nom_corpus_reactif()
      if (is.null(nom_corpus) || !nzchar(nom_corpus)) nom_corpus <- "Aucun corpus"

      tags$ul(
        style = "padding-left: 18px;",
        tags$li(sprintf("corpus : %s", nom_corpus)),
        tags$li("chd"),
        tags$li("wordcloud"),
        tags$li("afc")
      )
    })

  })
}
