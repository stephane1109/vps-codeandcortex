rainette_explor_native_css <- function() {
  getFromNamespace("rainette_explor_css", "rainette")()
}

chdrainette_parse_query <- function(query_string = "") {
  if (is.null(query_string) || !nzchar(query_string)) {
    return(list())
  }
  query_string <- sub("^\\?", "", query_string)
  shiny::parseQueryString(query_string)
}

chdrainette_storage_root <- function() {
  root <- Sys.getenv(
    "CHDRAINETTE_APP_DATA_DIR",
    unset = Sys.getenv("APP_DATA_DIR", unset = tempdir())
  )
  if (!nzchar(root)) {
    root <- tempdir()
  }
  dir.create(root, recursive = TRUE, showWarnings = FALSE)
  normalizePath(root, winslash = "/", mustWork = FALSE)
}

chdrainette_jobs_root <- function() {
  root <- file.path(chdrainette_storage_root(), "jobs")
  dir.create(root, recursive = TRUE, showWarnings = FALSE)
  normalizePath(root, winslash = "/", mustWork = FALSE)
}

chdrainette_new_job_dir <- function(session_token = "session") {
  timestamp <- format(Sys.time(), "%Y%m%d-%H%M%S")
  safe_token <- gsub("[^A-Za-z0-9_-]+", "-", session_token)
  base_dir <- file.path(
    chdrainette_jobs_root(),
    paste0("chdrainette_", safe_token, "_", timestamp)
  )
  dir.create(base_dir, recursive = TRUE, showWarnings = FALSE)
  normalizePath(base_dir, winslash = "/", mustWork = FALSE)
}

chdrainette_bundle_relative_path <- function(bundle_file) {
  if (is.null(bundle_file) || !nzchar(bundle_file) || !file.exists(bundle_file)) {
    return(NULL)
  }

  bundle_path <- normalizePath(bundle_file, winslash = "/", mustWork = FALSE)
  storage_root <- chdrainette_storage_root()
  storage_prefix <- paste0(storage_root, "/")

  if (!startsWith(bundle_path, storage_prefix)) {
    return(NULL)
  }

  substring(bundle_path, nchar(storage_prefix) + 1L)
}

chdrainette_resolve_bundle_path <- function(relative_path) {
  if (is.null(relative_path) || !nzchar(relative_path)) {
    return(NULL)
  }

  storage_root <- chdrainette_storage_root()
  candidate <- normalizePath(
    file.path(storage_root, relative_path),
    winslash = "/",
    mustWork = FALSE
  )
  storage_prefix <- paste0(storage_root, "/")

  if (!(identical(candidate, storage_root) || startsWith(candidate, storage_prefix))) {
    return(NULL)
  }
  if (!file.exists(candidate)) {
    return(NULL)
  }

  candidate
}

chdrainette_rainette_explor_url <- function(bundle_file) {
  relative_path <- chdrainette_bundle_relative_path(bundle_file)
  if (is.null(relative_path) || !nzchar(relative_path)) {
    return(NULL)
  }
  paste0(
    "?view=rainette_explor&bundle=",
    utils::URLencode(relative_path, reserved = TRUE)
  )
}

chdrainette_is_rainette_explor_request <- function(request) {
  query <- chdrainette_parse_query(request$QUERY_STRING %||% "")
  identical(query$view, "rainette_explor")
}

chdrainette_bundle_from_query <- function(query) {
  bundle_rel <- query$bundle %||% ""
  if (!nzchar(bundle_rel)) {
    return(NULL)
  }

  bundle_path <- chdrainette_resolve_bundle_path(bundle_rel)
  if (is.null(bundle_path)) {
    return(NULL)
  }

  bundle <- tryCatch(readRDS(bundle_path), error = function(e) NULL)
  if (is.null(bundle)) {
    return(NULL)
  }

  # rainette conserve les arguments dans `res$call`. Quand l'analyse a ete
  # lancee avec `params$min_segment_size`, cet element est une expression R.
  # docs_sample_ui() le compare directement a 1 et provoque alors :
  # "comparison (>) is not possible for language types".
  if (!is.null(bundle$res)) {
    fallback <- bundle$params$min_segment_size %||% 0L
    bundle$res <- chdrainette_normaliser_appel_rainette(
      bundle$res,
      min_segment_size = fallback
    )
  }

  bundle
}

chdrainette_rainette_explor_ui <- function(request) {
  query <- chdrainette_parse_query(request$QUERY_STRING %||% "")
  bundle <- chdrainette_bundle_from_query(query)

  if (is.null(bundle) || is.null(bundle$res) || is.null(bundle$dtm)) {
    return(
      miniUI::miniPage(
        shiny::tags$head(
          shiny::tags$style(shiny::HTML(rainette_explor_native_css()))
        ),
        shiny::div(
          style = "padding: 2rem; max-width: 60rem; margin: 0 auto;",
          shiny::h2("Rainette explor"),
          shiny::p("Le bundle d'analyse est introuvable ou invalide."),
          shiny::p("Relance une analyse CHD puis rouvre cet explorateur.")
        )
      )
    )
  }

  max_n_groups <- max(bundle$res$group, na.rm = TRUE)
  if (!is.finite(max_n_groups) || is.na(max_n_groups) || max_n_groups < 2) {
    max_n_groups <- 2L
  }

  miniUI::miniPage(
    title = "Rainette explor",
    shiny::tags$head(
      shiny::tags$style(shiny::HTML(rainette_explor_native_css())),
      shiny::tags$style(shiny::HTML("
        html, body {
          height: 100%;
          margin: 0;
          background: #ffffff;
        }
        body > .container-fluid {
          height: 100vh;
          padding: 0;
        }
        #main {
          min-height: 100%;
        }
      "))
    ),
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
                  "k",
                  label = "Number of clusters",
                  value = max_n_groups,
                  min = 2,
                  max = max_n_groups,
                  step = 1
                ),
                shiny::selectInput(
                  "measure",
                  "Statistics",
                  choices = c(
                    "Keyness - Chi-squared" = "chi2",
                    "Keyness - Likelihood ratio" = "lr",
                    "Frequency - Terms" = "frequency",
                    "Frequency - Documents proportion" = "docprop"
                  )
                ),
                shiny::numericInput(
                  "n_terms",
                  label = "Number of terms to display",
                  value = 20,
                  min = 5,
                  max = 30,
                  step = 1
                ),
                shiny::conditionalPanel(
                  "input.measure != 'docprop'",
                  shiny::checkboxInput(
                    "same_scales",
                    label = "Force same scales",
                    value = TRUE
                  )
                ),
                shiny::checkboxInput(
                  "show_negative",
                  label = "Show negative values",
                  value = FALSE
                ),
                shiny::sliderInput(
                  "text_size",
                  label = "Text size",
                  value = 8,
                  min = 6,
                  max = 20,
                  step = 1
                ),
                shiny::actionButton(
                  "get_r_code",
                  class = "btn-success",
                  icon = shiny::icon("code"),
                  label = gettext("Get R code")
                )
              )
            ),
            shiny::fillCol(
              id = "main",
              shiny::plotOutput("rainette_plot", height = "100%")
            )
          )
        )
      ),
      miniUI::miniTabPanel(
        "Cluster documents",
        icon = shiny::icon("file-alt"),
        miniUI::miniContentPanel(
          getFromNamespace("docs_sample_ui", "rainette")("rainette1", bundle$res)
        )
      )
    )
  )
}

run_rainette_explor_page_server <- function(input, output, session) {
  query_string <- ""
  if (!is.null(session$request) && !is.null(session$request$QUERY_STRING)) {
    query_string <- session$request$QUERY_STRING
  } else {
    query_string <- isolate(session$clientData$url_search %||% "")
  }

  query <- chdrainette_parse_query(query_string)
  if (!identical(query$view, "rainette_explor")) {
    return(invisible(NULL))
  }

  bundle <- chdrainette_bundle_from_query(query)
  if (is.null(bundle) || is.null(bundle$res) || is.null(bundle$dtm)) {
    return(invisible(NULL))
  }

  res <- bundle$res
  dtm <- bundle$dtm
  corpus_src <- bundle$corpus %||% NULL

  plot_code <- shiny::reactive({
    paste0(
      "rainette_plot(\n",
      "  bundle$res, bundle$dtm, k = ", input$k, ",\n",
      "  n_terms = ", input$n_terms, ",\n",
      "  free_scales = ", !isTRUE(input$same_scales), ",\n",
      "  measure = \"", input$measure, "\"",
      ",\n  show_negative = ", isTRUE(input$show_negative),
      if (input$text_size != 10) paste0(",\n  text_size = ", input$text_size) else "",
      "\n)"
    )
  })

  cutree_code <- shiny::reactive({
    paste0("cutree_rainette(bundle$res, k = ", input$k, ")")
  })

  generate_code <- shiny::reactive({
    code <- "## Clustering description plot\n"
    code <- paste0(code, plot_code())
    code <- paste0(code, "\n## Groups\n")
    code <- paste0(code, cutree_code())
    code
  })

  output$rainette_plot <- shiny::renderPlot({
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
  })

  shiny::observeEvent(input$get_r_code, {
    code <- generate_code()
    shiny::showModal(
      shiny::modalDialog(
        title = gettext("Export R code"),
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

  current_k <- shiny::reactive(input$k)
  getFromNamespace("docs_sample_server", "rainette")(
    "rainette1",
    res,
    corpus_src,
    current_k
  )
}
