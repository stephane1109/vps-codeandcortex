rainette_explor_native_css <- function() {
  getFromNamespace("rainette_explor_css", "rainette")()
}

rainette_docs_sample_server_reactive <- function(id, res_r, corpus_src_r, current_k) {
  shiny::moduleServer(id, function(input, output, session) {
    output$group_ui <- shiny::renderUI({
      res <- res_r()
      shiny::req(res)
      ns <- session$ns
      shiny::selectInput(
        ns("cluster"),
        label = "Cluster",
        selected = 1,
        choices = seq_len(current_k())
      )
    })

    groups <- shiny::reactive({
      res <- res_r()
      shiny::req(res)
      rainette::cutree(res, k = current_k())
    })

    corpus_cluster <- shiny::reactive({
      corpus_src <- corpus_src_r()
      res <- res_r()
      shiny::req(corpus_src, res)

      if (!is.null(input$show_merged) && isTRUE(input$show_merged)) {
        corpus_tmp <- corpus_src
        corpus_tmp$group <- groups()
        corpus_tmp$doc_name <- quanteda::docnames(corpus_tmp)
        corpus_tmp$uc_id <- res$corresp_uce_uc$uc
        quanteda::docvars(corpus_tmp) <- quanteda::docvars(corpus_tmp) %>%
          dplyr::group_by(.data$uc_id) %>%
          dplyr::mutate(doc_name = paste(.data$doc_name, collapse = " | ")) %>%
          dplyr::ungroup()
        result <- quanteda::corpus_group(corpus_tmp, groups = corpus_tmp$doc_name)
        sel <- quanteda::docvars(result, "group") == input$cluster &
          !is.na(quanteda::docvars(result, "group"))
        return(result[sel])
      }

      sel <- groups() == input$cluster & !is.na(groups())
      corpus_src[sel]
    })

    filter_regex <- shiny::reactive({
      stringr::regex(shiny::req(input$filter_term), ignore_case = TRUE, multiline = TRUE)
    })

    corpus_filtered <- shiny::reactive({
      corpus_src <- corpus_src_r()
      shiny::req(corpus_src)

      result <- corpus_cluster()
      filter_term <- stringr::str_trim(input$filter_term)
      if (!is.null(filter_term) && nzchar(filter_term)) {
        keep <- stringr::str_detect(as.character(result), filter_regex())
        result <- result[keep]
      }
      result
    })

    highlighter <- shiny::reactive({
      filter_term <- stringr::str_trim(input$filter_term)
      if (!is.null(filter_term) && nzchar(filter_term)) {
        function(txt) {
          stringr::str_replace_all(txt, filter_regex(), "<span class='highlight'>\\0</span>")
        }
      } else {
        I
      }
    })

    n_doc <- shiny::reactive({
      n_doc <- input$ndoc
      if (is.null(n_doc) || is.na(n_doc) || n_doc < 1) {
        n_doc <- 1
      }
      n_doc
    })

    n_char <- shiny::reactive({
      n_char <- input$nchar
      if (is.null(n_char) || is.na(n_char) || n_char < 1) {
        n_char <- 1
      }
      n_char
    })

    output$docs_sample_intro <- shiny::renderUI({
      corpus_src <- corpus_src_r()
      if (is.null(corpus_src)) {
        return(shiny::HTML(
          "<p>Can't display documents : <tt>corpus_src</tt> is null.</p><p>Please rerun <tt>rainette_explor</tt> with your quanteda corpus object as third parameter : something like <tt>rainette_explor(res, dtm, corpus)</tt>.</p>"
        ))
      }

      nb_docs_cluster <- quanteda::ndoc(corpus_filtered())
      out <- paste0("Displayed : <strong>", min(n_doc(), nb_docs_cluster), "</strong>")
      if (quanteda::ndoc(corpus_cluster()) != quanteda::ndoc(corpus_filtered())) {
        out <- paste0(
          out,
          " - Filtered documents : <strong>",
          quanteda::ndoc(corpus_filtered()),
          "</strong>"
        )
      }
      out <- paste0(out, " - Cluster size : <strong>", quanteda::ndoc(corpus_cluster()), "</strong>.")
      shiny::HTML(out)
    })

    output$docs_sample <- shiny::renderUI({
      corpus_src <- corpus_src_r()
      if (is.null(corpus_src)) {
        return(NULL)
      }

      size <- min(quanteda::ndoc(corpus_filtered()), n_doc())
      if (size < 1) {
        return(shiny::HTML("<p>Aucun document pour cette classe avec le filtre courant.</p>"))
      }

      if (isTRUE(input$random_sample)) {
        corp <- quanteda::corpus_sample(corpus_filtered(), size = size)
      } else {
        corp <- corpus_filtered()[seq_len(size)]
      }

      txt <- as.character(corp)
      txt <- ifelse(
        nchar(txt) <= n_char(),
        txt,
        paste(stringr::str_sub(txt, 1, n_char()), "(...)")
      )
      txt <- highlighter()(txt)

      out <- paste(
        "<div class='doc'>",
        "<div class='docname'>",
        quanteda::docnames(corp),
        "</div>",
        stringr::str_replace_all(txt, "\n", "<br>"),
        "</div>",
        "<hr>",
        collapse = "\n"
      )
      shiny::HTML(out)
    })
  })
}

rainette_explor_module_ui <- function(id) {
  ns <- shiny::NS(id)
  condition_same_scales <- sprintf("input['%s'] != 'docprop'", ns("measure"))

  shiny::tagList(
    shiny::tags$style(shiny::HTML(rainette_explor_native_css())),
    shiny::tags$style(shiny::HTML("
      .rainette-original-shell {
        position: relative;
        width: 100%;
        height: 100%;
        min-height: 72vh;
      }
      .rainette-original-shell > .gadget-tabs-content-container,
      .rainette-original-shell > .gadget-tabs-content-container > .tab-content,
      .rainette-original-shell > .gadget-tabs-content-container > .tab-content > .tab-pane,
      .rainette-original-shell .gadget-tabs-content-inner,
      .rainette-original-shell .gadget-scroll,
      .rainette-original-shell .gadget-content {
        height: 100% !important;
        min-height: 100% !important;
      }
      .rainette-original-shell > .gadget-tabs-content-container > .tab-content > .tab-pane {
        position: relative !important;
      }
      .rainette-original-shell .nav-tabs {
        border-bottom: 1px solid #ddd;
        gap: 0;
        padding: 0;
      }
      .rainette-original-shell .nav-tabs .nav-link {
        border: 1px solid transparent;
        border-radius: 4px 4px 0 0;
        background: transparent;
        color: #337ab7;
        font-weight: 400;
        margin-bottom: -1px;
        box-shadow: none;
      }
      .rainette-original-shell .nav-tabs .nav-link:hover {
        border-color: #eee #eee #ddd;
        background: #f9f9f9;
        color: #23527c;
      }
      .rainette-original-shell .nav-tabs .nav-link.active,
      .rainette-original-shell .nav-tabs .nav-link.active:hover {
        color: #555;
        background-color: #fff;
        border: 1px solid #ddd;
        border-bottom-color: transparent;
        box-shadow: none;
      }
      .rainette-original-shell .tab-content {
        background: #fff;
      }
    ")),
    htmltools::div(
      class = "rainette-original-shell",
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
                div(
                  shiny::sliderInput(ns("k"), "Number of clusters", value = 2, min = 2, max = 2, step = 1),
                  shiny::selectInput(
                    ns("measure"),
                    "Statistics",
                    choices = c(
                      "Keyness - Chi-squared" = "chi2",
                      "Keyness - Likelihood ratio" = "lr",
                      "Frequency - Terms" = "frequency",
                      "Frequency - Documents proportion" = "docprop"
                    ),
                    selected = "chi2"
                  ),
                  shiny::numericInput(ns("n_terms"), "Number of terms to display", value = 20, min = 5, max = 30, step = 1),
                  shiny::conditionalPanel(
                    condition = condition_same_scales,
                    shiny::checkboxInput(ns("same_scales"), "Force same scales", value = TRUE)
                  ),
                  shiny::checkboxInput(ns("show_negative"), "Show negative values", value = FALSE),
                  shiny::sliderInput(ns("text_size"), "Text size", value = 8, min = 6, max = 20, step = 1),
                  shiny::actionButton(ns("get_r_code"), class = "btn-success", icon = shiny::icon("code"), label = "Get R code")
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
            shiny::uiOutput(ns("docs_ui"))
          )
        )
      )
    )
  )
}

rainette_explor_module_server <- function(id, res_r, dtm_r, corpus_r, bundle_file_r = NULL, min_segment_size_r = NULL) {
  shiny::moduleServer(id, function(input, output, session) {
    shiny::observe({
      res <- res_r()
      if (is.null(res)) {
        return(invisible(NULL))
      }

      max_n_groups <- max(res$group, na.rm = TRUE)
      shiny::updateSliderInput(
        session,
        "k",
        min = 2,
        max = max_n_groups,
        value = max_n_groups,
        step = 1
      )
    })

    bundle_target <- shiny::reactive({
      bundle_file <- if (is.null(bundle_file_r)) NULL else bundle_file_r()
      if (!is.null(bundle_file) && nzchar(bundle_file)) {
        return(basename(bundle_file))
      }
      "analysis_bundle.rds"
    })

    plot_code <- shiny::reactive({
      paste0(
        "rainette_plot(\n",
        "  bundle$res, bundle$dtm, k = ", input$k, ",\n",
        "  n_terms = ", input$n_terms, ",\n",
        "  free_scales = ", !isTRUE(input$same_scales), ",\n",
        "  measure = \"", input$measure, "\",\n",
        "  show_negative = ", isTRUE(input$show_negative),
        if (input$text_size != 10) paste0(",\n  text_size = ", input$text_size) else "",
        "\n)"
      )
    })

    cutree_code <- shiny::reactive({
      paste0("cutree_rainette(bundle$res, k = ", input$k, ")")
    })

    generate_code <- shiny::reactive({
      paste(
        "library(rainette)",
        paste0("bundle <- readRDS('", bundle_target(), "')"),
        "## Clustering description plot",
        plot_code(),
        "## Groups",
        cutree_code(),
        sep = "\n"
      )
    })

    output$rainette_plot <- shiny::renderPlot({
      res <- res_r()
      dtm <- dtm_r()
      shiny::req(res, dtm)

      tryCatch(
        rainette::rainette_plot(
          res,
          dtm,
          k = input$k,
          n_terms = input$n_terms,
          free_scales = !isTRUE(input$same_scales),
          measure = input$measure,
          show_negative = isTRUE(input$show_negative),
          text_size = input$text_size
        ),
        error = function(e) {
          plot.new()
          text(0.5, 0.5, paste0("Erreur d'affichage Rainette : ", conditionMessage(e)), cex = 1)
        }
      )
    }, res = 140)

    shiny::observeEvent(input$get_r_code, {
      code <- generate_code()
      shiny::showModal(
        shiny::modalDialog(
          title = "Export R code",
          size = "l",
          shiny::HTML(
            paste0(
              "Code to generate the current plot and compute groups :",
              "<pre><code>",
              paste(highr::hi_html(code), collapse = "\n"),
              "</code></pre>"
            )
          ),
          easyClose = TRUE
        )
      )
    })

    output$docs_ui <- shiny::renderUI({
      res <- res_r()
      corpus_src <- corpus_r()
      dtm <- dtm_r()

      if (is.null(res) || is.null(corpus_src) || is.null(dtm)) {
        return(shiny::tags$p("Lance une analyse pour ouvrir ici le vrai explorateur Rainette des documents de classes."))
      }

      getFromNamespace("docs_sample_ui", "rainette")(
        session$ns("docs"),
        res
      )
    })

    rainette_docs_sample_server_reactive(
      "docs",
      res_r = res_r,
      corpus_src_r = corpus_r,
      current_k = shiny::reactive(input$k)
    )
  })
}
