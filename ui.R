library(bslib)
library(shiny)
library(htmltools)

ui <- page_sidebar(
  title = div(
    class = "app-title-block",
    tags$div(class = "app-kicker", "CHD Rainette"),
    tags$h1("CHD Rainette"),
    tags$p(
      class = "app-subtitle",
      tags$a(
        href = "https://www.codeandcortex.fr",
        target = "_blank",
        rel = "noopener noreferrer",
        "www.codeandcortex.fr"
      ),
      HTML(" &middot; version VPS Shiny")
    )
  ),
  theme = bs_theme(
    version = 5,
    primary = "#d96b2b",
    secondary = "#f0e2d0",
    success = "#2f855a",
    info = "#2b6cb0",
    warning = "#b7791f",
    danger = "#c53030",
    bg = "#f6f1ea",
    fg = "#2f241c",
    base_font = font_google("Source Sans 3"),
    heading_font = font_google("Merriweather Sans")
  ),
  fillable = TRUE,
  tags$head(
    tags$style(HTML("
      body {
        background: #f6f1ea;
      }
      .app-title-block h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.1;
      }
      .app-kicker {
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.76rem;
        font-weight: 700;
        color: #b4571f;
        margin-bottom: 0.25rem;
      }
      .app-subtitle {
        margin: 0.45rem 0 0;
        color: #6f5d4c;
      }
      .bslib-sidebar-layout > .sidebar {
        background: linear-gradient(180deg, #fbf6ef 0%, #f3e7d8 100%);
        border-right: 1px solid rgba(217, 107, 43, 0.12);
      }
      .sidebar-group + .sidebar-group {
        margin-top: 1rem;
      }
      .shiny-input-container {
        margin-bottom: 0.85rem;
      }
      .btn-primary {
        font-weight: 700;
      }
      .logs-box pre,
      .logs-box code {
        white-space: pre-wrap;
      }
      .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
      }
      .metric-card {
        background: #fffdf9;
        border: 1px solid rgba(47, 36, 28, 0.08);
        border-radius: 18px;
        padding: 1rem 1.1rem;
        box-shadow: 0 12px 30px rgba(47, 36, 28, 0.04);
      }
      .metric-card .label {
        font-size: 0.85rem;
        color: #7a6858;
        display: block;
        margin-bottom: 0.35rem;
      }
      .metric-card .value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #2f241c;
      }
      .preview-box {
        min-height: 22rem;
        max-height: 42rem;
        overflow: auto;
        background: #fffdf9;
        border: 1px solid rgba(47, 36, 28, 0.08);
        border-radius: 18px;
        padding: 1rem;
        white-space: pre-wrap;
      }
      .help-pane {
        max-width: 1000px;
      }
      .rainette-explorer-modal .modal-dialog {
        width: 96vw;
        max-width: 96vw;
      }
      .rainette-explorer-modal .modal-body {
        max-height: calc(100vh - 180px);
        overflow-y: auto;
      }
      @media (max-width: 980px) {
        .metrics-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }
      @media (max-width: 640px) {
        .metrics-grid {
          grid-template-columns: 1fr;
        }
      }
    "))
  ),
  sidebar = sidebar(
    width = 420,
    open = "desktop",
    div(
      class = "sidebar-group",
      fileInput("fichier_corpus", "Importer un corpus IRaMuTeQ (.txt)", accept = c(".txt")),
      p(
        class = "text-muted small",
        "Les lignes commençant par ",
        tags$code("****"),
        " sont reconnues comme dans IRaMuTeQ."
      )
    ),
    accordion(
      id = "sidebar_accordion",
      open = c("param_chd", "param_langue", "param_nettoyage"),
      accordion_panel(
        title = "Paramètres CHD",
        value = "param_chd",
        selectInput(
          "mode_decoupage",
          "Mode de découpage",
          choices = c("segment_size" = "segment_size", "ponctuation" = "ponctuation"),
          selected = "segment_size"
        ),
        numericInput("segment_size", "segment_size", value = 40, min = 5, step = 1),
        numericInput("k", "k (nombre de classes)", value = 3, min = 2, step = 1),
        numericInput("min_segment_size", "Nombre minimal de termes par segment", value = 10, min = 1, step = 1),
        numericInput("min_split_members", "Effectif minimal pour scinder une classe", value = 10, min = 1, step = 1),
        numericInput("min_docfreq", "Fréquence minimale des termes", value = 3, min = 1, step = 1),
        numericInput("max_p", "max_p (p-value)", value = 0.05, min = 0, max = 1, step = 0.01)
      ),
      accordion_panel(
        title = "Langue du corpus et stopwords",
        value = "param_langue",
        radioButtons(
          "langue_corpus",
          "Langue du corpus",
          choices = c("Français" = "fr", "Anglais" = "en", "Espagnol" = "es"),
          selected = "fr"
        ),
        p(class = "text-muted small", "Ce choix pilote l'estimation de langue et la liste de stopwords quanteda."),
        uiOutput("ui_langue_detection")
      ),
      accordion_panel(
        title = "Classification",
        value = "param_classification",
        radioButtons(
          "type_classification",
          "Type de classification",
          choices = c(
            "Classification simple (rainette)" = "simple",
            "Classification double (rainette2)" = "double"
          ),
          selected = "simple"
        ),
        conditionalPanel(
          condition = "input.type_classification == 'double'",
          numericInput("min_segment_size2", "min_segment_size (classification 2)", value = 15, min = 1, step = 1),
          numericInput("max_k_double", "max_k (rainette2)", value = 8, min = 2, step = 1)
        )
      ),
      accordion_panel(
        title = "Nettoyage",
        value = "param_nettoyage",
        checkboxInput("nettoyage_caracteres", "Nettoyage caractères (regex)", value = FALSE),
        checkboxInput("supprimer_ponctuation", "Supprimer la ponctuation", value = FALSE),
        checkboxInput("supprimer_chiffres", "Supprimer les chiffres", value = FALSE),
        checkboxInput("supprimer_apostrophes", "Traiter les élisions françaises", value = FALSE),
        checkboxInput("forcer_minuscules_avant", "Forcer les minuscules avant traitement", value = FALSE),
        checkboxInput("retirer_stopwords", "Retirer les stopwords (quanteda)", value = FALSE),
        p(class = "text-muted small", "Les stopwords sont désormais gérés directement avec quanteda.")
      ),
      accordion_panel(
        title = "AFC",
        value = "param_afc",
        checkboxInput("afc_reduire_chevauchement", "Réduire les chevauchements des mots", value = FALSE),
        radioButtons(
          "afc_taille_mots",
          "Taille des mots (AFC termes)",
          choices = c("Fréquence" = "frequency", "Chi2" = "chi2"),
          selected = "frequency"
        ),
        numericInput("afc_top_termes", "Nombre max de termes affichés", value = 120, min = 20, step = 10),
        numericInput("afc_top_modalites", "Nombre max de modalités affichées", value = 120, min = 20, step = 10)
      ),
      accordion_panel(
        title = "Cooccurrences",
        value = "param_cooc",
        numericInput("top_n", "top_n (wordcloud)", value = 20, min = 5, step = 1),
        numericInput("window_cooc", "window (cooccurrences)", value = 5, min = 1, step = 1),
        numericInput("top_feat", "top_feat (cooccurrences)", value = 20, min = 5, step = 1)
      )
    ),
    div(
      class = "sidebar-group d-grid gap-2",
      actionButton("lancer", "Lancer l'analyse", class = "btn-primary"),
      actionButton("explor", "Exploration Rainette", class = "btn-outline-secondary"),
      downloadButton("dl_zip", "Télécharger exports (zip)"),
      downloadButton("dl_afc_zip", "Télécharger AFC (zip)"),
      downloadButton("dl_segments", "Télécharger segments"),
      downloadButton("dl_stats", "Télécharger stats"),
      downloadButton("dl_html", "Télécharger concordancier HTML")
    )
  ),
  navset_card_tab(
    id = "onglets_principaux",
    full_screen = TRUE,
    nav_panel(
      "Analyse",
      layout_columns(
        col_widths = c(5, 7),
        card(
          card_header("Statut"),
          p(textOutput("statut")),
          uiOutput("barre_progression"),
          uiOutput("ui_chd_statut")
        ),
        card(
          card_header("Analyses lancées"),
          div(class = "metrics-grid",
            div(class = "metric-card", span(class = "label", "Documents"), span(class = "value", textOutput("metric_docs", inline = TRUE))),
            div(class = "metric-card", span(class = "label", "Segments"), span(class = "value", textOutput("metric_segments", inline = TRUE))),
            div(class = "metric-card", span(class = "label", "Segments analysés"), span(class = "value", textOutput("metric_analyzed", inline = TRUE))),
            div(class = "metric-card", span(class = "label", "Classes"), span(class = "value", textOutput("metric_classes", inline = TRUE)))
          )
        )
      ),
      card(
        class = "logs-box",
        card_header("Journal"),
        verbatimTextOutput("logs", placeholder = TRUE)
      ),
      card(
        card_header("Répartition des classes"),
        tableOutput("table_classes")
      )
    ),
    nav_panel(
      "CHD",
      card(
        full_screen = TRUE,
        card_header("Rainette Explor"),
        rainette_explorer_module_ui("explorer_tab")
      ),
      card(
        card_header("Résumé des classes"),
        tableOutput("table_classes_chd")
      ),
      card(
        card_header("Fichiers générés"),
        uiOutput("ui_exports_status")
      )
    ),
    nav_panel(
      "AFC",
      card(card_header("Statut AFC"), uiOutput("ui_afc_statut"), uiOutput("ui_afc_erreurs")),
      layout_columns(
        col_widths = c(6, 6),
        card(card_header("AFC des classes"), plotOutput("plot_afc_classes", height = "520px")),
        card(card_header("AFC des termes"), plotOutput("plot_afc", height = "520px"))
      ),
      card(card_header("Table des mots projetés"), uiOutput("ui_table_afc_mots_par_classe")),
      card(card_header("AFC des variables étoilées"), plotOutput("plot_afc_vars", height = "560px")),
      card(card_header("Table des modalités projetées"), tableOutput("table_afc_vars")),
      card(card_header("Valeurs propres"), tableOutput("table_afc_eig"))
    ),
    nav_panel(
      "Corpus",
      card(card_header("Informations"), uiOutput("corpus_meta")),
      card(
        card_header("Aperçu du corpus importé"),
        div(class = "preview-box", verbatimTextOutput("corpus_preview", placeholder = TRUE))
      )
    ),
    nav_panel(
      "Exports",
      card(
        card_header("Exports disponibles"),
        uiOutput("ui_exports_links")
      )
    ),
    nav_panel(
      "Aide",
      div(
        class = "help-pane",
        navset_pill(
          nav_panel("Aide générale", uiOutput("help_main")),
          nav_panel(
            "README Rainette",
            tags$p(
              tags$a(
                href = "https://github.com/juba/rainette/blob/main/README.md",
                target = "_blank",
                rel = "noopener noreferrer",
                "Ouvrir le README Rainette dans un nouvel onglet"
              )
            )
          )
        )
      )
    )
  )
)
