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
      HTML(" &middot; interface Shiny Rainette pour le VPS")
    )
  ),
  theme = bs_theme(
    version = 5,
    primary = "#d96b2b",
    secondary = "#f4e5d5",
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
        background:
          radial-gradient(circle at top left, rgba(239, 156, 69, 0.14), transparent 28%),
          radial-gradient(circle at top right, rgba(217, 107, 43, 0.08), transparent 32%),
          linear-gradient(180deg, #f8f4ed 0%, #f4ede4 100%);
      }
      .app-title-block h1 { margin: 0; font-size: 2.05rem; line-height: 1.04; }
      .app-kicker {
        text-transform: uppercase;
        letter-spacing: 0.12em;
        font-size: 0.76rem;
        font-weight: 700;
        color: #b4571f;
        margin-bottom: 0.25rem;
      }
      .app-subtitle { margin: 0.45rem 0 0; color: #6f5d4c; }
      .app-subtitle a {
        color: #a64f1b;
        font-weight: 700;
        text-decoration: none;
      }
      .app-subtitle a:hover { text-decoration: underline; }
      .bslib-sidebar-layout > .sidebar {
        background: linear-gradient(180deg, rgba(255,255,255,0.88) 0%, rgba(248, 239, 226, 0.96) 100%);
        border-right: 1px solid rgba(217, 107, 43, 0.10);
        box-shadow: inset -1px 0 0 rgba(255,255,255,0.65);
      }
      .sidebar-group {
        background: rgba(255, 253, 249, 0.82);
        border: 1px solid rgba(47, 36, 28, 0.08);
        border-radius: 20px;
        padding: 1rem 1rem 0.65rem;
        box-shadow: 0 14px 30px rgba(47, 36, 28, 0.05);
      }
      .sidebar-group + .sidebar-group { margin-top: 1rem; }
      .shiny-input-container { margin-bottom: 0.85rem; }
      .btn-primary {
        font-weight: 700;
        border: none;
        background: linear-gradient(135deg, #d96b2b 0%, #ef9c45 100%);
        box-shadow: 0 12px 25px rgba(217, 107, 43, 0.22);
      }
      .btn-primary:hover { filter: brightness(1.03); }
      .accordion-item, .accordion-button {
        border-radius: 16px !important;
      }
      .accordion-button {
        font-weight: 700;
        color: #3f2c1f;
      }
      .accordion-body {
        background: rgba(255,255,255,0.78);
      }
      .logs-box pre, .logs-box code { white-space: pre-wrap; }
      .bslib-navs-card, .card {
        border: 1px solid rgba(47, 36, 28, 0.08);
        border-radius: 22px;
        box-shadow: 0 18px 40px rgba(47, 36, 28, 0.06);
        background: rgba(255, 253, 249, 0.96);
      }
      .card-header {
        font-weight: 800;
        color: #39281d;
        background: linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(248,240,229,0.96) 100%);
        border-bottom: 1px solid rgba(47, 36, 28, 0.06);
      }
      .nav-tabs {
        border-bottom: none;
        gap: 0.45rem;
        padding: 0.45rem 0.45rem 0;
      }
      .nav-tabs .nav-link {
        border: none;
        border-radius: 999px;
        background: rgba(244, 229, 213, 0.55);
        color: #5c4535;
        font-weight: 700;
      }
      .nav-tabs .nav-link.active {
        background: linear-gradient(135deg, #d96b2b 0%, #ef9c45 100%);
        color: #fff9f3;
        box-shadow: 0 10px 20px rgba(217, 107, 43, 0.22);
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
      .hero-card {
        background:
          linear-gradient(135deg, rgba(217, 107, 43, 0.96) 0%, rgba(239, 156, 69, 0.94) 100%);
        color: #fff8f2;
        border: none;
      }
      .hero-card h2 {
        margin: 0 0 0.45rem;
        font-size: 1.55rem;
      }
      .hero-card p {
        margin: 0;
        color: rgba(255, 248, 242, 0.88);
        max-width: 70ch;
      }
      .debug-strip {
        display: flex;
        flex-wrap: wrap;
        gap: 0.6rem;
      }
      .debug-pill {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: rgba(255,255,255,0.8);
        border: 1px solid rgba(47, 36, 28, 0.08);
        color: #4a3425;
        border-radius: 999px;
        padding: 0.4rem 0.8rem;
        font-size: 0.88rem;
        font-weight: 700;
      }
      .debug-terminal {
        min-height: 22rem;
        max-height: 42rem;
        overflow: auto;
        background: #1e1d1a;
        color: #f1eee6;
        border-radius: 18px;
        padding: 1rem 1.05rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      }
      .debug-terminal pre {
        white-space: pre-wrap;
        margin: 0;
        color: #f1eee6;
      }
      .preview-box, .code-box {
        min-height: 22rem;
        max-height: 42rem;
        overflow: auto;
        background: #fffdf9;
        border: 1px solid rgba(47, 36, 28, 0.08);
        border-radius: 18px;
        padding: 1rem;
        white-space: pre-wrap;
      }
      .input-help-box {
        margin-top: 0.45rem;
        display: grid;
        gap: 0.15rem;
        background: rgba(255,250,243,0.95);
        border: 1px dashed rgba(217, 107, 43, 0.34);
        border-radius: 14px;
        padding: 0.65rem 0.8rem;
      }
      .input-help-label {
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #a25725;
      }
      .input-help-value {
        font-size: 0.9rem;
        color: #5b4638;
      }
      .help-pane { max-width: 1000px; }
      .progress-wrapper { display: grid; gap: 0.5rem; }
      .progress-label { font-size: 0.95rem; color: #6f5d4c; }
      .progress-shell {
        width: 100%;
        height: 14px;
        border-radius: 999px;
        background: rgba(47, 36, 28, 0.08);
        overflow: hidden;
      }
      .progress-bar-custom {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #d96b2b 0%, #ef9c45 100%);
      }
      .wide-stack {
        display: grid;
        gap: 1rem;
      }
      .control-note {
        display: flex;
        align-items: end;
        min-height: 100%;
      }
      @media (max-width: 980px) {
        .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 640px) {
        .metrics-grid { grid-template-columns: 1fr; }
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
        " sont reconnues comme dans le format IRaMuTeQ."
      )
    ),
    accordion(
      id = "sidebar_accordion",
      open = c("param_chd", "param_langue", "param_nettoyage", "param_debug"),
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
        numericInput("k", "k (nombre de classes)", value = 6, min = 2, step = 1),
        numericInput("min_segment_size", "Nombre minimal de termes par segment", value = 0, min = 0, step = 1),
        numericInput("min_split_members", "Effectif minimal pour scinder une classe", value = 12, min = 3, step = 1),
        numericInput("min_docfreq", "Fréquence minimale des termes", value = 1, min = 1, step = 1),
        numericInput("max_p", "max_p (p-value)", value = 0.05, min = 0, max = 1, step = 0.01)
      ),
      accordion_panel(
        title = "Langue et stopwords",
        value = "param_langue",
        radioButtons(
          "langue_corpus",
          "Langue du corpus",
          choices = c("Français" = "fr", "Anglais" = "en", "Espagnol" = "es"),
          selected = "fr"
        ),
        checkboxInput("retirer_stopwords", "Activer les stopwords quanteda", value = TRUE),
        uiOutput("ui_stopwords_info"),
        uiOutput("ui_langue_detection")
      ),
      accordion_panel(
        title = "Nettoyage",
        value = "param_nettoyage",
        checkboxInput("nettoyage_caracteres", "Nettoyage caractères (regex)", value = FALSE),
        checkboxInput("supprimer_ponctuation", "Supprimer la ponctuation", value = TRUE),
        checkboxInput("supprimer_chiffres", "Supprimer les chiffres", value = TRUE),
        checkboxInput("supprimer_apostrophes", "Traiter les élisions françaises", value = FALSE),
        checkboxInput("forcer_minuscules_avant", "Forcer les minuscules avant traitement", value = FALSE)
      ),
      accordion_panel(
        title = "Nuages de mots",
        value = "param_wordcloud",
        numericInput("top_n", "top_n (wordcloud)", value = 20, min = 5, step = 1)
      ),
      accordion_panel(
        title = "Debug",
        value = "param_debug",
        checkboxInput("debug_mode", "Activer le mode debug détaillé", value = TRUE),
        p(
          class = "text-muted small",
          "Quand il est activé, toutes les grandes étapes du pipeline sont journalisées de façon détaillée sur l’onglet Analyse."
        )
      )
    ),
    div(
      class = "sidebar-group d-grid gap-2",
      actionButton("lancer", "Lancer l'analyse", class = "btn-primary"),
      downloadButton("dl_zip", "Télécharger exports (zip)"),
      downloadButton("dl_segments", "Télécharger segments"),
      downloadButton("dl_stats", "Télécharger stats"),
      downloadButton("dl_html", "Télécharger concordancier HTML"),
      downloadButton("dl_bundle", "Télécharger bundle rainette_explor")
    )
  ),
  navset_card_tab(
    id = "onglets_principaux",
    full_screen = TRUE,
    nav_panel(
      "Analyse",
      card(
        class = "hero-card",
        full_screen = TRUE,
        card_body(
          tags$h2("Suivre, diagnostiquer et explorer la CHD Rainette"),
          tags$p("L’onglet Analyse centralise maintenant les indicateurs, l’état d’exécution et le journal détaillé du pipeline pour faciliter le debug sur le VPS.")
        )
      ),
      card(
        full_screen = TRUE,
        card_header("Statut et indicateurs"),
        div(class = "wide-stack",
          uiOutput("ui_debug_status"),
          p(textOutput("statut")),
          uiOutput("barre_progression"),
          div(
            class = "metrics-grid",
            div(class = "metric-card", span(class = "label", "Documents"), span(class = "value", textOutput("metric_docs", inline = TRUE))),
            div(class = "metric-card", span(class = "label", "Segments"), span(class = "value", textOutput("metric_segments", inline = TRUE))),
            div(class = "metric-card", span(class = "label", "Segments analysés"), span(class = "value", textOutput("metric_analyzed", inline = TRUE))),
            div(class = "metric-card", span(class = "label", "Classes"), span(class = "value", textOutput("metric_classes", inline = TRUE)))
          )
        )
      ),
      card(
        class = "logs-box",
        full_screen = TRUE,
        card_header("Mode debug et étapes de l’analyse"),
        div(class = "debug-terminal", verbatimTextOutput("logs", placeholder = TRUE))
      )
    ),
    nav_panel(
      "CHD",
      card(
        full_screen = TRUE,
        card_header("Rainette explor"),
        rainette_explor_module_ui("rainette_explor")
      )
    ),
    nav_panel(
      "Résultats",
      card(
        full_screen = TRUE,
        card_header("Résumé des classes"),
        tableOutput("table_classes")
      ),
      card(
        full_screen = TRUE,
        card_header("Statistiques par classe"),
        selectInput("classe_resultat", "Classe", choices = NULL),
        tableOutput("table_stats_classe")
      ),
      card(
        full_screen = TRUE,
        card_header("Nuages de mots"),
        uiOutput("ui_wordclouds")
      )
    ),
    nav_panel(
      "Corpus",
      card(
        card_header("Informations"),
        uiOutput("corpus_meta")
      ),
      card(
        card_header("Aperçu du corpus importé"),
        div(class = "preview-box", verbatimTextOutput("corpus_preview", placeholder = TRUE))
      ),
      card(
        full_screen = TRUE,
        card_header("Concordancier HTML"),
        uiOutput("ui_concordancier")
      )
    ),
    nav_panel(
      "Exports",
      card(
        card_header("Fichiers générés"),
        uiOutput("ui_exports_links")
      ),
      card(
        card_header("Code R pour rainette_explor"),
        div(class = "code-box", verbatimTextOutput("bundle_code", placeholder = TRUE))
      )
    ),
    nav_panel(
      "Aide",
      div(class = "help-pane", uiOutput("help_main"))
    )
  )
)
