safe_rainette_internal <- function(name, fallback = NULL) {
  tryCatch(
    getFromNamespace(name, "rainette"),
    error = function(...) fallback
  )
}

docs_sample_ui_proxy <- safe_rainette_internal("docs_sample_ui")
docs_sample_server_proxy <- safe_rainette_internal("docs_sample_server")

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
  max_k_double,
  min_segment_size_value = NULL
) {
  shiny::moduleServer(id, function(input, output, session) {
    ns <- session$ns

    normalize_rainette_result_for_docs <- function(res, min_segment_size_fallback = NULL) {
      if (is.null(res) || inherits(res, "rainette2")) {
        return(res)
      }

      res_copy <- res
      current_value <- NULL

      if (!is.null(res_copy$call$min_segment_size) &&
          is.atomic(res_copy$call$min_segment_size) &&
          length(res_copy$call$min_segment_size) == 1L) {
        current_value <- suppressWarnings(as.numeric(res_copy$call$min_segment_size))
      }

      if ((!is.finite(current_value) || is.na(current_value)) &&
          !is.null(min_segment_size_fallback) &&
          is.atomic(min_segment_size_fallback) &&
          length(min_segment_size_fallback) == 1L) {
        current_value <- suppressWarnings(as.numeric(min_segment_size_fallback))
      }

      if (is.finite(current_value) && !is.na(current_value)) {
        res_copy$call$min_segment_size <- current_value
      }

      res_copy
    }

    current_k_value <- shiny::reactive({
      value <- suppressWarnings(as.integer(input$k))
      if (!is.finite(value) || is.na(value) || value < 2L) {
        value <- 2L
      }
      value
    })

    scoped_docs_css <- function() {
      paste(
        ".rainette-embedded .rainette-summary-layout { gap: 1rem; }",
        ".rainette-embedded .rainette-summary-controls { background: #f8f3ed; border: 1px solid rgba(47, 36, 28, 0.08); border-radius: 18px; padding: 1rem; }",
        ".rainette-embedded .rainette-plot-card { background: #fffdf9; border: 1px solid rgba(47, 36, 28, 0.08); border-radius: 18px; padding: 0.75rem; }",
        ".rainette-embedded .rainette-plot-card .shiny-plot-output { min-height: 72vh; }",
        ".rainette-embedded #docs { height: 72vh; max-height: 72vh; overflow-y: hidden; padding-left: 1rem; }",
        ".rainette-embedded #docs_sample { height: 100%; max-height: 100%; overflow-y: auto; padding-right: 1rem; }",
        ".rainette-embedded #docs_sample_intro { color: #2b6cb0; background-color: #f1f5f9; border-radius: 10px; padding: 0.75rem 1rem; margin-bottom: 1rem; }",
        ".rainette-embedded #docs_sample hr { margin-top: 12px; margin-bottom: 12px; }",
        ".rainette-embedded #side { background-color: #f3e7d8; padding: 1.25rem; border-radius: 18px; font-size: 12px; }",
        ".rainette-embedded .docname { font-size: 80%; color: #2b6cb0; margin: 0 0 .3em 0; }",
        ".rainette-embedded .doc { font-size: 100%; max-width: 50em; border-left: 3px solid #d96b2b; margin: 0; padding: .3em 1em .2em 1em; background: #fffdf9; }",
        ".rainette-embedded .doc .highlight { background-color: #ffe066; }",
        ".rainette-embedded span.hl.str { color: #d14; }",
        ".rainette-embedded span.hl.kwa, .rainette-embedded span.hl.num { color: #099; }",
        ".rainette-embedded span.hl.kwd { color: #333; font-weight: bold; }",
        ".rainette-embedded span.hl.com { color: #888; font-style: italic; }",
        sep = "\n"
      )
    }

    safe_docs_ui <- function(payload) {
      if (!is.function(docs_sample_ui_proxy)) {
        return(
          shiny::div(
            class = "alert alert-warning",
            "Le module officiel Rainette pour les documents n'est pas disponible dans cette image."
          )
        )
      }

      tryCatch(
        docs_sample_ui_proxy(ns("rainette_docs"), payload$docs_res),
        error = function(e) {
          shiny::div(
            class = "alert alert-warning",
            paste0("Le volet documents Rainette n'a pas pu se charger : ", e$message)
          )
        }
      )
    }

    explorer_payload <- shiny::reactive({
      current_type <- as.character(res_type() %||% "simple")
      if (identical(current_type, "double")) {
        list(
          type = "double",
          res = cutree_res(),
          docs_res = cutree_res(),
          dtm = plot_dtm(),
          corpus = corpus_src(),
          max_n_groups = as.integer(max_k_double() %||% 2L),
          criterion_choices = c("Somme des chi2" = "chi2", "Somme des effectifs" = "n")
        )
      } else {
        plot_res_value <- plot_res()
        list(
          type = "simple",
          res = plot_res_value,
          docs_res = normalize_rainette_result_for_docs(
            plot_res_value,
            min_segment_size_value() %||% NULL
          ),
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

      shiny::tagList(
        shiny::tags$style(shiny::HTML(scoped_docs_css())),
        shiny::div(
          class = "rainette-embedded",
          bslib::navset_pill(
            id = ns("rainette_tabs"),
            bslib::nav_panel(
              "Résumé",
              bslib::layout_columns(
                col_widths = c(4, 8),
                shiny::div(
                  class = "rainette-summary-controls",
                  shiny::sliderInput(
                    ns("k"),
                    label = "Nombre de classes",
                    value = max_n_groups,
                    min = 2,
                    max = max_n_groups,
                    step = 1
                  ),
                  shiny::selectInput(
                    ns("measure"),
                    "Statistique",
                    choices = c(
                      "Keyness - Chi2" = "chi2",
                      "Keyness - Likelihood ratio" = "lr",
                      "Fréquence - Termes" = "frequency",
                      "Fréquence - Proportion de documents" = "docprop"
                    )
                  ),
                  shiny::numericInput(
                    ns("n_terms"),
                    label = "Nombre de termes affichés",
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
                      label = "Forcer les mêmes échelles",
                      value = TRUE
                    )
                  ),
                  shiny::checkboxInput(
                    ns("show_negative"),
                    label = "Afficher les valeurs négatives",
                    value = FALSE
                  ),
                  shiny::sliderInput(
                    ns("text_size"),
                    label = "Taille du texte",
                    value = 12,
                    min = 6,
                    max = 20,
                    step = 1
                  ),
                  shiny::actionButton(
                    ns("get_r_code"),
                    class = "btn-success",
                    icon = shiny::icon("code"),
                    label = "Code R"
                  )
                ),
                shiny::div(
                  class = "rainette-plot-card",
                  shiny::plotOutput(ns("rainette_plot"), height = "72vh")
                )
              )
            ),
            bslib::nav_panel(
              "Documents du cluster",
              safe_docs_ui(payload)
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

      shiny::tagList(
        shiny::tags$style(shiny::HTML(scoped_docs_css())),
        shiny::div(
          class = "rainette-embedded",
          bslib::navset_pill(
            id = ns("rainette_tabs"),
            bslib::nav_panel(
              "Résumé",
              bslib::layout_columns(
                col_widths = c(4, 8),
                shiny::div(
                  class = "rainette-summary-controls",
                  shiny::sliderInput(
                    ns("k"),
                    label = "Nombre de classes",
                    value = max_n_groups,
                    min = 2,
                    max = max_n_groups,
                    step = 1
                  ),
                  shiny::selectInput(
                    ns("criterion"),
                    "Critère de partition",
                    choices = payload$criterion_choices
                  ),
                  shiny::checkboxInput(
                    ns("complete_km"),
                    label = "Compléter par k plus proches voisins",
                    value = FALSE
                  ),
                  shiny::selectInput(
                    ns("measure"),
                    "Statistique",
                    choices = c(
                      "Keyness - Chi2" = "chi2",
                      "Keyness - Likelihood ratio" = "lr",
                      "Fréquence - Termes" = "frequency",
                      "Fréquence - Proportion de documents" = "docprop"
                    )
                  ),
                  shiny::numericInput(
                    ns("n_terms"),
                    label = "Nombre de termes affichés",
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
                      label = "Forcer les mêmes échelles",
                      value = TRUE
                    )
                  ),
                  shiny::checkboxInput(
                    ns("show_negative"),
                    label = "Afficher les valeurs négatives",
                    value = FALSE
                  ),
                  shiny::sliderInput(
                    ns("text_size"),
                    label = "Taille du texte",
                    value = 12,
                    min = 6,
                    max = 20,
                    step = 1
                  ),
                  shiny::actionButton(
                    ns("get_r_code"),
                    class = "btn-success",
                    icon = shiny::icon("code"),
                    label = "Code R"
                  )
                ),
                shiny::div(
                  class = "rainette-plot-card",
                  shiny::plotOutput(ns("rainette2_plot"), height = "72vh")
                )
              )
            ),
            bslib::nav_panel(
              "Documents du cluster",
              safe_docs_ui(payload)
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

      tryCatch(
        if (identical(payload$type, "double")) {
          render_double_ui(payload)
        } else {
          render_simple_ui(payload)
        },
        error = function(e) {
          shiny::div(
            class = "alert alert-danger",
            paste0("L'interface Rainette n'a pas pu s'afficher : ", e$message)
          )
        }
      )
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

      tryCatch(
        rainette::rainette_plot(
          payload$res,
          payload$dtm,
          k = input$k,
          n_terms = input$n_terms,
          free_scales = !isTRUE(input$same_scales),
          measure = input$measure,
          show_negative = isTRUE(input$show_negative),
          text_size = input$text_size
        ),
        error = function(e) {
          graphics::plot.new()
          graphics::text(0.5, 0.5, paste0("Erreur d'affichage CHD : ", e$message), cex = 1)
        }
      )
    })

    output$rainette2_plot <- shiny::renderPlot({
      payload <- explorer_payload()
      shiny::req(payload$res, payload$dtm, input$k, input$criterion, input$measure, input$n_terms)

      tryCatch(
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
        ),
        error = function(e) {
          graphics::plot.new()
          graphics::text(0.5, 0.5, paste0("Erreur d'affichage CHD double : ", e$message), cex = 1)
        }
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

      current_k <- shiny::reactive(current_k_value())

      tryCatch(
        docs_sample_server_proxy("rainette_docs", payload$docs_res, payload$corpus, current_k),
        error = function(...) invisible(NULL)
      )
    })
  })
}
