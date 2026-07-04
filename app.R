library(bslib)
library(dplyr)
library(htmltools)
library(igraph)
library(quanteda)
library(quanteda.textstats)
library(rainette)
library(shiny)
library(wordcloud)
library(RColorBrewer)

options(
  shiny.maxRequestSize = 300 * 1024^2,
  bspm.sudo = TRUE,
  stringsAsFactors = FALSE
)

`%||%` <- function(left, right) {
  if (is.null(left) || !length(left)) {
    return(right)
  }
  left
}

source("nettoyage.R", encoding = "UTF-8", local = TRUE)
source("concordancier.R", encoding = "UTF-8", local = TRUE)
source("afc.R", encoding = "UTF-8", local = TRUE)
source("R/rainette_explorer_module.R", encoding = "UTF-8", local = TRUE)
source("ui.R", encoding = "UTF-8", local = TRUE)

source("R/utils_general.R", encoding = "UTF-8", local = TRUE)
source("R/utils_logging.R", encoding = "UTF-8", local = TRUE)
source("R/utils_text.R", encoding = "UTF-8", local = TRUE)
source("R/segmentation_helpers.R", encoding = "UTF-8", local = TRUE)
source("R/afc_helpers.R", encoding = "UTF-8", local = TRUE)
source("R/chd_afc_pipeline.R", encoding = "UTF-8", local = TRUE)
source("R/nlp_language.R", encoding = "UTF-8", local = TRUE)
source("R/server_outputs_status.R", encoding = "UTF-8", local = TRUE)
source("R/server_events_lancer.R", encoding = "UTF-8", local = TRUE)

render_markdown_or_message <- function(path, fallback) {
  if (file.exists(path)) {
    return(includeMarkdown(path))
  }
  tags$p(fallback)
}

ensure_exports_resource_path <- function(rv) {
  if (is.null(rv$export_dir) || !nzchar(rv$export_dir)) {
    return(FALSE)
  }
  if (is.null(rv$exports_prefix) || !nzchar(rv$exports_prefix)) {
    return(FALSE)
  }
  if (!(rv$exports_prefix %in% names(shiny::resourcePaths()))) {
    shiny::addResourcePath(rv$exports_prefix, rv$export_dir)
  }
  TRUE
}

server <- function(input, output, session) {
  rv <- reactiveValues(
    logs = "[info] Prêt.",
    statut = "En attente.",
    progression = 0,
    base_dir = NULL,
    export_dir = NULL,
    segments_file = NULL,
    stats_file = NULL,
    html_file = NULL,
    zip_file = NULL,
    res = NULL,
    res_chd = NULL,
    dfm_chd = NULL,
    dfm = NULL,
    filtered_corpus = NULL,
    res_stats_df = NULL,
    clusters = NULL,
    max_n_groups = NULL,
    max_n_groups_chd = NULL,
    res_type = "simple",
    exports_prefix = paste0("exports_", session$token),
    textes_indexation = NULL,
    afc_obj = NULL,
    afc_erreur = NULL,
    afc_vars_obj = NULL,
    afc_vars_erreur = NULL,
    afc_dir = NULL,
    afc_table_mots = NULL,
    afc_table_vars = NULL,
    afc_plot_classes = NULL,
    afc_plot_termes = NULL,
    afc_plot_vars = NULL,
    explor_assets = NULL,
    corpus_importe = NULL,
    corpus_segmente = NULL,
    corpus_preview_text = "",
    rainette_min_segment_size = NULL,
    explorer_corpus = NULL
  )

  rainette_explorer_module_server(
    "explorer_tab",
    res_type = reactive(rv$res_type),
    plot_res = reactive(rv$res_chd),
    cutree_res = reactive(rv$res),
    plot_dtm = reactive(rv$dfm_chd),
    explorer_dtm = reactive(rv$dfm),
    corpus_src = reactive(rv$explorer_corpus),
    max_k_plot = reactive(rv$max_n_groups_chd),
    max_k_double = reactive(rv$max_n_groups),
    min_segment_size_value = reactive(rv$rainette_min_segment_size)
  )

  register_outputs_status(input, output, session, rv)

  observeEvent(input$fichier_corpus, {
    req(input$fichier_corpus$datapath)
    if (!file.exists(input$fichier_corpus$datapath)) {
      return(invisible(NULL))
    }
    lines <- tryCatch(
      readLines(input$fichier_corpus$datapath, warn = FALSE, encoding = "UTF-8"),
      error = function(e) character(0)
    )
    rv$corpus_preview_text <- paste(utils::head(lines, 400), collapse = "\n")
  }, ignoreNULL = TRUE)

  output$corpus_meta <- renderUI({
    req(input$fichier_corpus)
    size_kb <- round(as.numeric(input$fichier_corpus$size %||% 0) / 1024, 1)
    docs_detected <- 0L
    if (nzchar(rv$corpus_preview_text)) {
      docs_detected <- sum(grepl("^\\*\\*\\*\\*", strsplit(rv$corpus_preview_text, "\n", fixed = TRUE)[[1]]))
    }
    tagList(
      tags$p(tags$strong("Fichier : "), input$fichier_corpus$name),
      tags$p(tags$strong("Taille : "), paste0(size_kb, " Ko")),
      tags$p(tags$strong("Documents détectés dans l'aperçu : "), docs_detected)
    )
  })

  output$corpus_preview <- renderText({
    if (!nzchar(rv$corpus_preview_text)) {
      return("Importe un fichier texte pour afficher ici l’aperçu du corpus.")
    }
    rv$corpus_preview_text
  })

  output$help_main <- renderUI({
    render_markdown_or_message("help/help.md", "Le fichier help/help.md est introuvable.")
  })

  output$metric_docs <- renderText({
    if (is.null(rv$filtered_corpus)) return("—")
    quanteda::ndoc(rv$corpus_importe %||% rv$filtered_corpus)
  })

  output$metric_segments <- renderText({
    if (is.null(rv$corpus_segmente)) return("—")
    quanteda::ndoc(rv$corpus_segmente)
  })

  output$metric_analyzed <- renderText({
    if (is.null(rv$filtered_corpus)) return("—")
    quanteda::ndoc(rv$filtered_corpus)
  })

  output$metric_classes <- renderText({
    if (is.null(rv$clusters)) return("—")
    length(rv$clusters)
  })

  output$ui_langue_detection <- renderUI({
    if (is.null(rv$filtered_corpus) && !nzchar(rv$corpus_preview_text)) {
      return(tags$p("Détection langue : importe et lance une analyse pour afficher une estimation."))
    }

    textes <- if (!is.null(rv$filtered_corpus)) {
      as.character(rv$filtered_corpus)
    } else {
      strsplit(rv$corpus_preview_text, "\n", fixed = TRUE)[[1]]
    }

    est <- estimer_langue_corpus(textes, rv = rv)
    if (is.na(est$code)) {
      return(tags$p("Détection langue : estimation indisponible."))
    }

    cfg_est <- configurer_langue_corpus(est$code)
    cfg_sel <- configurer_langue_corpus(input$langue_corpus)

    msg <- paste0(
      "Langue estimée du corpus : ", cfg_est$libelle,
      " (scores stopwords FR=", sprintf("%.3f", est$scores[["fr"]]),
      ", EN=", sprintf("%.3f", est$scores[["en"]]),
      ", ES=", sprintf("%.3f", est$scores[["es"]]), ")."
    )

    if (!identical(cfg_est$code, cfg_sel$code)) {
      return(tags$div(class = "alert alert-warning", tags$p(style = "margin:0;", paste0(msg, " Langue sélectionnée : ", cfg_sel$libelle, "."))))
    }

    tags$div(class = "alert alert-success", tags$p(style = "margin:0;", paste0(msg, " Langue sélectionnée : ", cfg_sel$libelle, ".")))
  })

  output$ui_chd_statut <- renderUI({
    if (is.null(rv$res)) {
      return(tags$p("CHD non disponible. Lance une analyse."))
    }
    if (identical(rv$res_type, "double")) {
      return(tags$p("CHD disponible (classification double rainette2)."))
    }
    nb_classes <- if (!is.null(rv$clusters)) length(rv$clusters) else NA_integer_
    tags$p(paste0("CHD disponible (classification simple rainette) - classes détectées : ", nb_classes, "."))
  })

  output$ui_afc_statut <- renderUI({
    if (!is.null(rv$afc_erreur) && nzchar(rv$afc_erreur)) {
      return(
        tags$div(
          class = "alert alert-warning",
          tags$p(style = "margin:0;", "AFC calculée partiellement : la projection principale a rencontré une erreur.")
        )
      )
    }
    if (is.null(rv$afc_obj) || is.null(rv$afc_obj$ca)) {
      return(tags$p("AFC non disponible. Lance une analyse pour calculer les projections factorielles."))
    }

    eig1 <- tryCatch(round(as.numeric(rv$afc_obj$ca$eig[1, 2]), 2), error = function(e) NA_real_)
    parts <- c("AFC des classes et des termes disponible.")
    if (!is.na(eig1)) {
      parts <- c(parts, paste0("Inertie de l'axe 1 : ", eig1, " %."))
    }
    if (!is.null(rv$afc_vars_obj) && is.null(rv$afc_vars_erreur)) {
      parts <- c(parts, "AFC des variables étoilées disponible.")
    }

    tags$div(
      class = "alert alert-success",
      tags$p(style = "margin:0;", paste(parts, collapse = " "))
    )
  })

  output$ui_afc_erreurs <- renderUI({
    messages <- Filter(
      nzchar,
      c(
        if (!is.null(rv$afc_erreur)) paste0("AFC classes / termes : ", rv$afc_erreur),
        if (!is.null(rv$afc_vars_erreur)) paste0("AFC variables étoilées : ", rv$afc_vars_erreur)
      )
    )

    if (!length(messages)) {
      return(NULL)
    }

    tags$div(
      class = "alert alert-warning",
      tags$strong("Détails AFC"),
      tags$ul(class = "mb-0", lapply(messages, tags$li))
    )
  })

  output$ui_exports_status <- renderUI({
    lignes <- list(
      list(label = "Export global ZIP", ok = !is.null(rv$zip_file) && file.exists(rv$zip_file)),
      list(label = "Segments par classe", ok = !is.null(rv$segments_file) && file.exists(rv$segments_file)),
      list(label = "Statistiques CSV", ok = !is.null(rv$stats_file) && file.exists(rv$stats_file)),
      list(label = "Concordancier HTML", ok = !is.null(rv$html_file) && file.exists(rv$html_file)),
      list(label = "Dossier AFC", ok = !is.null(rv$afc_dir) && dir.exists(rv$afc_dir)),
      list(label = "CHD PNG", ok = !is.null(rv$export_dir) && file.exists(file.path(rv$export_dir, "explor", "chd.png")))
    )

    tags$ul(
      class = "mb-0",
      lapply(lignes, function(item) {
        couleur <- if (isTRUE(item$ok)) "#2f855a" else "#b7791f"
        statut <- if (isTRUE(item$ok)) "disponible" else "en attente"
        tags$li(
          tags$strong(item$label),
          HTML(" : "),
          tags$span(style = paste0("color:", couleur, "; font-weight:600;"), statut)
        )
      })
    )
  })

  output$ui_exports_links <- renderUI({
    tagList(
      tags$p("Les exports apparaissent ici dès qu'une analyse est terminée."),
      div(
        class = "d-grid gap-2",
        downloadButton("dl_zip_tab", "Télécharger export global (zip)"),
        downloadButton("dl_afc_zip_tab", "Télécharger AFC (zip)"),
        downloadButton("dl_segments_tab", "Télécharger segments"),
        downloadButton("dl_stats_tab", "Télécharger statistiques"),
        downloadButton("dl_html_tab", "Télécharger concordancier HTML")
      ),
      tags$hr(),
      tags$ul(
        class = "mb-0",
        tags$li(
          tags$strong("ZIP global : "),
          tags$code(if (!is.null(rv$zip_file)) basename(rv$zip_file) else "non généré")
        ),
        tags$li(
          tags$strong("Segments : "),
          tags$code(if (!is.null(rv$segments_file)) basename(rv$segments_file) else "non généré")
        ),
        tags$li(
          tags$strong("Statistiques : "),
          tags$code(if (!is.null(rv$stats_file)) basename(rv$stats_file) else "non généré")
        ),
        tags$li(
          tags$strong("Concordancier HTML : "),
          tags$code(if (!is.null(rv$html_file)) basename(rv$html_file) else "non généré")
        ),
        tags$li(
          tags$strong("Dossier AFC : "),
          tags$code(if (!is.null(rv$afc_dir)) basename(rv$afc_dir) else "non généré")
        )
      )
    )
  })

  register_events_lancer(input, output, session, rv)

  observeEvent(input$explor, {
    try(updateTabsetPanel(session, "onglets_principaux", selected = "CHD"), silent = TRUE)
  })

  output$plot_afc_classes <- renderPlot({
    if (!is.null(rv$afc_erreur) && nzchar(rv$afc_erreur)) {
      plot.new()
      text(0.5, 0.5, "AFC indisponible (erreur).", cex = 1.1)
      return(invisible(NULL))
    }
    if (is.null(rv$afc_obj) || is.null(rv$afc_obj$ca)) {
      plot.new()
      text(0.5, 0.5, "AFC non disponible. Lance une analyse.", cex = 1.1)
      return(invisible(NULL))
    }
    tracer_afc_classes_seules(rv$afc_obj, axes = c(1, 2), cex_labels = 1.05)
  })

  output$plot_afc <- renderPlot({
    if (!is.null(rv$afc_erreur) && nzchar(rv$afc_erreur)) {
      plot.new()
      text(0.5, 0.5, "AFC indisponible (erreur).", cex = 1.1)
      return(invisible(NULL))
    }
    if (is.null(rv$afc_obj) || is.null(rv$afc_obj$ca)) {
      plot.new()
      text(0.5, 0.5, "AFC non disponible. Lance une analyse.", cex = 1.1)
      return(invisible(NULL))
    }

    activer_repel <- isTRUE(input$afc_reduire_chevauchement)
    taille_sel <- as.character(input$afc_taille_mots %||% "frequency")
    if (!taille_sel %in% c("frequency", "chi2")) {
      taille_sel <- "frequency"
    }
    top_termes <- as.integer(input$afc_top_termes %||% 120)
    tracer_afc_classes_termes(rv$afc_obj, axes = c(1, 2), top_termes = top_termes, taille_sel = taille_sel, activer_repel = activer_repel)
  })

  output$ui_table_afc_mots_par_classe <- renderUI({
    if (is.null(rv$afc_table_mots)) {
      output$table_afc_mots_message <- renderTable({
        data.frame(Message = "AFC mots : non disponible.", stringsAsFactors = FALSE)
      }, rownames = FALSE)
      return(tableOutput("table_afc_mots_message"))
    }

    df <- rv$afc_table_mots
    colonnes <- intersect(c("Terme", "Classe_max", "frequency", "chi2", "p_value", "Segment_texte"), names(df))
    df <- df[, colonnes, drop = FALSE]
    if ("p_value" %in% names(df)) {
      df$p_value <- ifelse(is.na(df$p_value), NA_character_, formatC(df$p_value, format = "f", digits = 6))
    }

    classes <- unique(as.character(df$Classe_max))
    classes <- sort(classes[!is.na(classes) & nzchar(classes)])
    if (!length(classes)) {
      output$table_afc_mots_message <- renderTable({
        data.frame(Message = "AFC mots : aucune classe disponible.", stringsAsFactors = FALSE)
      }, rownames = FALSE)
      return(tableOutput("table_afc_mots_message"))
    }

    do.call(tagList, lapply(seq_along(classes), function(i) {
      cl <- classes[[i]]
      id <- paste0("table_afc_mots_", i)

      output[[id]] <- renderUI({
        sous_df <- df[df$Classe_max == cl, , drop = FALSE]
        colonnes_locales <- intersect(c("Terme", "frequency", "chi2", "p_value", "Segment_texte"), names(sous_df))
        sous_df <- sous_df[, colonnes_locales, drop = FALSE]
        if ("p_value" %in% names(sous_df)) {
          sous_df$p_value <- ifelse(is.na(sous_df$p_value), NA_character_, formatC(sous_df$p_value, format = "f", digits = 6))
        }
        if ("chi2" %in% names(sous_df)) {
          sous_df <- sous_df[order(-sous_df$chi2), , drop = FALSE]
          sous_df$chi2 <- ifelse(is.na(sous_df$chi2), NA_character_, formatC(sous_df$chi2, format = "f", digits = 6))
        }
        sous_df <- head(sous_df, 100)
        generer_table_html_afc_mots(sous_df)
      })

      card(card_header(cl), uiOutput(id))
    }))
  })

  output$plot_afc_vars <- renderPlot({
    if (!is.null(rv$afc_vars_erreur) && nzchar(rv$afc_vars_erreur)) {
      plot.new()
      text(0.5, 0.5, "AFC variables étoilées indisponible (erreur).", cex = 1.1)
      return(invisible(NULL))
    }
    if (is.null(rv$afc_vars_obj) || is.null(rv$afc_vars_obj$ca)) {
      plot.new()
      text(0.5, 0.5, "AFC variables étoilées non disponible. Lance une analyse.", cex = 1.1)
      return(invisible(NULL))
    }
    activer_repel <- isTRUE(input$afc_reduire_chevauchement)
    top_mod <- as.integer(input$afc_top_modalites %||% 120)
    tracer_afc_variables_etoilees(rv$afc_vars_obj, axes = c(1, 2), top_modalites = top_mod, activer_repel = activer_repel)
  })

  output$table_afc_vars <- renderTable({
    if (is.null(rv$afc_table_vars)) {
      return(data.frame(Message = "AFC variables étoilées : non disponible.", stringsAsFactors = FALSE))
    }
    df <- rv$afc_table_vars
    colonnes <- intersect(c("Modalite", "Classe_max", "frequency", "chi2", "p_value"), names(df))
    df <- df[, colonnes, drop = FALSE]
    if ("p_value" %in% names(df)) {
      p_values <- df$p_value
      df$p_value <- ifelse(is.na(p_values), NA_character_, ifelse(p_values > 0.05, sprintf("<span style='color:#d97706;font-weight:600;'>%s</span>", formatC(p_values, format = "f", digits = 6)), formatC(p_values, format = "f", digits = 6)))
    }
    if ("chi2" %in% names(df)) {
      df <- df[order(-df$chi2), , drop = FALSE]
      df$chi2 <- ifelse(is.na(df$chi2), NA_character_, formatC(df$chi2, format = "f", digits = 6))
    }
    head(df, 200)
  }, rownames = FALSE, sanitize.text.function = function(x) x)

  output$table_afc_eig <- renderTable({
    if (!is.null(rv$afc_erreur) && nzchar(rv$afc_erreur)) {
      return(data.frame(Message = "AFC indisponible (erreur).", stringsAsFactors = FALSE))
    }
    if (is.null(rv$afc_obj) || is.null(rv$afc_obj$ca) || is.null(rv$afc_obj$ca$eig)) {
      return(data.frame(Message = "Valeurs propres indisponibles.", stringsAsFactors = FALSE))
    }
    df <- as.data.frame(rv$afc_obj$ca$eig)
    df$Dim <- rownames(df)
    rownames(df) <- NULL
    df <- df[, c("Dim", names(df)[1], names(df)[2], names(df)[3]), drop = FALSE]
    names(df) <- c("Dim", "Valeur_propre", "Pourcentage_inertie", "Pourcentage_cumule")
    df
  }, rownames = FALSE)

  output$dl_segments <- downloadHandler(
    filename = function() "segments_par_classe.txt",
    content = function(file) {
      req(rv$segments_file)
      file.copy(rv$segments_file, file, overwrite = TRUE)
    }
  )

  output$dl_stats <- downloadHandler(
    filename = function() "stats_par_classe.csv",
    content = function(file) {
      req(rv$stats_file)
      file.copy(rv$stats_file, file, overwrite = TRUE)
    }
  )

  output$dl_html <- downloadHandler(
    filename = function() "segments_par_classe.html",
    content = function(file) {
      req(rv$html_file)
      file.copy(rv$html_file, file, overwrite = TRUE)
    }
  )

  output$dl_zip <- downloadHandler(
    filename = function() "exports_rainette.zip",
    content = function(file) {
      req(rv$zip_file)
      file.copy(rv$zip_file, file, overwrite = TRUE)
    }
  )

  output$dl_afc_zip <- downloadHandler(
    filename = function() "afc_exports.zip",
    content = function(file) {
      req(rv$afc_dir)
      zip_tmp <- tempfile(fileext = ".zip")
      ancien <- getwd()
      on.exit(setwd(ancien), add = TRUE)
      setwd(dirname(rv$afc_dir))
      if (file.exists(zip_tmp)) unlink(zip_tmp)
      utils::zip(zipfile = zip_tmp, files = basename(rv$afc_dir))
      file.copy(zip_tmp, file, overwrite = TRUE)
    }
  )

  output$dl_segments_tab <- downloadHandler(
    filename = function() "segments_par_classe.txt",
    content = function(file) {
      req(rv$segments_file)
      file.copy(rv$segments_file, file, overwrite = TRUE)
    }
  )

  output$dl_stats_tab <- downloadHandler(
    filename = function() "stats_par_classe.csv",
    content = function(file) {
      req(rv$stats_file)
      file.copy(rv$stats_file, file, overwrite = TRUE)
    }
  )

  output$dl_html_tab <- downloadHandler(
    filename = function() "segments_par_classe.html",
    content = function(file) {
      req(rv$html_file)
      file.copy(rv$html_file, file, overwrite = TRUE)
    }
  )

  output$dl_zip_tab <- downloadHandler(
    filename = function() "exports_rainette.zip",
    content = function(file) {
      req(rv$zip_file)
      file.copy(rv$zip_file, file, overwrite = TRUE)
    }
  )

  output$dl_afc_zip_tab <- downloadHandler(
    filename = function() "afc_exports.zip",
    content = function(file) {
      req(rv$afc_dir)
      zip_tmp <- tempfile(fileext = ".zip")
      ancien <- getwd()
      on.exit(setwd(ancien), add = TRUE)
      setwd(dirname(rv$afc_dir))
      if (file.exists(zip_tmp)) unlink(zip_tmp)
      utils::zip(zipfile = zip_tmp, files = basename(rv$afc_dir))
      file.copy(zip_tmp, file, overwrite = TRUE)
    }
  )
}

shinyApp(ui = ui, server = server)
