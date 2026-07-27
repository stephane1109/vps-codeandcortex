library(shiny)
library(htmltools)

build_main_ui <- function() {
  section <- function(title, ..., class = NULL) {
    div(
      class = paste(c("plain-section", class), collapse = " "),
      if (!is.null(title) && nzchar(title)) tags$h2(class = "section-title", title),
      ...
    )
  }

  control_section <- function(title, ...) {
    div(
      class = "control-section",
      tags$h3(class = "control-title", title),
      div(class = "control-section-body", ...)
    )
  }

  metric_item <- function(label, output_id) {
    div(
      class = "metric-item",
      span(class = "metric-label", label),
      span(class = "metric-value", textOutput(output_id, inline = TRUE))
    )
  }

  fluidPage(
    tags$head(
      tags$style(HTML("
        html, body {
          min-height: 100%;
        }
        body {
          margin: 0;
          color: #24211f;
          background: #f7f6f2;
          font-family: 'Avenir Next', 'Helvetica Neue', sans-serif;
          font-size: 21px;
          line-height: 1.5;
        }
        a {
          color: #9a4d16;
          text-decoration: none;
        }
        a:hover {
          color: #24211f;
          text-decoration: underline;
        }
        .container-fluid {
          width: 100%;
          max-width: none;
          padding: 0 1.4rem 2rem;
        }
        .app-header {
          margin: 0 0 1.1rem;
          padding: 1rem 0 0.8rem;
          border-bottom: 1px solid #d8d1c5;
        }
        .app-header h1 {
          margin: 0;
          font-size: 3rem !important;
          line-height: 1.1;
          font-weight: 650;
          letter-spacing: -0.02em;
        }
        .app-subtitle {
          margin: 0.25rem 0 0;
          color: #6b625b;
          font-size: 1.3rem !important;
        }
        .layout-row {
          margin-left: -0.7rem;
          margin-right: -0.7rem;
        }
        .control-column,
        .main-column {
          padding-left: 0.7rem;
          padding-right: 0.7rem;
        }
        .control-column {
          border-right: 1px solid #d8d1c5;
        }
        .control-section,
        .sidebar-group,
        .ticket-access-group {
          margin: 0 0 1.15rem;
          padding: 0;
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
        }
        .control-title,
        .ticket-access-title {
          margin: 0;
          padding: 0 0 0.25rem;
          border-bottom: 1px solid #d8d1c5;
          color: #24211f;
          font-size: 1.3rem !important;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }
        .control-section-body {
          padding-top: 0.95rem;
        }
        .help-block,
        .text-muted,
        .small {
          color: #6b625b !important;
          font-size: 1.2rem !important;
        }
        .shiny-input-container {
          width: 100%;
          margin-bottom: 0.78rem;
        }
        .shiny-input-container label,
        .control-label {
          margin-bottom: 0.2rem;
          color: #3b3632;
          font-size: 1.32rem !important;
          font-weight: 600;
        }
        .form-control,
        .form-select,
        .selectize-input {
          min-height: 2rem;
          border: 1px solid #cfc8bd !important;
          border-radius: 0 !important;
          background: #fffefa !important;
          box-shadow: none !important;
          color: #24211f;
          font-size: 1.32rem !important;
        }
        .selectize-input input,
        .selectize-dropdown,
        .selectize-dropdown-content,
        .selectize-dropdown .option {
          font-size: 1.32rem !important;
        }
        .form-control:focus,
        .form-select:focus,
        .selectize-input.focus {
          border-color: #24211f !important;
          box-shadow: none !important;
        }
        .checkbox,
        .radio {
          margin-top: 0.2rem;
          margin-bottom: 0.35rem;
          font-size: 1.32rem !important;
        }
        .checkbox label,
        .radio label {
          min-height: 0;
          font-size: 1.32rem !important;
          font-weight: 400;
        }
        input[type='checkbox'],
        input[type='radio'] {
          margin-top: 0.2rem;
          accent-color: #24211f;
        }
        .btn,
        .btn-default,
        .btn-primary {
          min-height: 2rem;
          padding: 0.35rem 0.55rem;
          border: 1px solid #24211f !important;
          border-radius: 0 !important;
          background: #fffefa !important;
          box-shadow: none !important;
          color: #24211f !important;
          font-size: 1.28rem !important;
          font-weight: 600;
          line-height: 1.2;
        }
        .btn-primary,
        .btn:hover,
        .btn-default:hover,
        .btn-primary:hover {
          background: #24211f !important;
          color: #fffefa !important;
        }
        .shiny-input-container .input-group {
          display: flex !important;
          align-items: stretch !important;
          width: 100%;
        }
        .shiny-input-container label.input-group-btn,
        .shiny-input-container .input-group-btn {
          display: flex !important;
          align-items: stretch !important;
          margin: 0 !important;
          padding: 0 !important;
          width: auto !important;
        }
        .shiny-input-container .input-group .form-control {
          height: auto !important;
          min-height: 2.75rem !important;
        }
        .shiny-input-container .btn-file {
          display: inline-flex !important;
          align-items: center !important;
          min-height: 2.75rem !important;
          margin: 0 !important;
          white-space: nowrap;
        }
        .action-row {
          display: grid;
          gap: 0.45rem;
          margin-top: 0.85rem;
        }
        .action-row .btn {
          width: 100%;
        }
        .nav-tabs {
          margin: 0;
          padding: 0;
          border-bottom: 1px solid #24211f;
        }
        .nav-tabs > li > a {
          margin-right: 0;
          padding: 0.9rem 1.2rem !important;
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          color: #6b625b !important;
          font-size: 1.55rem !important;
          font-weight: 700 !important;
        }
        .nav-tabs > li.active > a,
        .nav-tabs > li.active > a:hover,
        .nav-tabs > li.active > a:focus {
          border: 0 !important;
          background: #24211f !important;
          color: #fffefa !important;
        }
        .tab-content {
          padding-top: 1rem;
          overflow: visible !important;
        }
        .plain-section {
          margin: 0 0 1.8rem;
          padding: 0;
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
          overflow: visible !important;
        }
        .section-title {
          margin: 0 0 0.7rem;
          padding: 0 0 0.35rem;
          border-bottom: 1px solid #d8d1c5;
          color: #24211f;
          font-size: 1.45rem !important;
          font-weight: 700;
          letter-spacing: 0.06em;
          text-transform: uppercase;
        }
        .help-pane,
        .help-pane p,
        .help-pane li {
          color: #24211f;
          font-size: 1.32rem !important;
          line-height: 1.45 !important;
        }
        .help-pane h1,
        .help-pane h2,
        .help-pane h3 {
          margin: 0.95rem 0 0.45rem;
          color: #24211f;
          font-size: 1.45rem !important;
          font-weight: 700;
          line-height: 1.25 !important;
        }
        .help-pane h1:first-child,
        .help-pane h2:first-child,
        .help-pane h3:first-child {
          margin-top: 0;
        }
        .help-pane ul,
        .help-pane ol {
          margin: 0.35rem 0 0.9rem 1.35rem;
          padding-left: 0;
        }
        .help-pane a,
        .help-pane strong,
        .help-pane code {
          font-size: inherit !important;
        }
        .wide-stack {
          display: grid;
          gap: 0.85rem;
        }
        .metrics-grid {
          display: grid;
          grid-template-columns: repeat(4, minmax(0, 1fr));
          gap: 1rem;
        }
        .metric-item {
          padding: 0;
          border: 0;
          background: transparent;
        }
        .metric-label {
          display: block;
          margin-bottom: 0.15rem;
          color: #6b625b;
          font-size: 1.16rem !important;
          text-transform: uppercase;
          letter-spacing: 0.05em;
        }
        .metric-value {
          color: #24211f;
          font-size: 1.95rem !important;
          font-weight: 650;
        }
        .progress-wrapper {
          display: grid;
          gap: 0.35rem;
        }
        .progress-label {
          color: #6b625b;
          font-size: 1.16rem !important;
        }
        .progress-shell {
          width: 100%;
          height: 8px;
          border-radius: 0 !important;
          background: #ded8ce;
          overflow: visible !important;
        }
        .progress-bar-custom {
          height: 100%;
          border-radius: 0 !important;
          background: #24211f;
          box-shadow: none !important;
        }
        .debug-terminal,
        .preview-box,
        .code-box {
          min-height: auto !important;
          max-height: none !important;
          padding: 0;
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
          color: #24211f;
          overflow: visible !important;
          white-space: pre-wrap;
        }
        .debug-terminal pre,
        .preview-box pre,
        .code-box pre {
          margin: 0;
          padding: 0;
          border: 0;
          background: transparent;
          color: #24211f;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .preview-box {
          min-height: 12rem !important;
          max-height: 22rem !important;
          padding: 0.75rem !important;
          border: 1px solid #d8d1c5 !important;
          background: #fffefa !important;
          overflow: auto !important;
        }
        .afc-plot-host,
        .afc-plot-canvas {
          width: 100%;
          min-width: 0;
          max-width: none;
          margin: 0;
          padding: 0;
          border: 0 !important;
          background: transparent !important;
          overflow: visible !important;
        }
        .afc-plot-canvas {
          height: calc(100vh - 11rem);
          min-height: 760px;
        }
        .afc-plot-canvas .shiny-plot-output {
          width: 100% !important;
          height: 100% !important;
        }
        .afc-plot-canvas .shiny-image-output,
        .afc-plot-canvas img {
          width: 100% !important;
          height: 100% !important;
        }
        .afc-plot-canvas img {
          object-fit: contain;
          display: block;
        }
        .full-page-iframe,
        iframe {
          width: 100% !important;
          min-height: calc(100vh - 11rem) !important;
          height: calc(100vh - 11rem) !important;
          border: 0 !important;
          border-radius: 0 !important;
          background: #ffffff;
          box-shadow: none !important;
        }
        .full-page-image,
        .wordcloud-full-page img {
          width: 100% !important;
          max-height: calc(100vh - 11rem);
          object-fit: contain;
          border: 0 !important;
          border-radius: 0 !important;
          box-shadow: none !important;
        }
        .input-help-box,
        .ticket-status-card,
        .ticket-status-message,
        .alert {
          padding: 0;
          border: 0 !important;
          border-radius: 0 !important;
          background: transparent !important;
          box-shadow: none !important;
        }
        .input-help-label,
        .input-help-value {
          font-size: 1.2rem !important;
          line-height: 1.35;
        }
        .input-help-label {
          font-weight: 700;
        }
        .language-detection-note {
          margin: 0.15rem 0 0 !important;
          color: #6b625b !important;
          font-size: 1.02rem !important;
          font-weight: 400 !important;
          line-height: 1.35 !important;
          letter-spacing: 0 !important;
        }
        .language-detection-note.is-warning {
          color: #8a5a13 !important;
        }
        .language-detection-note.is-ok {
          color: #2f6f4e !important;
        }
        .rainette-explor-placeholder {
          margin: 0.15rem 0 0 !important;
          color: #6b625b !important;
          font-size: 1.02rem !important;
          font-weight: 400 !important;
          line-height: 1.35 !important;
        }
        .archive-placeholder {
          margin: 0.15rem 0 0 !important;
          color: #6b625b !important;
          font-size: 1.02rem !important;
          font-weight: 400 !important;
          line-height: 1.35 !important;
        }
        .archive-download-action {
          margin-top: 0.85rem;
        }
        .ticket-status-shell {
          display: grid;
          gap: 0.4rem;
        }
        .ticket-status-card {
          display: flex;
          align-items: flex-start;
          gap: 0.45rem;
        }
        .ticket-status-dot {
          width: 0.55rem;
          height: 0.55rem;
          flex: 0 0 0.55rem;
          margin-top: 0.35rem;
          border-radius: 0 !important;
          background: #6b625b;
          box-shadow: none !important;
        }
        .ticket-status-dot.is-active {
          background: #2f855a;
        }
        .ticket-status-dot.is-waiting {
          background: #b7791f;
        }
        .ticket-status-dot.is-error {
          background: #c53030;
        }
        .ticket-status-meta,
        .ticket-status-note,
        .ticket-status-message {
          color: #4a433e;
          font-size: 1.16rem !important;
        }
        .ticket-actions {
          display: grid;
          gap: 0.45rem;
        }
        table {
          width: 100%;
          font-size: 1.18rem !important;
        }
        .result-note {
          margin: 0.2rem 0 0.75rem;
          color: #5c544e;
          font-size: 1.18rem !important;
        }
        .table > thead > tr > th,
        .table > tbody > tr > td,
        table > thead > tr > th,
        table > tbody > tr > td {
          padding: 0.35rem 0.45rem;
          border-top: 1px solid #ded8ce;
        }
        @media (max-width: 992px) {
          .control-column {
            margin-bottom: 1.2rem;
            border-right: 0;
            border-bottom: 1px solid #d8d1c5;
            padding-bottom: 1rem;
          }
          .metrics-grid {
            grid-template-columns: repeat(2, minmax(0, 1fr));
          }
        }
        @media (max-width: 640px) {
          .container-fluid {
            padding: 0 0.85rem 1.4rem;
          }
          .metrics-grid {
            grid-template-columns: 1fr;
          }
          .afc-plot-canvas {
            height: 620px;
            min-height: 620px;
          }
        }
      "))
    ),
    uiOutput("ui_ticket_release_hook"),
    tags$header(
      class = "app-header",
      tags$h1("CHD Rainette"),
      tags$p(
        class = "app-subtitle",
        tags$a(
          href = "https://www.codeandcortex.fr",
          target = "_blank",
          rel = "noopener noreferrer",
          "www.codeandcortex.fr"
        ),
        HTML(" · version 0_4beta - modifiée 27-07-2026")
      )
    ),
    fluidRow(
      class = "layout-row",
      column(
        width = 3,
        class = "control-column",
        uiOutput("ui_ticket_sidebar"),
        control_section(
          "Corpus",
          fileInput("fichier_corpus", "Importer un corpus IRaMuTeQ (.txt)", accept = c(".txt")),
          p(
            class = "text-muted small",
            "Le corpus doit être dans le format IRaMuTeQ."
          )
        ),
        control_section(
          "Paramètres CHD",
          selectInput(
            "mode_decoupage",
            "Mode de découpage",
            choices = c("segment_size" = "segment_size", "ponctuation" = "ponctuation"),
            selected = "segment_size"
          ),
          numericInput("segment_size", "segment_size", value = 40, min = 5, step = 1),
          numericInput("k", "k (nombre de classes)", value = 6, min = 2, step = 1),
          numericInput("min_segment_size", "Nombre minimal de termes par segment", value = 0, min = 0, step = 1),
          numericInput("min_split_members", "Effectif minimal pour scinder une classe", value = 12, min = 3, step = 1),
          numericInput("min_docfreq", "Fréquence minimale des termes", value = 1, min = 1, step = 1),
          numericInput("max_p", "max_p (p-value)", value = 0.05, min = 0, max = 1, step = 0.01)
        ),
        control_section(
          "Langue du corpus",
          radioButtons(
            "langue_corpus",
            NULL,
            choices = c("Français" = "fr", "Anglais" = "en", "Espagnol" = "es"),
            selected = "fr"
          ),
          uiOutput("ui_langue_detection")
        ),
        control_section(
          "Nettoyage",
          radioButtons(
            "mode_nettoyage_lexical",
            NULL,
            choices = c(
              "Stopwords quanteda" = "stopwords_quanteda",
              "Dictionnaire IRaMuTeQ-lite (lexique_fr)" = "lexique_iramuteq",
              "Aucun nettoyage lexical" = "aucun"
            ),
            selected = "stopwords_quanteda"
          ),
          uiOutput("ui_stopwords_info"),
          checkboxInput("lexique_utiliser_lemmes", "Lemmatisation lexique_fr (forme vers c_lemme)", value = TRUE),
          selectizeInput(
            "pos_lexique_a_conserver",
            "Catégories c_morpho à conserver",
            choices = categories_morpho_iramuteq(),
            selected = c("NOM", "VER", "ADJ"),
            multiple = TRUE
          ),
          checkboxInput("morpho_conserver_hors_lexique", "Conserver les formes hors lexique (AUTRE_FORME)", value = TRUE),
          checkboxInput("morpho_exclure_etre_verbe", "Exclure le terme être/etre si VER est sélectionné", value = FALSE),
          checkboxInput("nettoyage_caracteres", "Nettoyage caractères (regex)", value = FALSE),
          checkboxInput("supprimer_ponctuation", "Supprimer la ponctuation", value = TRUE),
          checkboxInput("supprimer_chiffres", "Supprimer les chiffres", value = TRUE),
          checkboxInput("supprimer_apostrophes", "Traiter les élisions françaises", value = FALSE),
          checkboxInput("forcer_minuscules_avant", "Forcer les minuscules avant traitement", value = FALSE)
        ),
        control_section(
          "AFC",
          checkboxInput("afc_avoid_overlap", "Éviter les chevauchements AFC", value = TRUE)
        ),
        control_section(
          "Nuages de mots",
          numericInput("top_n", "top_n (wordcloud)", value = 20, min = 5, step = 1)
        ),
        control_section(
          "Debug",
          checkboxInput("debug_mode", "Activer le mode debug détaillé", value = TRUE),
          p(
            class = "text-muted small",
            "Quand il est activé, toutes les grandes étapes du pipeline sont journalisées dans l’onglet Analyse."
          )
        ),
        div(
          class = "action-row",
          actionButton("lancer", "Lancer l'analyse", class = "btn-primary")
        )
      ),
      column(
        width = 9,
        class = "main-column",
        tabsetPanel(
          id = "onglets_principaux",
          type = "tabs",
          tabPanel(
            "Analyse",
            section(
              "Statut et indicateurs",
              div(
                class = "wide-stack",
                p(textOutput("statut")),
                uiOutput("barre_progression"),
                div(
                  class = "metrics-grid",
                  metric_item("Documents", "metric_docs"),
                  metric_item("Segments", "metric_segments"),
                  metric_item("Segments analysés", "metric_analyzed"),
                  metric_item("Classes", "metric_classes")
                )
              )
            ),
            section(
              "Mode debug et étapes de l’analyse",
              div(class = "debug-terminal", verbatimTextOutput("logs", placeholder = TRUE))
            )
          ),
          tabPanel(
            "Corpus",
            section("Informations", uiOutput("corpus_meta")),
            section(
              "Aperçu du corpus importé",
              div(class = "preview-box", verbatimTextOutput("corpus_preview", placeholder = TRUE))
            ),
            section("Concordancier HTML", uiOutput("ui_concordancier"))
          ),
          tabPanel(
            "CHD",
            section("Rainette explor", uiOutput("ui_rainette_explor_frame"), class = "graph-full-page-section")
          ),
          tabPanel(
            "AFC",
            section(
              "Analyse factorielle des correspondances",
              uiOutput("ui_afc_status"),
              fluidRow(
                column(
                  width = 6,
                  numericInput("afc_top_terms", "Nombre de termes affichés", value = 80, min = 10, max = 200, step = 10)
                ),
                column(
                  width = 6,
                  selectInput("afc_size_by", "Taille des termes", choices = c("Chi2" = "Chi2", "Fréquence" = "Frequence"), selected = "Chi2")
                )
              )
            ),
            section(
              "Projection des classes",
              div(
                class = "afc-plot-host",
                div(
                  class = "afc-plot-canvas",
                  imageOutput("plot_afc_classes", width = "100%", height = "100%")
                )
              ),
              class = "graph-full-page-section"
            ),
            section(
              "Projection des classes et des termes",
              div(
                class = "afc-plot-host",
                div(
                  class = "afc-plot-canvas",
                  imageOutput("plot_afc_terms", width = "100%", height = "100%")
                )
              ),
              class = "graph-full-page-section"
            ),
            section("Valeurs propres et inertie", tableOutput("table_afc_eigenvalues"))
          ),
          tabPanel(
            "Résultats",
            section("Affichage des résultats", uiOutput("ui_resultats_perf_note")),
            section("Résumé des classes", tableOutput("table_classes")),
            section(
              "Statistiques par classe",
              selectInput("classe_resultat", "Classe", choices = NULL),
              uiOutput("ui_table_stats_note"),
              tableOutput("table_stats_classe")
            ),
            section("Nuages de mots", uiOutput("ui_wordclouds"), class = "graph-full-page-section")
          ),
          tabPanel(
            "Exports",
            section("Archive globale", uiOutput("ui_exports_links"))
          ),
          tabPanel(
            "Aide",
            section(NULL, uiOutput("help_main"), class = "help-pane")
          )
        )
      )
    )
  )
}
