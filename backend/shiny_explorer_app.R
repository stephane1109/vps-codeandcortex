#!/usr/bin/env Rscript

suppressPackageStartupMessages({
  library(shiny)
  library(bslib)
  library(htmltools)
  library(quanteda)
  library(rainette)
})

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) return(right)
  left
}

explorer_theme <- function() {
  bs_theme(
    version = 5,
    primary = "#d96b2b",
    secondary = "#f4ede5",
    success = "#2d8a57",
    info = "#3f7cac",
    warning = "#d96b2b",
    bg = "#f7f3ee",
    fg = "#1f1b18",
    base_font = bslib::font_collection("Segoe UI", "Helvetica Neue", "Arial", "sans-serif"),
    heading_font = bslib::font_collection("Segoe UI", "Helvetica Neue", "Arial", "sans-serif")
  )
}

explorer_css <- function() {
  rainette_css <- getFromNamespace("rainette_explor_css", "rainette")()
  paste0(
    rainette_css,
    "
body {
  background: #f7f3ee;
}
.bslib-page-fill {
  min-height: 100vh;
}
.explorer-shell {
  min-height: 100vh;
}
.explorer-header {
  padding: 1rem 1.25rem 0.35rem 1.25rem;
}
.explorer-kicker {
  margin: 0 0 0.35rem 0;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.75rem;
  font-weight: 700;
  color: #d96b2b;
}
.explorer-title {
  margin: 0;
  font-size: 1.85rem;
  line-height: 1.05;
}
.explorer-copy {
  margin: 0.45rem 0 0 0;
  color: #5f5348;
  max-width: 60rem;
}
.explorer-layout {
  padding: 0 1.25rem 1.25rem 1.25rem;
}
.explorer-layout .sidebar {
  background: #f1e7dc;
  border: 1px solid rgba(217, 107, 43, 0.14);
}
.explorer-layout .sidebar .form-label,
.explorer-layout .sidebar label {
  color: #1f1b18;
  font-weight: 600;
}
.explorer-card {
  border: 1px solid rgba(31, 27, 24, 0.08);
  box-shadow: 0 12px 28px rgba(27, 21, 17, 0.06);
}
.explorer-code {
  white-space: pre-wrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  background: #1f1b18;
  color: #f6ede5;
  border-radius: 16px;
  padding: 1rem;
  min-height: 220px;
}
.explorer-note {
  margin: 0 0 1rem 0;
  color: #6f6255;
}
#side {
  background: transparent;
  padding: 0;
}
#docs {
  padding-left: 0;
}
#docs_sample {
  padding-right: 0;
}
"
  )
}

docs_sample_ui_proxy <- getFromNamespace("docs_sample_ui", "rainette")
docs_sample_server_proxy <- getFromNamespace("docs_sample_server", "rainette")

build_simple_code <- function(res_name, dtm_name, input) {
  paste0(
    "rainette_plot(\n",
    "  ", res_name, ", ", dtm_name, ",\n",
    "  k = ", input$k, ",\n",
    "  n_terms = ", input$n_terms, ",\n",
    "  free_scales = ", tolower(as.character(!isTRUE(input$same_scales))), ",\n",
    "  measure = \"", input$measure, "\",\n",
    "  show_negative = ", tolower(as.character(isTRUE(input$show_negative))), ",\n",
    "  text_size = ", input$text_size, "\n",
    ")\n\n",
    "cutree_rainette(", res_name, ", k = ", input$k, ")"
  )
}

build_double_code <- function(res_name, dtm_name, input) {
  completion <- if (isTRUE(input$complete_km)) {
    paste0(
      "\ngroups <- rainette2_complete_groups(",
      dtm_name,
      ", groups)"
    )
  } else {
    ""
  }

  paste0(
    "rainette2_plot(\n",
    "  ", res_name, ", ", dtm_name, ",\n",
    "  k = ", input$k, ",\n",
    "  criterion = \"", input$criterion, "\",\n",
    "  n_terms = ", input$n_terms, ",\n",
    "  free_scales = ", tolower(as.character(!isTRUE(input$same_scales))), ",\n",
    "  measure = \"", input$measure, "\",\n",
    "  show_negative = ", tolower(as.character(isTRUE(input$show_negative))), ",\n",
    "  complete_groups = ", if (isTRUE(input$complete_km)) "\"TRUE\"" else "FALSE", ",\n",
    "  text_size = ", input$text_size, "\n",
    ")\n\n",
    "groups <- cutree_rainette2(",
    res_name,
    ", k = ",
    input$k,
    ", criterion = \"",
    input$criterion,
    "\")",
    completion
  )
}

simple_explorer_app <- function(res, dtm, corpus_src, metadata) {
  res_name <- metadata$res_name %||% "res"
  dtm_name <- metadata$dtm_name %||% "dtm"
  max_n_groups <- max(res$group, na.rm = TRUE)

  ui <- page_fillable(
    theme = explorer_theme(),
    class = "explorer-shell",
    tags$head(tags$style(HTML(explorer_css()))),
    div(
      class = "explorer-header",
      tags$p(class = "explorer-kicker", "Explorateur Rainette"),
      tags$h1(class = "explorer-title", "rainette_explor"),
      tags$p(
        class = "explorer-copy",
        "Visualisation Shiny native du clustering Rainette. ",
        "Le traitement Python/spaCy reste exécuté côté backend ; cette vue lit simplement le bundle produit par le job."
      )
    ),
    div(
      class = "explorer-layout",
      layout_sidebar(
        fillable = TRUE,
        sidebar = sidebar(
          open = "desktop",
          width = 320,
          sliderInput("k", "Nombre de clusters", value = max_n_groups, min = 2, max = max_n_groups, step = 1),
          selectInput(
            "measure",
            "Statistique",
            choices = c(
              "Keyness - Chi-squared" = "chi2",
              "Keyness - Likelihood ratio" = "lr",
              "Frequency - Terms" = "frequency",
              "Frequency - Documents proportion" = "docprop"
            )
          ),
          numericInput("n_terms", "Nombre de termes à afficher", value = 20, min = 5, max = 30, step = 1),
          conditionalPanel(
            "input.measure != 'docprop'",
            checkboxInput("same_scales", "Forcer les mêmes échelles", value = TRUE)
          ),
          checkboxInput("show_negative", "Afficher les valeurs négatives", value = FALSE),
          sliderInput("text_size", "Taille du texte", value = 12, min = 6, max = 20, step = 1),
          hr(),
          p(class = "explorer-note", "L’option d’échelle reste fixée par défaut pour stabiliser la lecture visuelle.")
        ),
        navset_card_pill(
          id = "explorerTabs",
          full_screen = TRUE,
          class = "explorer-card",
          nav_panel(
            "Résumé",
            card_body_fill(
              plotOutput("rainette_plot", height = "78vh")
            )
          ),
          nav_panel(
            "Documents du cluster",
            card_body_fill(
              docs_sample_ui_proxy("rainette_docs", res)
            )
          ),
          nav_panel(
            "Code R",
            card_body(
              p(class = "explorer-note", "Code R correspondant à la vue courante."),
              verbatimTextOutput("generated_code", placeholder = TRUE)
            )
          )
        )
      )
    )
  )

  server <- function(input, output, session) {
    output$rainette_plot <- renderPlot({
      rainette::rainette_plot(
        res,
        dtm,
        k = input$k,
        n_terms = input$n_terms,
        free_scales = !isTRUE(input$same_scales),
        measure = input$measure,
        show_negative = isTRUE(input$show_negative),
        text_size = input$text_size
      )
    }, res = 120)

    output$generated_code <- renderText({
      build_simple_code(res_name, dtm_name, input)
    })

    current_k <- reactive(input$k)
    docs_sample_server_proxy("rainette_docs", res, corpus_src, current_k)
  }

  shinyApp(ui, server)
}

double_explorer_app <- function(res, dtm, corpus_src, metadata) {
  res_name <- metadata$res_name %||% "res"
  dtm_name <- metadata$dtm_name %||% "dtm"
  max_n_groups <- max(res$k, na.rm = TRUE)

  criterion_choices <- c("Sum of chi-squared" = "chi2")
  if (!is.null(attr(res, "full")) && isTRUE(attr(res, "full"))) {
    criterion_choices <- c(criterion_choices, "Sum of sizes" = "n")
  }

  ui <- page_fillable(
    theme = explorer_theme(),
    class = "explorer-shell",
    tags$head(tags$style(HTML(explorer_css()))),
    div(
      class = "explorer-header",
      tags$p(class = "explorer-kicker", "Explorateur Rainette"),
      tags$h1(class = "explorer-title", "rainette2_explor"),
      tags$p(
        class = "explorer-copy",
        "Exploration Shiny native de la classification double Rainette. ",
        "Le backend Python/spaCy reste inchangé."
      )
    ),
    div(
      class = "explorer-layout",
      layout_sidebar(
        fillable = TRUE,
        sidebar = sidebar(
          open = "desktop",
          width = 320,
          sliderInput("k", "Nombre de clusters", value = max_n_groups, min = 2, max = max_n_groups, step = 1),
          selectInput("criterion", "Critère de partition", choices = criterion_choices),
          checkboxInput("complete_km", "Compléter avec k-nearest neighbours", value = FALSE),
          selectInput(
            "measure",
            "Statistique",
            choices = c(
              "Keyness - Chi-squared" = "chi2",
              "Keyness - Likelihood ratio" = "lr",
              "Frequency - Terms" = "frequency",
              "Frequency - Documents proportion" = "docprop"
            )
          ),
          numericInput("n_terms", "Nombre de termes à afficher", value = 20, min = 5, max = 30, step = 1),
          conditionalPanel(
            "input.measure != 'docprop'",
            checkboxInput("same_scales", "Forcer les mêmes échelles", value = TRUE)
          ),
          checkboxInput("show_negative", "Afficher les valeurs négatives", value = FALSE),
          sliderInput("text_size", "Taille du texte", value = 12, min = 6, max = 20, step = 1)
        ),
        navset_card_pill(
          id = "explorerTabs",
          full_screen = TRUE,
          class = "explorer-card",
          nav_panel(
            "Résumé",
            card_body_fill(
              plotOutput("rainette2_plot", height = "78vh")
            )
          ),
          nav_panel(
            "Documents du cluster",
            card_body_fill(
              docs_sample_ui_proxy("rainette2_docs", res)
            )
          ),
          nav_panel(
            "Code R",
            card_body(
              p(class = "explorer-note", "Code R correspondant à la vue courante."),
              verbatimTextOutput("generated_code", placeholder = TRUE)
            )
          )
        )
      )
    )
  )

  server <- function(input, output, session) {
    output$rainette2_plot <- renderPlot({
      rainette::rainette2_plot(
        res,
        dtm,
        k = input$k,
        criterion = input$criterion,
        n_terms = input$n_terms,
        free_scales = !isTRUE(input$same_scales),
        measure = input$measure,
        show_negative = isTRUE(input$show_negative),
        complete_groups = if (isTRUE(input$complete_km)) "TRUE" else FALSE,
        text_size = input$text_size
      )
    }, res = 120)

    output$generated_code <- renderText({
      build_double_code(res_name, dtm_name, input)
    })

    current_k <- reactive(input$k)
    docs_sample_server_proxy("rainette2_docs", res, corpus_src, current_k)
  }

  shinyApp(ui, server)
}

build_shiny_explorer_app <- function(bundle_path) {
  bundle <- readRDS(bundle_path)
  metadata <- bundle$metadata %||% list()
  classification_type <- metadata$classification_type %||% "simple"

  if (identical(classification_type, "double") || inherits(bundle$cutree_res, "rainette2")) {
    double_explorer_app(
      res = bundle$cutree_res %||% bundle$res,
      dtm = bundle$dtm,
      corpus_src = bundle$corpus_src,
      metadata = metadata
    )
  } else {
    simple_explorer_app(
      res = bundle$plot_res %||% bundle$res,
      dtm = bundle$plot_dtm %||% bundle$dtm,
      corpus_src = bundle$corpus_src,
      metadata = metadata
    )
  }
}
