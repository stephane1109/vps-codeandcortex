#!/usr/bin/env Rscript

options(
  stringsAsFactors = FALSE,
  bspm.sudo = TRUE
)

suppressPackageStartupMessages({
  library(shiny)
  library(miniUI)
  library(rainette)
  library(quanteda)
  library(htmltools)
})

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) return(right)
  left
}

docs_sample_ui_proxy <- getFromNamespace("docs_sample_ui", "rainette")
docs_sample_server_proxy <- getFromNamespace("docs_sample_server", "rainette")
rainette_css_proxy <- getFromNamespace("rainette_explor_css", "rainette")

explorer_shell_css <- function() {
  paste0(
    rainette_css_proxy(),
    "
body {
  background: #f6f1ea;
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
}
.miniTabstripPanel {
  min-height: 100vh;
}
.miniTabstripPanel .tab-content {
  min-height: calc(100vh - 64px);
}
#side {
  background: #efe5d8;
  border-right: 1px solid rgba(217, 107, 43, 0.15);
}
#main {
  background: #fbf7f2;
}
#docs_sample_intro {
  color: #714a2f;
  background: rgba(217, 107, 43, 0.08);
}
.explorer-actions {
  display: flex;
  gap: 0.7rem;
  margin-top: 1rem;
}
.explorer-note {
  margin-top: 0.7rem;
  color: #6f6255;
  line-height: 1.45;
}
.explorer-code {
  white-space: pre-wrap;
  background: #1f1b18;
  color: #f6ede5;
  border-radius: 16px;
  padding: 1rem;
  min-height: 14rem;
  overflow: auto;
}
"
  )
}

build_simple_code <- function(input) {
  paste0(
    "rainette_plot(\n",
    "  res,\n",
    "  dtm,\n",
    "  k = ", input$k, ",\n",
    "  n_terms = ", input$n_terms, ",\n",
    "  free_scales = ", tolower(as.character(!isTRUE(input$same_scales))), ",\n",
    "  measure = \"", input$measure, "\",\n",
    "  show_negative = ", tolower(as.character(isTRUE(input$show_negative))),
    if (identical(as.integer(input$text_size), 10L)) "" else paste0(",\n  text_size = ", input$text_size),
    "\n)\n\n",
    "cutree_rainette(res, k = ", input$k, ")"
  )
}

build_double_code <- function(input) {
  completion <- if (isTRUE(input$complete_km)) {
    "\ngroups <- rainette2_complete_groups(dtm, groups)"
  } else {
    ""
  }

  paste0(
    "rainette2_plot(\n",
    "  res,\n",
    "  dtm,\n",
    "  k = ", input$k, ",\n",
    "  criterion = \"", input$criterion, "\",\n",
    "  n_terms = ", input$n_terms, ",\n",
    "  free_scales = ", tolower(as.character(!isTRUE(input$same_scales))), ",\n",
    "  measure = \"", input$measure, "\",\n",
    "  show_negative = ", tolower(as.character(isTRUE(input$show_negative))),
    if (isTRUE(input$complete_km)) ",\n  complete_groups = \"TRUE\"" else "",
    if (identical(as.integer(input$text_size), 10L)) "" else paste0(",\n  text_size = ", input$text_size),
    "\n)\n\n",
    "groups <- cutree_rainette2(res, k = ", input$k, ", criterion = \"", input$criterion, "\")",
    completion
  )
}

build_simple_explorer_app <- function(res, dtm, corpus_src = NULL) {
  if (is.null(dtm)) {
    stop("rainette_explor doit recevoir le résultat et son dtm associé.")
  }
  if (!is.null(corpus_src) && quanteda::ndoc(corpus_src) != quanteda::ndoc(dtm)) {
    stop("corpus_src et dtm doivent avoir le même nombre de documents.")
  }
  if (inherits(res, "rainette2")) {
    stop("Utilisez rainette2_explor pour un résultat rainette2.")
  }
  if (length(res$group) != quanteda::ndoc(dtm)) {
    stop("Le résultat rainette et le dtm doivent avoir le même nombre de documents.")
  }

  max_n_groups <- max(res$group, na.rm = TRUE)

  ui <- miniPage(
    tags$head(tags$style(HTML(explorer_shell_css()))),
    miniTabstripPanel(
      miniTabPanel(
        "Summary",
        icon = shiny::icon("chart-bar"),
        miniContentPanel(
          fillRow(
            flex = c(1, 3),
            fillCol(
              flex = c(10, 1),
              id = "side",
              div(
                sliderInput("k", "Number of clusters", value = max_n_groups, min = 2, max = max_n_groups, step = 1),
                selectInput(
                  "measure",
                  "Statistics",
                  choices = c(
                    "Keyness - Chi-squared" = "chi2",
                    "Keyness - Likelihood ratio" = "lr",
                    "Frequency - Terms" = "frequency",
                    "Frequency - Documents proportion" = "docprop"
                  )
                ),
                numericInput("n_terms", "Number of terms to display", value = 20, min = 5, max = 30, step = 1),
                conditionalPanel(
                  "input.measure != 'docprop'",
                  checkboxInput("same_scales", "Force same scales", value = TRUE)
                ),
                checkboxInput("show_negative", "Show negative values", value = FALSE),
                sliderInput("text_size", "Text size", value = 12, min = 6, max = 20, step = 1),
                div(
                  class = "explorer-actions",
                  actionButton("show_code", label = "Get R code", icon = icon("code"), class = "btn-success")
                ),
                p(class = "explorer-note", "Vue Shiny native construite à partir du code officiel de rainette_explor().")
              )
            ),
            fillCol(
              id = "main",
              plotOutput("rainette_plot", height = "100%")
            )
          )
        )
      ),
      miniTabPanel(
        "Cluster documents",
        icon = shiny::icon("file-alt"),
        miniContentPanel(
          docs_sample_ui_proxy("rainette1", res)
        )
      ),
      miniTabPanel(
        "Code",
        icon = shiny::icon("code"),
        miniContentPanel(
          div(class = "explorer-code", verbatimTextOutput("generated_code", placeholder = TRUE))
        )
      )
    )
  )

  server <- function(input, output, session) {
    plot_code <- reactive(build_simple_code(input))

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
      plot_code()
    })

    observeEvent(input$show_code, {
      showModal(modalDialog(
        title = "Export R code",
        size = "l",
        easyClose = TRUE,
        HTML(paste0("<pre><code>", plot_code(), "</code></pre>"))
      ))
    })

    current_k <- reactive(input$k)
    docs_sample_server_proxy("rainette1", res, corpus_src, current_k)
  }

  shinyApp(ui, server)
}

build_double_explorer_app <- function(res, dtm, corpus_src = NULL) {
  if (is.null(dtm)) {
    stop("rainette2_explor doit recevoir le résultat et son dtm associé.")
  }
  if (inherits(res, "rainette")) {
    stop("Le résultat transmis semble être un objet rainette simple.")
  }

  criterion_choices <- c("Sum of chi-squared" = "chi2")
  if (!is.null(attr(res, "full")) && isTRUE(attr(res, "full"))) {
    criterion_choices <- c(criterion_choices, "Sum of sizes" = "n")
  }

  max_n_groups <- max(res$k, na.rm = TRUE)

  ui <- miniPage(
    tags$head(tags$style(HTML(explorer_shell_css()))),
    miniTabstripPanel(
      miniTabPanel(
        "Summary",
        icon = shiny::icon("chart-bar"),
        miniContentPanel(
          fillRow(
            flex = c(1, 3),
            fillCol(
              flex = c(10, 1),
              id = "side",
              div(
                sliderInput("k", "Number of clusters", value = max_n_groups, min = 2, max = max_n_groups, step = 1),
                selectInput("criterion", "Partition criterion", choices = criterion_choices),
                checkboxInput("complete_km", "Complete with k-nearest neighbours", value = FALSE),
                selectInput(
                  "measure",
                  "Statistics",
                  choices = c(
                    "Keyness - Chi-squared" = "chi2",
                    "Keyness - Likelihood ratio" = "lr",
                    "Frequency - Terms" = "frequency",
                    "Frequency - Documents proportion" = "docprop"
                  )
                ),
                numericInput("n_terms", "Number of terms to display", value = 20, min = 5, max = 30, step = 1),
                conditionalPanel(
                  "input.measure != 'docprop'",
                  checkboxInput("same_scales", "Force same scales", value = TRUE)
                ),
                checkboxInput("show_negative", "Show negative values", value = FALSE),
                sliderInput("text_size", "Text size", value = 12, min = 6, max = 20, step = 1),
                div(
                  class = "explorer-actions",
                  actionButton("show_code", label = "Get R code", icon = icon("code"), class = "btn-success")
                ),
                p(class = "explorer-note", "Vue Shiny native construite à partir du code officiel de rainette2_explor().")
              )
            ),
            fillCol(
              id = "main",
              plotOutput("rainette2_plot", height = "100%")
            )
          )
        )
      ),
      miniTabPanel(
        "Cluster documents",
        icon = shiny::icon("file-alt"),
        miniContentPanel(
          docs_sample_ui_proxy("rainette2", res)
        )
      ),
      miniTabPanel(
        "Code",
        icon = shiny::icon("code"),
        miniContentPanel(
          div(class = "explorer-code", verbatimTextOutput("generated_code", placeholder = TRUE))
        )
      )
    )
  )

  server <- function(input, output, session) {
    plot_code <- reactive(build_double_code(input))

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
      plot_code()
    })

    observeEvent(input$show_code, {
      showModal(modalDialog(
        title = "Export R code",
        size = "l",
        easyClose = TRUE,
        HTML(paste0("<pre><code>", plot_code(), "</code></pre>"))
      ))
    })

    current_k <- reactive(input$k)
    docs_sample_server_proxy("rainette2", res, corpus_src, current_k)
  }

  shinyApp(ui, server)
}

build_shiny_explorer_app <- function(bundle_path) {
  bundle <- readRDS(bundle_path)
  metadata <- bundle$metadata %||% list()
  classification_type <- metadata$classification_type %||% "simple"

  if (identical(classification_type, "double") || inherits(bundle$cutree_res, "rainette2")) {
    build_double_explorer_app(
      res = bundle$cutree_res %||% bundle$res,
      dtm = bundle$dtm,
      corpus_src = bundle$corpus_src
    )
  } else {
    build_simple_explorer_app(
      res = bundle$plot_res %||% bundle$res,
      dtm = bundle$plot_dtm %||% bundle$dtm,
      corpus_src = bundle$corpus_src
    )
  }
}
