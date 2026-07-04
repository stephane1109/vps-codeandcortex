safe_rainette_internal <- function(name, fallback = NULL) {
  tryCatch(
    getFromNamespace(name, "rainette"),
    error = function(...) fallback
  )
}

docs_sample_ui_proxy <- safe_rainette_internal("docs_sample_ui")
docs_sample_server_proxy <- safe_rainette_internal("docs_sample_server")
rainette_css_proxy <- safe_rainette_internal("rainette_explor_css", function() "")

rainette_explorer_module_ui <- function(id) {
  ns <- shiny::NS(id)
  shiny::uiOutput(ns("content"))
}

rainette_explorer_module_server <- function(
  id,
  res_type,
  plot_res,
  cutree_res,
  plot_dtm,
  explorer_dtm,
  corpus_src,
  max_k_plot,
  max_k_double
) {
  shiny::moduleServer(id, function(input, output, session) {
    ns <- session$ns

    explorer_payload <- shiny::reactive({
      current_type <- as.character(res_type() %||% "simple")
      if (identical(current_type, "double")) {
        list(
          type = "double",
          res = cutree_res(),
          dtm = explorer_dtm(),
          corpus = corpus_src(),
          max_n_groups = as.integer(max_k_double() %||% 2L),
          criterion_choices = c("Sum of chi-squared" = "chi2", "Sum of sizes" = "n")
        )
      } else {
        list(
          type = "simple",
          res = plot_res(),
          dtm = plot_dtm(),
          corpus = corpus_src(),
          max_n_groups = as.integer(max_k_plot() %||% 2L),
          criterion_choices = NULL
        )
      }
    })

    render_simple_ui <- function(payload) {
      max_n_groups <- payload$max_n_groups
      if (!is.finite(max_n_groups) || is.na(max_n_groups) || max_n_groups < 2L) {
        max_n_groups <- 2L
      }

      miniUI::miniPage(
        shiny::tags$head(shiny::tags$style(rainette_css_proxy())),
        miniUI::miniTabstripPanel(
          miniUI::miniTabPanel(
            "Summary",
            icon = shiny::icon("chart-bar"),
            miniUI::miniContentPanel(
              shiny::fillRow(
                flex = c(1, 3),
                shiny::fillCol(
                  flex = c(10, 1),
                  id = "side",
                  shiny::div(
                    shiny::sliderInput(
                      ns("k"),
                      label = "Number of clusters",
                      value = max_n_groups,
                      min = 2,
                      max = max_n_groups,
                      step = 1
                    ),
                    shiny::selectInput(
                      ns("measure"),
                      "Statistics",
                      choices = c(
                        "Keyness - Chi-squared" = "chi2",
                        "Keyness - Likelihood ratio" = "lr",
                        "Frequency - Terms" = "frequency",
                        "Frequency - Documents proportion" = "docprop"
                      )
                    ),
                    shiny::numericInput(
                      ns("n_terms"),
                      label = "Number of terms to display",
                      value = 20,
                      min = 5,
                      max = 30,
                      step = 1
                    ),
                    shiny::conditionalPanel(
                      "input.measure != 'docprop'",
                      ns = ns,
                      shiny::checkboxInput(
                        ns("same_scales"),
                        label = "Force same scales",
                        value = TRUE
                      )
                    ),
                    shiny::checkboxInput(
                      ns("show_negative"),
                      label = "Show negative values",
                      value = FALSE
                    ),
                    shiny::sliderInput(
                      ns("text_size"),
                      label = "Text size",
                      value = 12,
                      min = 6,
                      max = 20,
                      step = 1
                    )
                  ),
                  shiny::actionButton(
                    ns("get_r_code"),
                    class = "btn-success",
                    icon = shiny::icon("code"),
                    label = gettext("Get R code")
                  )
                ),
                shiny::fillCol(
                  id = "main",
                  shiny::plotOutput(ns("rainette_plot"), height = "100%")
                )
              )
            )
          ),
          miniUI::miniTabPanel(
            "Cluster documents",
            icon = shiny::icon("file-alt"),
            miniUI::miniContentPanel(
              if (is.function(docs_sample_ui_proxy)) {
                docs_sample_ui_proxy(ns("rainette_docs"), payload$res)
              } else {
                shiny::div(
                  class = "alert alert-warning",
                  "The official rainette cluster documents module is not available."
                )
              }
            )
          )
        )
      )
    }

    render_double_ui <- function(payload) {
      max_n_groups <- payload$max_n_groups
      if (!is.finite(max_n_groups) || is.na(max_n_groups) || max_n_groups < 2L) {
        max_n_groups <- 2L
      }

      miniUI::miniPage(
        shiny::tags$head(shiny::tags$style(rainette_css_proxy())),
        miniUI::miniTabstripPanel(
          miniUI::miniTabPanel(
            "Summary",
            icon = shiny::icon("chart-bar"),
            miniUI::miniContentPanel(
              shiny::fillRow(
                flex = c(1, 3),
                shiny::fillCol(
                  flex = c(10, 1),
                  id = "side",
                  shiny::div(
                    shiny::sliderInput(
                      ns("k"),
                      label = "Number of clusters",
                      value = max_n_groups,
                      min = 2,
                      max = max_n_groups,
                      step = 1
                    ),
                    shiny::selectInput(
                      ns("criterion"),
                      "Partition criterion",
                      choices = payload$criterion_choices
                    ),
                    shiny::checkboxInput(
                      ns("complete_km"),
                      label = "Complete with k-nearest neighbours",
                      value = FALSE
                    ),
                    shiny::selectInput(
                      ns("measure"),
                      "Statistics",
                      choices = c(
                        "Keyness - Chi-squared" = "chi2",
                        "Keyness - Likelihood ratio" = "lr",
                        "Frequency - Terms" = "frequency",
                        "Frequency - Documents proportion" = "docprop"
                      )
                    ),
                    shiny::numericInput(
                      ns("n_terms"),
                      label = "Number of terms to display",
                      value = 20,
                      min = 5,
                      max = 30,
                      step = 1
                    ),
                    shiny::conditionalPanel(
                      "input.measure != 'docprop'",
                      ns = ns,
                      shiny::checkboxInput(
                        ns("same_scales"),
                        label = "Force same scales",
                        value = TRUE
                      )
                    ),
                    shiny::checkboxInput(
                      ns("show_negative"),
                      label = "Show negative values",
                      value = FALSE
                    ),
                    shiny::sliderInput(
                      ns("text_size"),
                      label = "Text size",
                      value = 12,
                      min = 6,
                      max = 20,
                      step = 1
                    )
                  ),
                  shiny::actionButton(
                    ns("get_r_code"),
                    class = "btn-success",
                    icon = shiny::icon("code"),
                    label = gettext("Get R code")
                  )
                ),
                shiny::fillCol(
                  id = "main",
                  shiny::plotOutput(ns("rainette2_plot"), height = "100%")
                )
              )
            )
          ),
          miniUI::miniTabPanel(
            "Cluster documents",
            icon = shiny::icon("file-alt"),
            miniUI::miniContentPanel(
              if (is.function(docs_sample_ui_proxy)) {
                docs_sample_ui_proxy(ns("rainette_docs"), payload$res)
              } else {
                shiny::div(
                  class = "alert alert-warning",
                  "The official rainette cluster documents module is not available."
                )
              }
            )
          )
        )
      )
    }

    output$content <- shiny::renderUI({
      payload <- explorer_payload()
      if (is.null(payload$res) || is.null(payload$dtm)) {
        return(
          shiny::div(
            class = "alert alert-warning",
            "Lance une analyse CHD avant d'ouvrir l'exploration Rainette."
          )
        )
      }

      if (identical(payload$type, "double")) {
        render_double_ui(payload)
      } else {
        render_simple_ui(payload)
      }
    })

    simple_plot_code <- shiny::reactive({
      paste0(
        "rainette_plot(\n  res, dtm, k = ",
        input$k,
        ",\n  n_terms = ",
        input$n_terms,
        ",\n  free_scales = ",
        !isTRUE(input$same_scales),
        ",\n  measure = \"",
        input$measure,
        "\"",
        ",\n  show_negative = ",
        isTRUE(input$show_negative),
        ifelse(
          input$text_size != "10",
          paste0(",\n  text_size = ", input$text_size),
          ""
        ),
        "\n)"
      )
    })

    simple_cutree_code <- shiny::reactive({
      paste0("cutree_rainette(res, k = ", input$k, ")")
    })

    double_plot_code <- shiny::reactive({
      paste0(
        "rainette2_plot(\n  res, dtm, k = ",
        input$k,
        ",\n  criterion = \"",
        input$criterion,
        "\"",
        ",\n  n_terms = ",
        input$n_terms,
        ",\n  free_scales = ",
        !isTRUE(input$same_scales),
        ",\n  measure = \"",
        input$measure,
        "\"",
        ",\n  show_negative = ",
        isTRUE(input$show_negative),
        ifelse(
          isTRUE(input$complete_km),
          paste0(",\n  complete_groups = \"", input$complete_km, "\""),
          ""
        ),
        ifelse(
          input$text_size != "10",
          paste0(",\n  text_size = ", input$text_size),
          ""
        ),
        "\n)"
      )
    })

    double_cutree_code <- shiny::reactive({
      out <- ""
      if (isTRUE(input$complete_km)) {
        out <- "groups <- "
      }
      out <- paste0(
        out,
        "cutree_rainette2(res, k = ",
        input$k,
        ", criterion = \"",
        input$criterion,
        "\")"
      )
      if (isTRUE(input$complete_km)) {
        out <- paste0(out, "\n", "rainette2_complete_groups(dtm, groups)")
      }
      out
    })

    generate_code <- shiny::reactive({
      payload <- explorer_payload()
      if (identical(payload$type, "double")) {
        paste0(
          "## Clustering description plot\n",
          double_plot_code(),
          "\n## Groups\n",
          double_cutree_code()
        )
      } else {
        paste0(
          "## Clustering description plot\n",
          simple_plot_code(),
          "\n## Groups\n",
          simple_cutree_code()
        )
      }
    })

    output$rainette_plot <- shiny::renderPlot({
      payload <- explorer_payload()
      shiny::req(payload$res, payload$dtm, input$k, input$measure, input$n_terms)

      rainette::rainette_plot(
        payload$res,
        payload$dtm,
        k = input$k,
        n_terms = input$n_terms,
        free_scales = !isTRUE(input$same_scales),
        measure = input$measure,
        show_negative = isTRUE(input$show_negative),
        text_size = input$text_size
      )
    })

    output$rainette2_plot <- shiny::renderPlot({
      payload <- explorer_payload()
      shiny::req(payload$res, payload$dtm, input$k, input$criterion, input$measure, input$n_terms)

      rainette::rainette2_plot(
        payload$res,
        payload$dtm,
        k = input$k,
        criterion = input$criterion,
        n_terms = input$n_terms,
        free_scales = !isTRUE(input$same_scales),
        measure = input$measure,
        show_negative = isTRUE(input$show_negative),
        complete_groups = if (isTRUE(input$complete_km)) "TRUE" else FALSE,
        text_size = input$text_size
      )
    })

    shiny::observeEvent(input$get_r_code, {
      code <- generate_code()
      shiny::showModal(shiny::modalDialog(
        title = gettext("Export R code"),
        size = "l",
        shiny::HTML(paste0(
          "Code to generate the current plot and compute groups :",
          "<pre><code>",
          paste(highr::hi_html(code), collapse = "\n"),
          "</code></pre>"
        )),
        easyClose = TRUE
      ))
    })

    shiny::observe({
      payload <- explorer_payload()
      if (!is.function(docs_sample_server_proxy)) {
        return(invisible(NULL))
      }
      if (is.null(payload$res) || is.null(payload$corpus)) {
        return(invisible(NULL))
      }

      current_k <- shiny::reactive(input$k)
      docs_sample_server_proxy("rainette_docs", payload$res, payload$corpus, current_k)
    })
  })
}
