# Rôle du fichier: centraliser l'affichage des résultats IRaMuTeQ-lite avec des sous-onglets dédiés.

ui_resultats_chd_iramuteq <- function() {
  tabsetPanel(
    id = "tabs_resultats_chd_iramuteq",
    tabPanel(
      "Dendrogramme",
      tags$h3("Dendrogramme CHD"),
      tags$p("Ouvrez la boîte de dialogue pour configurer les paramètres de l'analyse CHD."),
      tags$div(
        style = "display:flex; gap:8px; flex-wrap:wrap; margin-bottom:12px; align-items:center;",
        actionButton("ouvrir_param_chd", "Paramètres de l'analyse CHD", class = "btn-primary")
      ),
      uiOutput("ui_chd_statut"),
      tags$div(
        style = "width: 800px; max-width: 100%; margin: 0 auto 12px auto;",
        selectInput(
          inputId = "chd_dendro_style",
          label = "Style d'affichage",
          choices = c(
            "iramuteq_bars" = "iramuteq_bars",
            "factoextra" = "factoextra"
          ),
          selected = "iramuteq_bars"
        )
      ),
      tags$div(
        style = "width: 800px; max-width: 100%; margin: 0 auto;",
        plotOutput("plot_chd_iramuteq_dendro", height = "420px", width = "800px")
      )
    ),
    tabPanel(
      "Stats CHD",
      tags$h3("Tableaux statistiques CHD par classe"),
      uiOutput("ui_tables_stats_chd_iramuteq")
    ),
    tabPanel(
      "Concordancier",
      tags$h3("Concordancier"),
      uiOutput("ui_concordancier_iramuteq"),
      tags$hr(),
      tags$h4("Concordancier AFC (mots et segments)", style = "margin-top: 18px;"),
      uiOutput("ui_table_afc_mots_par_classe")
    ),
    tabPanel(
      "Nuage de mots",
      tags$h3("Nuages de mots par classe"),
      uiOutput("ui_wordcloud_iramuteq")
    )
  )
}
