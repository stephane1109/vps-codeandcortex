library(bslib)
library(shiny)
library(htmltools)

build_main_ui <- function() {
page_sidebar(
  title = div(
    class = "app-title-block",
    tags$div(class = "app-monogram", "R"),
    tags$div(
      class = "app-title-copy",
      tags$div(class = "app-kicker", "Laboratoire textuel"),
      tags$h1("CHD Rainette"),
      tags$p(
        class = "app-subtitle",
        tags$a(
          href = "https://www.codeandcortex.fr",
          target = "_blank",
          rel = "noopener noreferrer",
          "www.codeandcortex.fr"
        ),
        HTML(" &middot; version 0_3beta")
      )
    )
  ),
  theme = bs_theme(
    version = 5,
    primary = "#ef6c21",
    secondary = "#f4dfcf",
    success = "#2f855a",
    info = "#2b6cb0",
    warning = "#b7791f",
    danger = "#c53030",
    bg = "#f6f1ea",
    fg = "#24211f",
    base_font = font_google("Source Sans 3"),
    heading_font = font_google("Space Grotesk")
  ),
  fillable = TRUE,
  tags$head(
    tags$style(HTML("
      body {
        background:
          linear-gradient(180deg, rgba(255,255,255,0.70) 0%, rgba(255,255,255,0.70) 100%),
          repeating-linear-gradient(
            0deg,
            rgba(20, 24, 28, 0.028) 0,
            rgba(20, 24, 28, 0.028) 1px,
            transparent 1px,
            transparent 40px
          ),
          linear-gradient(180deg, #f4f2ee 0%, #ece8e2 100%);
      }
      .app-title-block h1 {
        margin: 0;
        font-size: 2rem;
        line-height: 1.08;
        letter-spacing: -0.02em;
      }
      .app-kicker {
        text-transform: uppercase;
        letter-spacing: 0.16em;
        font-size: 0.72rem;
        font-weight: 700;
        color: #8d5d2b;
        margin-bottom: 0.4rem;
      }
      .app-subtitle {
        margin: 0.55rem 0 0;
        color: #5f6670;
        max-width: 70ch;
      }
      .app-subtitle a {
        color: #9e5b22;
        font-weight: 700;
        text-decoration: none;
      }
      .app-subtitle a:hover { text-decoration: underline; }
      .bslib-sidebar-layout > .sidebar {
        background: rgba(247, 245, 241, 0.97);
        border-right: 1px solid rgba(31, 35, 40, 0.08);
        box-shadow: inset -1px 0 0 rgba(255,255,255,0.8);
      }
      .sidebar-group {
        background: rgba(255, 255, 255, 0.9);
        border: 1px solid rgba(31, 35, 40, 0.08);
        border-radius: 12px;
        padding: 1rem 1rem 0.65rem;
        box-shadow: 0 6px 18px rgba(24, 28, 33, 0.05);
      }
      .sidebar-group + .sidebar-group { margin-top: 1rem; }
      .shiny-input-container { margin-bottom: 0.85rem; }
      .btn-primary {
        font-weight: 700;
        border: none;
        background: #d96b2b;
        box-shadow: 0 6px 14px rgba(217, 107, 43, 0.14);
      }
      .btn-primary:hover { background: #c85d1b; }
      .btn-secondary, .btn-default {
        border: 1px solid rgba(31, 35, 40, 0.10);
        background: #ffffff;
        color: #1f2328;
      }
      .accordion-item, .accordion-button {
        border-radius: 10px !important;
      }
      .accordion-button {
        font-weight: 700;
        color: #1f2328;
        background: #fbfaf8;
      }
      .accordion-body {
        background: #ffffff;
      }
      .logs-box pre, .logs-box code { white-space: pre-wrap; }
      .bslib-navs-card, .card {
        border: 1px solid rgba(31, 35, 40, 0.08);
        border-radius: 14px;
        box-shadow: 0 8px 24px rgba(24, 28, 33, 0.05);
        background: rgba(255, 255, 255, 0.95);
      }
      .card-header {
        font-weight: 800;
        color: #1f2328;
        background: #fbfaf8;
        border-bottom: 1px solid rgba(31, 35, 40, 0.06);
      }
      .nav-tabs {
        border-bottom: 1px solid rgba(31, 35, 40, 0.08);
        gap: 0.25rem;
        padding: 0.45rem 0.45rem 0;
      }
      .nav-tabs .nav-link,
      .nav-tabs > li > a {
        border: 1px solid transparent;
        border-radius: 10px 10px 0 0;
        background: transparent;
        color: #5f6670;
        font-weight: 700;
      }
      .nav-tabs .nav-link.active {
        background: #ffffff;
        color: #1f2328;
        border-color: rgba(31, 35, 40, 0.08) rgba(31, 35, 40, 0.08) #ffffff;
        box-shadow: inset 0 3px 0 #d96b2b;
      }
      .metrics-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 1rem;
      }
      .metric-card {
        background: #fbfaf8;
        border: 1px solid rgba(31, 35, 40, 0.08);
        border-radius: 12px;
        padding: 1rem 1.1rem;
        box-shadow: none;
      }
      .metric-card .label {
        font-size: 0.85rem;
        color: #66707a;
        display: block;
        margin-bottom: 0.35rem;
      }
      .metric-card .value {
        font-size: 1.45rem;
        font-weight: 700;
        color: #1f2328;
      }
      .analysis-intro {
        border-left: 4px solid #d96b2b;
        background: linear-gradient(180deg, rgba(255,255,255,0.96) 0%, rgba(249,247,243,0.96) 100%);
      }
      .analysis-intro h2 {
        margin: 0 0 0.55rem;
        font-size: 1.35rem;
        color: #1f2328;
      }
      .analysis-intro p {
        margin: 0;
        color: #4d5863;
        max-width: 74ch;
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
        background: #fbfaf8;
        border: 1px solid rgba(31, 35, 40, 0.08);
        color: #2d333b;
        border-radius: 999px;
        padding: 0.4rem 0.8rem;
        font-size: 0.88rem;
        font-weight: 700;
      }
      .debug-terminal {
        min-height: 22rem;
        max-height: 42rem;
        overflow: auto;
        background: #14181c;
        color: #eef2f6;
        border-radius: 12px;
        padding: 1rem 1.05rem;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.03);
      }
      .debug-terminal pre {
        white-space: pre-wrap;
        margin: 0;
        color: #eef2f6;
      }
      .preview-box, .code-box {
        min-height: 22rem;
        max-height: 42rem;
        overflow: auto;
        background: #ffffff;
        border: 1px solid rgba(31, 35, 40, 0.08);
        border-radius: 12px;
        padding: 1rem;
        white-space: pre-wrap;
      }
      .afc-plot-host {
        width: 100%;
        display: flex;
        justify-content: center;
        overflow: visible;
        padding: 0.4rem 0 1rem;
      }
      .afc-plot-canvas {
        flex: 0 1 1000px;
        width: min(100%, 1000px);
        min-width: 0;
        max-width: 1000px;
        height: auto;
        aspect-ratio: 1 / 1;
        margin: 0 auto;
      }
      .afc-plot-canvas .shiny-plot-output {
        width: 100% !important;
        height: 100% !important;
      }
      .input-help-box {
        margin-top: 0.45rem;
        display: grid;
        gap: 0.15rem;
        background: #fbfaf8;
        border: 1px dashed rgba(217, 107, 43, 0.4);
        border-radius: 10px;
        padding: 0.65rem 0.8rem;
      }
      .input-help-label {
        font-size: 0.75rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #9e5b22;
      }
      .input-help-value {
        font-size: 0.9rem;
        color: #4d5863;
      }
      .help-pane { max-width: 1000px; }
      .progress-wrapper { display: grid; gap: 0.5rem; }
      .progress-label { font-size: 0.95rem; color: #4d5863; }
      .progress-shell {
        width: 100%;
        height: 14px;
        border-radius: 999px;
        background: rgba(31, 35, 40, 0.08);
        overflow: hidden;
      }
      .progress-bar-custom {
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #d96b2b 0%, #e68f40 100%);
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
      .lab-note {
        font-size: 0.9rem;
        color: #5f6670;
        margin: 0;
      }
      .rainette-host-shell {
        min-height: 78vh;
        height: 78vh;
      }
      @media (max-width: 980px) {
        .metrics-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      }
      @media (max-width: 640px) {
        .metrics-grid { grid-template-columns: 1fr; }
      }

      :root {
        --rainette-orange: #ef6c21;
        --rainette-orange-dark: #c94f0b;
        --rainette-orange-soft: #fff0e5;
        --rainette-ink: #24211f;
        --rainette-muted: #6f665f;
        --rainette-paper: #fffdf9;
        --rainette-line: rgba(87, 63, 47, 0.13);
      }
      body {
        color: var(--rainette-ink);
        background:
          radial-gradient(circle at 88% 8%, rgba(239, 108, 33, 0.12), transparent 28rem),
          radial-gradient(circle at 8% 92%, rgba(218, 155, 93, 0.10), transparent 32rem),
          linear-gradient(135deg, #f8f3ec 0%, #f1e9df 100%);
      }
      .navbar {
        background: rgba(255, 253, 249, 0.94) !important;
        border-bottom: 1px solid var(--rainette-line);
        box-shadow: 0 10px 30px rgba(76, 49, 31, 0.07);
        backdrop-filter: blur(16px);
      }
      .app-title-block {
        display: flex;
        align-items: center;
        gap: 0.95rem;
        padding: 0.2rem 0;
      }
      .app-monogram {
        display: grid;
        place-items: center;
        width: 3.1rem;
        height: 3.1rem;
        flex: 0 0 3.1rem;
        border-radius: 7px;
        color: #ffffff;
        background: var(--rainette-orange);
        box-shadow: 0 5px 12px rgba(76, 49, 31, 0.15);
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.55rem;
        font-weight: 800;
      }
      .app-title-copy { min-width: 0; }
      .app-title-block h1 {
        color: var(--rainette-ink);
        font-size: clamp(1.55rem, 2.2vw, 2.15rem);
        font-weight: 760;
        letter-spacing: -0.045em;
      }
      .app-kicker {
        margin-bottom: 0.22rem;
        color: var(--rainette-orange-dark);
        font-size: 0.68rem;
        letter-spacing: 0.19em;
      }
      .app-subtitle { margin-top: 0.28rem; }
      .app-subtitle a { color: var(--rainette-orange-dark); }
      .bslib-sidebar-layout > .sidebar {
        background: rgba(247, 240, 232, 0.96);
        border-right: 1px solid var(--rainette-line);
        box-shadow: 12px 0 34px rgba(76, 49, 31, 0.06);
      }
      .sidebar-group {
        border: 1px solid var(--rainette-line);
        border-radius: 18px;
        background: rgba(255, 253, 249, 0.94);
        box-shadow: 0 12px 28px rgba(76, 49, 31, 0.07);
      }
      .form-control, .form-select, .selectize-input {
        min-height: 2.75rem;
        border: 1px solid rgba(87, 63, 47, 0.18) !important;
        border-radius: 11px !important;
        background: #fffefa !important;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.8);
      }
      .form-control:focus, .form-select:focus, .selectize-input.focus {
        border-color: var(--rainette-orange) !important;
        box-shadow: 0 0 0 0.22rem rgba(239, 108, 33, 0.15) !important;
      }
      .form-check-input { accent-color: var(--rainette-orange); }
      .form-check-input:checked {
        background-color: var(--rainette-orange);
        border-color: var(--rainette-orange);
      }
      .accordion-item {
        margin-bottom: 0.55rem;
        overflow: hidden;
        border: 1px solid var(--rainette-line) !important;
        border-radius: 8px !important;
        background: var(--rainette-paper);
      }
      .accordion-button {
        padding: 0.9rem 1rem;
        color: var(--rainette-ink);
        background: #fffaf5;
        box-shadow: none !important;
      }
      .accordion-button:not(.collapsed) {
        color: var(--rainette-orange-dark);
        background: var(--rainette-orange-soft);
      }
      .accordion-button:not(.collapsed)::after { filter: sepia(1) saturate(5) hue-rotate(340deg); }
      .btn:not(.btn-close) {
        min-height: 2.65rem;
        border: 1px solid #cf5816 !important;
        border-radius: 6px !important;
        color: #ffffff !important;
        background: #e7651d !important;
        box-shadow: none !important;
        font-weight: 700 !important;
        transition: background-color 140ms ease, border-color 140ms ease;
      }
      .btn:not(.btn-close):hover {
        transform: none;
        filter: none;
        border-color: #ad4308 !important;
        background: #c95312 !important;
        box-shadow: none !important;
      }
      .btn:not(.btn-close):active { background: #ad4308 !important; }
      .sidebar-group.d-grid .btn { width: 100%; }
      .bslib-navs-card, .card {
        overflow: hidden;
        border: 1px solid var(--rainette-line);
        border-radius: 20px;
        background: rgba(255, 253, 249, 0.97);
        box-shadow: 0 16px 38px rgba(76, 49, 31, 0.08);
      }
      .tab-content > .tab-pane > .card {
        animation: rainette-card-in 360ms ease both;
      }
      .card-header {
        padding: 1rem 1.2rem;
        color: var(--rainette-ink);
        background: linear-gradient(90deg, var(--rainette-orange-soft), #fffaf5 38%, #fffdf9 100%);
        border-bottom: 1px solid var(--rainette-line);
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.02rem;
        letter-spacing: -0.01em;
      }
      .nav-tabs {
        gap: 0.5rem;
        padding: 0.7rem;
        border: 0;
        background: rgba(249, 241, 232, 0.88);
      }
      .nav-tabs .nav-link,
      .nav-tabs > li > a {
        border: 1px solid transparent;
        border-radius: 6px;
        color: #625951 !important;
        background: rgba(255,255,255,0.72) !important;
        padding: 0.65rem 1rem;
      }
      .nav-tabs .nav-link:hover,
      .nav-tabs > li > a:hover {
        color: var(--rainette-orange-dark) !important;
        border-color: rgba(239, 108, 33, 0.22) !important;
        background: #fff7f0 !important;
      }
      .nav-tabs .nav-link.active,
      .nav-tabs .nav-item.show .nav-link,
      .nav-tabs > li.active > a,
      .nav-tabs > li.active > a:hover,
      .nav-tabs > li.active > a:focus {
        color: #ffffff !important;
        border-color: var(--rainette-orange) !important;
        background: #e7651d !important;
        box-shadow: none !important;
      }
      .metric-card {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(239, 108, 33, 0.17);
        border-radius: 16px;
        background: linear-gradient(145deg, #fffdf9 0%, #fff5ed 100%);
        box-shadow: 0 10px 22px rgba(76, 49, 31, 0.06);
      }
      .metric-card::before {
        content: '';
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: linear-gradient(180deg, #ff9c5b, var(--rainette-orange));
      }
      .metric-card .value { color: var(--rainette-orange-dark); }
      .progress-shell { height: 16px; background: #eadfd5; }
      .progress-bar-custom {
        background: linear-gradient(90deg, #ff9b59 0%, var(--rainette-orange) 60%, #cc4b08 100%);
        box-shadow: 0 0 14px rgba(239, 108, 33, 0.30);
      }
      .debug-terminal {
        border: 1px solid rgba(239, 108, 33, 0.25);
        background: #211c19;
        box-shadow: inset 4px 0 0 var(--rainette-orange), 0 12px 24px rgba(36, 24, 17, 0.10);
      }
      @keyframes rainette-card-in {
        from { opacity: 0; transform: translateY(8px); }
        to { opacity: 1; transform: translateY(0); }
      }
      @media (prefers-reduced-motion: reduce) {
        .tab-content > .tab-pane > .card { animation: none; }
        .btn:not(.btn-close) { transition: none; }
      }
      @media (max-width: 640px) {
        .app-monogram { width: 2.65rem; height: 2.65rem; flex-basis: 2.65rem; }
        .nav-tabs { gap: 0.3rem; }
        .nav-tabs .nav-link { padding: 0.55rem 0.75rem; }
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
      open = c("param_chd", "param_langue", "param_nettoyage", "param_afc", "param_debug"),
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
        title = "Langue du corpus",
        value = "param_langue",
        radioButtons(
          "langue_corpus",
          "Langue du corpus",
          choices = c("Français" = "fr", "Anglais" = "en", "Espagnol" = "es"),
          selected = "fr"
        ),
        uiOutput("ui_langue_detection")
      ),
      accordion_panel(
        title = "Nettoyage",
        value = "param_nettoyage",
        checkboxInput("retirer_stopwords", "Stopwords quanteda", value = TRUE),
        uiOutput("ui_stopwords_info"),
        checkboxInput("nettoyage_caracteres", "Nettoyage caractères (regex)", value = FALSE),
        checkboxInput("supprimer_ponctuation", "Supprimer la ponctuation", value = TRUE),
        checkboxInput("supprimer_chiffres", "Supprimer les chiffres", value = TRUE),
        checkboxInput("supprimer_apostrophes", "Traiter les élisions françaises", value = FALSE),
        checkboxInput("forcer_minuscules_avant", "Forcer les minuscules avant traitement", value = FALSE)
      ),
      accordion_panel(
        title = "AFC",
        value = "param_afc",
        checkboxInput("afc_avoid_overlap", "Éviter les chevauchements des mots", value = TRUE)
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
      downloadButton("dl_zip", "Télécharger l'archive globale (zip)")
    )
  ),
  navset_card_tab(
    id = "onglets_principaux",
    full_screen = TRUE,
    nav_panel(
      "Analyse",
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
      "CHD",
      card(
        full_screen = TRUE,
        card_header("Rainette explor"),
        card_body(
          fill = TRUE,
          uiOutput("ui_rainette_explor_frame")
        )
      )
    ),
    nav_panel(
      "AFC",
      card(
        full_screen = TRUE,
        card_header("Analyse factorielle des correspondances"),
        uiOutput("ui_afc_status"),
        layout_columns(
          col_widths = c(6, 6),
          numericInput("afc_top_terms", "Nombre de termes affichés", value = 80, min = 10, max = 200, step = 10),
          selectInput("afc_size_by", "Taille des termes", choices = c("Chi2" = "Chi2", "Fréquence" = "Frequence"), selected = "Chi2")
        )
      ),
      card(
        full_screen = TRUE,
        card_header("Projection des classes"),
        card_body(
          div(
            class = "afc-plot-host",
            div(
              class = "afc-plot-canvas",
              plotOutput("plot_afc_classes", width = "100%", height = "100%")
            )
          )
        )
      ),
      card(
        full_screen = TRUE,
        card_header("Projection des classes et des termes"),
        card_body(
          div(
            class = "afc-plot-host",
            div(
              class = "afc-plot-canvas",
              plotOutput("plot_afc_terms", width = "100%", height = "100%")
            )
          )
        )
      ),
      card(
        full_screen = TRUE,
        card_header("Valeurs propres et inertie"),
        tableOutput("table_afc_eigenvalues")
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
      "Exports",
      card(
        full_screen = TRUE,
        card_header("Archive globale"),
        uiOutput("ui_exports_links")
      )
    ),
    nav_panel(
      "Aide",
      div(class = "help-pane", uiOutput("help_main"))
    )
  )
)
}
