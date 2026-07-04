safe_rainette_internal <- function(name, fallback = NULL) {
  tryCatch(
    getFromNamespace(name, "rainette"),
    error = function(...) fallback
  )
}

docs_sample_ui_proxy <- safe_rainette_internal("docs_sample_ui")
docs_sample_server_proxy <- safe_rainette_internal("docs_sample_server")
rainette_css_proxy <- safe_rainette_internal("rainette_explor_css", function() "")

rainette_explorer_shell_css <- function() {
  paste0(
    rainette_css_proxy(),
    "
.rainette-explorer-shell {
  background: #f6f1ea;
}
.rainette-explorer-shell .card {
  border-radius: 18px;
}
.rainette-explorer-shell .explorer-note {
  margin: 0;
  color: #6f6255;
  line-height: 1.45;
}
.rainette-explorer-shell .explorer-code {
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

build_rainette_explorer_code <- function(input, res_type) {
  if (identical(res_type, "double")) {
    completion <- if (isTRUE(input$complete_km)) {
      "\ngroups <- rainette2_complete_groups(dtm, groups)"
    } else {
      ""
    }

    return(paste0(
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
    ))
  }

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
          res_type = "double",
          res = cutree_res(),
          dtm = explorer_dtm(),
          corpus = corpus_src(),
          max_k = as.integer(max_k_double() %||% 2L)
        )
      } else {
        list(
          res_type = "simple",
          res = plot_res(),
          dtm = plot_dtm(),
          corpus = corpus_src(),
          max_k = as.integer(max_k_plot() %||% 2L)
        )
      }
    })

    output$content <- shiny::renderUI({
      payload <- explorer_payload()

      if (is.null(payload$res) || is.null(payload$dtm)) {
        return(
          shiny::tagList(
            shiny::tags$style(shiny::HTML(rainette_explorer_shell_css())),
            shiny::div(
              class = "alert alert-warning",
              "Lance une analyse CHD avant d'ouvrir l'exploration Rainette."
            )
          )
        )
      }

      max_k <- payload$max_k
      if (!is.finite(max_k) || is.na(max_k) || max_k < 2L) {
        max_k <- 2L
      }

      default_k <- max_k
      if (identical(payload$res_type, "double")) {
        if (!is.null(payload$res$k) && length(payload$res$k)) {
          default_k <- max(payload$res$k, na.rm = TRUE)
        }
      } else if (!is.null(payload$res$group) && length(payload$res$group)) {
        default_k <- max(payload$res$group, na.rm = TRUE)
      }
      if (!is.finite(default_k) || is.na(default_k)) {
        default_k <- max_k
      }
      default_k <- max(2L, min(max_k, as.integer(default_k)))

      docs_ui <- if (is.function(docs_sample_ui_proxy)) {
        docs_sample_ui_proxy(ns("rainette_docs"), payload$res)
      } else {
        shiny::div(
          class = "alert alert-secondary",
          "Le module officiel « documents par classe » de rainette n'est pas disponible dans cet environnement."
        )
      }

      shiny::tagList(
        shiny::tags$style(shiny::HTML(rainette_explorer_shell_css())),
        shiny::div(
          class = "rainette-explorer-shell",
          bslib::navset_card_tab(
            id = ns("explorer_tabs"),
            full_screen = TRUE,
            bslib::nav_panel(
              "Synthèse",
              bslib::layout_columns(
                col_widths = c(4, 8),
                bslib::card(
                  bslib::card_header("Paramètres Rainette"),
                  shiny::sliderInput(ns("k"), "Nombre de classes", value = default_k, min = 2L, max = max_k, step = 1L),
                  if (identical(payload$res_type, "double")) {
                    shiny::tagList(
                      shiny::selectInput(
                        ns("criterion"),
                        "Critère de partition",
                        choices = c("Somme des chi2" = "chi2", "Somme des tailles" = "n"),
                        selected = "chi2"
                      ),
                      shiny::checkboxInput(ns("complete_km"), "Compléter avec k plus proches voisins", value = FALSE)
                    )
                  },
                  shiny::selectInput(
                    ns("measure"),
                    "Statistiques",
                    choices = c(
                      "Keyness - Chi-squared" = "chi2",
                      "Keyness - Likelihood ratio" = "lr",
                      "Frequency - Terms" = "frequency",
                      "Frequency - Documents proportion" = "docprop"
                    ),
                    selected = "chi2"
                  ),
                  shiny::numericInput(ns("n_terms"), "Nombre de termes à afficher", value = 20, min = 5, max = 30, step = 1),
                  shiny::conditionalPanel(
                    condition = sprintf("input['%s'] != 'docprop'", ns("measure")),
                    ns = ns,
                    shiny::checkboxInput(ns("same_scales"), "Forcer les mêmes échelles", value = TRUE)
                  ),
                  shiny::checkboxInput(ns("show_negative"), "Afficher les valeurs négatives", value = FALSE),
                  shiny::sliderInput(ns("text_size"), "Taille du texte", value = 12, min = 6, max = 20, step = 1),
                  shiny::div(
                    class = "d-grid gap-2",
                    shiny::actionButton(ns("show_code"), "Afficher le code R", class = "btn-primary")
                  ),
                  shiny::p(
                    class = "explorer-note",
                    if (identical(payload$res_type, "double")) {
                      "Vue Shiny branchée sur les fonctions officielles rainette2_plot() pour la classification double."
                    } else {
                      "Vue Shiny branchée sur les fonctions officielles rainette_plot() dans l'esprit de rainette_explor()."
                    }
                  )
                ),
                bslib::card(
                  bslib::card_header("CHD Rainette"),
                  shiny::plotOutput(ns("rainette_plot_live"), height = "72vh")
                )
              )
            ),
            bslib::nav_panel(
              "Documents par classe",
              bslib::card(
                bslib::card_header("Explorer les segments par classe"),
                docs_ui
              )
            ),
            bslib::nav_panel(
              "Code R",
              bslib::card(
                bslib::card_header("Code généré"),
                shiny::div(class = "explorer-code", shiny::verbatimTextOutput(ns("generated_code"), placeholder = TRUE))
              )
            )
          )
        )
      )
    })

    output$rainette_plot_live <- shiny::renderPlot({
      payload <- explorer_payload()
      shiny::req(payload$res, payload$dtm, input$k, input$measure, input$n_terms)

      if (identical(payload$res_type, "double")) {
        rainette::rainette2_plot(
          payload$res,
          payload$dtm,
          k = input$k,
          criterion = input$criterion %||% "chi2",
          n_terms = input$n_terms,
          free_scales = !isTRUE(input$same_scales),
          measure = input$measure,
          show_negative = isTRUE(input$show_negative),
          complete_groups = if (isTRUE(input$complete_km)) "TRUE" else FALSE,
          text_size = input$text_size
        )
      } else {
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
      }
    }, res = 120)

    output$generated_code <- shiny::renderText({
      payload <- explorer_payload()
      if (is.null(payload$res) || is.null(payload$dtm)) {
        return("Aucun code disponible tant qu'aucune analyse n'a été lancée.")
      }
      build_rainette_explorer_code(input, payload$res_type)
    })

    shiny::observeEvent(input$show_code, {
      shiny::showModal(
        shiny::modalDialog(
          title = "Code R Rainette",
          size = "l",
          easyClose = TRUE,
          footer = shiny::modalButton("Fermer"),
          shiny::div(class = "explorer-code", shiny::verbatimTextOutput(ns("generated_code_modal"), placeholder = TRUE))
        )
      )
    })

    output$generated_code_modal <- shiny::renderText({
      payload <- explorer_payload()
      if (is.null(payload$res) || is.null(payload$dtm)) {
        return("Aucun code disponible tant qu'aucune analyse n'a été lancée.")
      }
      build_rainette_explorer_code(input, payload$res_type)
    })

    if (is.function(docs_sample_server_proxy)) {
      docs_state <- shiny::reactiveVal(FALSE)

      shiny::observe({
        payload <- explorer_payload()
        if (docs_state()) {
          return(invisible(NULL))
        }
        if (is.null(payload$res) || is.null(payload$corpus)) {
          return(invisible(NULL))
        }

        current_k <- shiny::reactive({
          input$k %||% 2L
        })

        docs_sample_server_proxy("rainette_docs", payload$res, payload$corpus, current_k)
        docs_state(TRUE)
      })
    }
  })
}
