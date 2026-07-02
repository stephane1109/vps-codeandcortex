# Module server - événement principal `input$lancer`
# Ce fichier encapsule le pipeline principal lancé au clic sur "Lancer l'analyse"
# (préparation, CHD/AFC/NER, exports) pour alléger `app.R` à comportement constant.

register_events_lancer <- function(input, output, session, rv) {
    formater_df_csv_6_decimales <- function(df) {
      if (is.null(df)) return(df)
      df_out <- df
      for (nm in names(df_out)) {
        col <- df_out[[nm]]
        if (is.numeric(col)) {
          df_out[[nm]] <- ifelse(
            is.na(col),
            NA_character_,
            formatC(col, format = "f", digits = 6)
          )
        }
      }
      df_out
    }

    ecrire_csv_6_decimales <- function(df, chemin, row.names = FALSE) {
      write.csv(formater_df_csv_6_decimales(df), chemin, row.names = row.names)
    }

    observeEvent(input$lancer, {
      rv$logs <- ""
      rv$statut <- "Vérification du fichier..."
      rv$progression <- 0

      rv$spacy_tokens_df <- NULL
      rv$textes_indexation <- NULL
      rv$ner_df <- NULL
      rv$ner_nb_segments <- NA_integer_
      rv$afc_obj <- NULL
      rv$afc_erreur <- NULL
      rv$afc_vars_obj <- NULL
      rv$afc_vars_erreur <- NULL

      rv$afc_dir <- NULL
      rv$afc_table_mots <- NULL
      rv$afc_table_vars <- NULL
      rv$afc_plot_classes <- NULL
      rv$afc_plot_termes <- NULL
      rv$afc_plot_vars <- NULL

      rv$segments_file <- NULL
      rv$stats_file <- NULL
      rv$html_file <- NULL
      rv$ner_file <- NULL
      rv$zip_file <- NULL

      rv$res <- NULL
      rv$res_chd <- NULL
      rv$dfm_chd <- NULL
      rv$res_type <- "simple"
      rv$max_n_groups <- NULL
      rv$max_n_groups_chd <- NULL
      rv$explor_assets <- NULL

      ajouter_log(rv, "Clic sur 'Lancer l'analyse' reçu.")

      if (is.null(input$fichier_corpus) || is.null(input$fichier_corpus$datapath) || !file.exists(input$fichier_corpus$datapath)) {
        rv$statut <- "Aucun fichier uploadé."
        rv$progression <- 0
        ajouter_log(rv, "Aucun fichier uploadé côté serveur. Sélectionne un .txt puis relance.")
        showNotification("Aucun fichier uploadé. Choisis un .txt.", type = "error", duration = 6)
        return(invisible(NULL))
      }

      withProgress(message = "Analyse Rainette en cours", value = 0, {

        p <- Progress$new(session, min = 0, max = 1)
        on.exit(try(p$close(), silent = TRUE), add = TRUE)

        avancer <- function(valeur, detail) {
          valeur <- max(0, min(1, valeur))
          p$set(value = valeur, message = "Analyse Rainette en cours", detail = detail)
          rv$progression <- round(valeur * 100)
        }

        tryCatch({

          avancer(0.02, "Préparation des répertoires")
          rv$statut <- "Préparation des répertoires..."

          rv$base_dir <- file.path(tempdir(), paste0("rainette_", session$token))
          rv$export_dir <- file.path(rv$base_dir, "exports")
          dir.create(rv$export_dir, showWarnings = FALSE, recursive = TRUE)
          ajouter_log(rv, paste0("export_dir = ", rv$export_dir))

          avancer(0.08, "Import du corpus")
          rv$statut <- "Import du corpus..."
          chemin_fichier <- input$fichier_corpus$datapath
          md5 <- md5_fichier(chemin_fichier)
          ajouter_log(rv, paste0("MD5 fichier = ", md5))

          corpus <- import_corpus_iramuteq(chemin_fichier)
          ajouter_log(rv, paste0("Nombre de documents importés : ", ndoc(corpus)))

          avancer(0.14, "Segmentation")
          rv$statut <- "Segmentation..."
          segment_size <- input$segment_size
          corpus <- split_segments(corpus, segment_size = segment_size)
          ajouter_log(rv, paste0("Nombre de segments après découpage : ", ndoc(corpus)))

          ids_corpus <- docnames(corpus)
          textes_orig <- as.character(corpus)

          avancer(0.18, "Préparation texte (nettoyage / minuscules)")
          rv$statut <- "Préparation texte..."

          textes_chd <- appliquer_nettoyage_et_minuscules(
            textes = textes_orig,
            activer_nettoyage = isTRUE(input$nettoyage_caracteres),
            forcer_minuscules = isTRUE(input$forcer_minuscules_avant),
            supprimer_chiffres = isTRUE(input$supprimer_chiffres),
            supprimer_apostrophes = isTRUE(input$supprimer_apostrophes)
          )
          names(textes_chd) <- ids_corpus

          verifier_coherence_dictionnaire_langue(textes_chd, input$spacy_langue, rv = rv)

          avancer(0.22, "Prétraitement + DFM")
          rv$statut <- "Prétraitement et DFM..."

          filtrage_morpho <- isTRUE(input$filtrage_morpho)
          utiliser_lemmes <- isTRUE(input$spacy_utiliser_lemmes)
          config_spacy <- configurer_langue_spacy(input$spacy_langue)
          utiliser_pipeline_spacy <- filtrage_morpho || utiliser_lemmes

          if (!utiliser_pipeline_spacy) {

            ajouter_log(rv, "Filtrage morphosyntaxique désactivé : pipeline standard.")
            tok_base <- tokens(
              textes_chd,
              remove_punct = isTRUE(input$supprimer_ponctuation),
              remove_numbers = isTRUE(input$supprimer_chiffres)
            )

            res_dfm <- construire_dfm_avec_fallback_stopwords(
              tok_base = tok_base,
              min_docfreq = input$min_docfreq,
              retirer_stopwords = isTRUE(input$retirer_stopwords),
              langue_spacy = input$spacy_langue,
              rv = rv,
              libelle = "Standard"
            )
            tok <- res_dfm$tok
            dfm_obj <- res_dfm$dfm

          } else {

            pos_a_conserver <- NULL
            if (isTRUE(filtrage_morpho)) {
              pos_a_conserver <- input$pos_spacy_a_conserver
              if (is.null(pos_a_conserver) || length(pos_a_conserver) == 0) pos_a_conserver <- c("NOUN", "ADJ")
            }

            ajouter_log(
              rv,
              paste0(
                "spaCy (", config_spacy$modele, ", ", config_spacy$libelle, ") | filtrage POS=", ifelse(filtrage_morpho, "1", "0"),
                ifelse(filtrage_morpho, paste0(" (", paste(pos_a_conserver, collapse = ", "), ")"), ""),
                " | lemmes=", ifelse(utiliser_lemmes, "1", "0"),
                " | stopwords: spaCy"
              )
            )

            avancer(0.28, "spaCy : exécution Python")
            rv$statut <- "spaCy : prétraitement..."

            sp <- executer_spacy_filtrage(
              ids = ids_corpus,
              textes = unname(textes_chd),
              pos_a_conserver = pos_a_conserver,
              utiliser_lemmes = utiliser_lemmes,
              lower_input = isTRUE(input$forcer_minuscules_avant),
              modele_spacy = config_spacy$modele,
              rv = rv
            )

            textes_spacy <- sp$textes
            names(textes_spacy) <- ids_corpus
            rv$spacy_tokens_df <- sp$tokens_df

            avancer(0.40, "spaCy : tokens + DFM")
            tok_base <- tokens(
              textes_spacy,
              remove_punct = isTRUE(input$supprimer_ponctuation),
              remove_numbers = isTRUE(input$supprimer_chiffres)
            )

            res_dfm <- construire_dfm_avec_fallback_stopwords(
              tok_base = tok_base,
              min_docfreq = input$min_docfreq,
              retirer_stopwords = isTRUE(input$retirer_stopwords),
              langue_spacy = input$spacy_langue,
              rv = rv,
              libelle = "spaCy"
            )
            tok <- res_dfm$tok
            dfm_obj <- res_dfm$dfm
          }

          included_segments <- docnames(dfm_obj)
          filtered_corpus <- corpus[included_segments]
          tok <- tok[included_segments]

          dfm_obj <- assurer_docvars_dfm_minimal(dfm_obj, filtered_corpus)

          tmp <- supprimer_docs_vides_dfm(dfm_obj, filtered_corpus, tok, rv)
          dfm_obj <- tmp$dfm
          filtered_corpus <- tmp$corpus
          tok <- tmp$tok

          ajouter_log(rv, paste0("Après suppression segments vides : ", ndoc(dfm_obj), " docs ; ", nfeat(dfm_obj), " termes."))
          verifier_dfm_avant_rainette(dfm_obj, input)

          rv$textes_indexation <- vapply(as.list(tok), function(x) paste(x, collapse = " "), FUN.VALUE = character(1))
          names(rv$textes_indexation) <- docnames(dfm_obj)

          avancer(0.52, "Classification (rainette / rainette2)")
          rv$statut <- "Classification en cours..."

          type_classif <- as.character(input$type_classification)
          if (!type_classif %in% c("simple", "double")) type_classif <- "simple"

          groupes <- NULL
          res_final <- NULL

          if (type_classif == "simple") {

            rv$res_type <- "simple"
            ajouter_log(rv, "Mode : classification simple (rainette).")

            k_effectif <- calculer_k_effectif(dfm_obj, input$k, input$min_split_members, rv)

            res <- rainette(
              dfm_obj,
              k = k_effectif,
              min_segment_size = input$min_segment_size,
              min_split_members = input$min_split_members,
              doc_id = "segment_source"
            )

            if (is.null(res) || is.null(res$group) || length(res$group) == 0) stop("Rainette n'a pas pu calculer de clusters. Diminue les filtrages, augmente segment_size, ou réduis k.")

            groupes <- res$group
            res_final <- res
            rv$res_chd <- res
            rv$dfm_chd <- dfm_obj
            rv$max_n_groups <- max(res$group, na.rm = TRUE)
            rv$max_n_groups_chd <- rv$max_n_groups

          } else {

            rv$res_type <- "double"
            ajouter_log(rv, "Mode : classification double (rainette2).")

            k_effectif <- calculer_k_effectif(dfm_obj, input$k, input$min_split_members, rv)

            res1 <- rainette(dfm_obj, k = k_effectif, min_segment_size = input$min_segment_size, min_split_members = input$min_split_members, doc_id = "segment_source")
            if (is.null(res1) || is.null(res1$group) || length(res1$group) == 0) stop("Classification 1 (rainette) impossible.")

            res2 <- rainette(dfm_obj, k = k_effectif, min_segment_size = input$min_segment_size2, min_split_members = input$min_split_members, doc_id = "segment_source")
            if (is.null(res2) || is.null(res2$group) || length(res2$group) == 0) stop("Classification 2 (rainette) impossible.")

            res_d <- rainette2(res1, res2, max_k = input$max_k_double)
            groupes <- cutree(res_d, k = k_effectif)

            res_final <- res_d
            rv$res_chd <- res1
            rv$dfm_chd <- dfm_obj
            rv$max_n_groups <- input$max_k_double
            rv$max_n_groups_chd <- max(res1$group, na.rm = TRUE)
          }

          docvars(filtered_corpus)$Classes <- groupes

          idx_ok <- !is.na(docvars(filtered_corpus)$Classes)
          filtered_corpus_ok <- filtered_corpus[idx_ok]
          dfm_ok <- dfm_obj[idx_ok, ]
          tok_ok <- tok[idx_ok]

          if (ndoc(dfm_ok) < 2) stop("Après classification, il reste moins de 2 segments classés (hors NA).")
          if (nfeat(dfm_ok) < 2) stop("Après classification, le DFM classé est trop pauvre (moins de 2 termes).")

          rv$clusters <- sort(unique(docvars(filtered_corpus_ok)$Classes))
          rv$res <- res_final
          rv$dfm <- dfm_ok
          rv$filtered_corpus <- filtered_corpus_ok
          rv$res_stats_df <- NULL

          avancer(0.58, "NER (si activé)")
          rv$statut <- "NER (si activé)..."

          if (isTRUE(input$activer_ner)) {
            config_spacy_ner <- configurer_langue_spacy(input$spacy_langue)
            ids_ner <- docnames(filtered_corpus_ok)
            textes_ner <- as.character(filtered_corpus_ok)
            rv$ner_nb_segments <- length(textes_ner)
            ajouter_log(rv, paste0("NER spaCy : modèle ", config_spacy_ner$modele, " (", config_spacy_ner$libelle, ")."))

            df_ent <- executer_spacy_ner(
              ids_ner,
              textes_ner,
              modele_spacy = config_spacy_ner$modele,
              rv = rv
            )

            classes_vec <- as.integer(docvars(filtered_corpus_ok)$Classes)
            names(classes_vec) <- ids_ner

            df_ent$Classe <- classes_vec[df_ent$doc_id]
            df_ent$Classe <- as.integer(df_ent$Classe)
            df_ent <- df_ent[!is.na(df_ent$Classe), , drop = FALSE]

            rv$ner_df <- df_ent
          }

          avancer(0.62, "Exports + stats")
          rv$statut <- "Exports et statistiques..."

          segments_vec <- as.character(filtered_corpus_ok)
          names(segments_vec) <- docnames(filtered_corpus_ok)
          segments_by_class <- split(segments_vec, docvars(filtered_corpus_ok)$Classes)

          segments_file <- file.path(rv$export_dir, "segments_par_classe.txt")
          writeLines(unlist(lapply(names(segments_by_class), function(cl) c(paste0("Classe ", cl, ":"), unname(segments_by_class[[cl]]), ""))), segments_file)

          res_stats_list <- rainette_stats(
            dtm = dfm_ok,
            groups = docvars(filtered_corpus_ok)$Classes,
            measure = c("chi2", "lr", "frequency", "docprop"),
            n_terms = 9999,
            show_negative = TRUE,
            max_p = input$max_p
          )

          res_stats_df <- bind_rows(res_stats_list, .id = "ClusterID") %>%
            rename(Terme = feature, Classe = ClusterID) %>%
            mutate(
              Classe = as.numeric(Classe),
              p_value_filter = ifelse(p <= input$max_p, paste0("≤ ", input$max_p), paste0("> ", input$max_p))
            ) %>%
            arrange(Classe, desc(chi2))

          stats_file <- file.path(rv$export_dir, "stats_par_classe.csv")
          ecrire_csv_6_decimales(res_stats_df, stats_file, row.names = FALSE)

          rv$segments_file <- segments_file
          rv$stats_file <- stats_file
          rv$res_stats_df <- res_stats_df

          avancer(0.72, "AFC (classes × termes)")
          rv$statut <- "Calcul AFC classes × termes..."

          rv$afc_obj <- NULL
          rv$afc_erreur <- NULL
          rv$afc_vars_obj <- NULL
          rv$afc_vars_erreur <- NULL
          rv$afc_dir <- file.path(rv$export_dir, "afc")
          dir.create(rv$afc_dir, showWarnings = FALSE, recursive = TRUE)

          termes_signif <- unique(subset(res_stats_df, p <= input$max_p)$Terme)
          termes_signif <- termes_signif[!is.na(termes_signif) & nzchar(termes_signif)]
          if (length(termes_signif) < 2) termes_signif <- NULL

          tryCatch({
            groupes_docs <- docvars(filtered_corpus_ok)$Classes

            obj <- executer_afc_classes(
              dfm_obj = dfm_ok,
              groupes = groupes_docs,
              termes_cibles = termes_signif,
              max_termes = 400,
              seuil_p = input$max_p,
              rv = rv
            )

            if (!is.null(obj$termes_stats) && !is.null(rv$res_stats_df)) {
              df_m <- obj$termes_stats
              df_m$Classe_num <- suppressWarnings(as.numeric(gsub("^Classe\\s+", "", as.character(df_m$Classe_max))))
              rs <- rv$res_stats_df

              rs2 <- rs[, intersect(c("Terme", "Classe", "chi2", "p", "frequency", "docprop", "lr"), names(rs)), drop = FALSE]
              rs2$Classe <- as.numeric(rs2$Classe)

              m <- merge(
                df_m,
                rs2,
                by.x = c("Terme", "Classe_num"),
                by.y = c("Terme", "Classe"),
                all.x = TRUE,
                suffixes = c("_global", "_rainette")
              )

              if ("chi2" %in% names(m)) {
                df_m$chi2 <- ifelse(is.na(m$chi2), df_m$chi2, m$chi2)
              }
              if ("p" %in% names(m)) {
                df_m$p_value <- ifelse(is.na(m$p), df_m$p_value, m$p)
              }

              df_m$Classe_num <- NULL
              obj$termes_stats <- df_m
            }

            obj$termes_stats <- construire_segments_exemples_afc(
              termes_stats = obj$termes_stats,
              dfm_obj = dfm_ok,
              corpus_obj = filtered_corpus_ok
            )

            rv$afc_obj <- obj
            ajouter_log(rv, "AFC classes × termes : calcul terminé.")

          }, error = function(e) {
            rv$afc_erreur <- paste0("AFC classes × termes : ", e$message)
            ajouter_log(rv, rv$afc_erreur)
            showNotification(rv$afc_erreur, type = "error", duration = 8)
          })

          avancer(0.74, "AFC (variables étoilées)")
          rv$statut <- "Calcul AFC variables étoilées..."

          tryCatch({
            if (!is.null(docvars(filtered_corpus_ok)$Classes)) {
              objv <- executer_afc_variables_etoilees(
                corpus_aligne = filtered_corpus_ok,
                groupes = docvars(filtered_corpus_ok)$Classes,
                max_modalites = 400,
                seuil_p = input$max_p,
                rv = rv
              )
              rv$afc_vars_obj <- objv
              ajouter_log(rv, "AFC variables étoilées : calcul terminé.")
            }
          }, error = function(e) {
            rv$afc_vars_erreur <- paste0("AFC variables étoilées : ", e$message)
            ajouter_log(rv, rv$afc_vars_erreur)
          })

          if (!is.null(rv$afc_obj) && !is.null(rv$afc_obj$ca)) {

            afc_classes_png <- file.path(rv$afc_dir, "afc_classes.png")
            afc_termes_png <- file.path(rv$afc_dir, "afc_termes.png")

            activer_repel <- TRUE
            if (!is.null(input$afc_reduire_chevauchement)) activer_repel <- isTRUE(input$afc_reduire_chevauchement)

            taille_sel <- "frequency"
            if (!is.null(input$afc_taille_mots) && nzchar(as.character(input$afc_taille_mots))) {
              taille_sel <- as.character(input$afc_taille_mots)
            }
            if (!taille_sel %in% c("frequency", "chi2")) taille_sel <- "frequency"

            top_termes <- 120
            if (!is.null(input$afc_top_termes) && is.finite(input$afc_top_termes)) top_termes <- as.integer(input$afc_top_termes)

            png(afc_classes_png, width = 1800, height = 1400, res = 180)
            try(tracer_afc_classes_seules(rv$afc_obj, axes = c(1, 2), cex_labels = 1.05), silent = TRUE)
            dev.off()

            png(afc_termes_png, width = 2000, height = 1600, res = 180)
            try(tracer_afc_classes_termes(rv$afc_obj, axes = c(1, 2), top_termes = top_termes, taille_sel = taille_sel, activer_repel = activer_repel), silent = TRUE)
            dev.off()

            rv$afc_plot_classes <- afc_classes_png
            rv$afc_plot_termes <- afc_termes_png

            ecrire_csv_6_decimales(rv$afc_obj$table, file.path(rv$afc_dir, "table_classes_termes.csv"), row.names = TRUE)
            ecrire_csv_6_decimales(rv$afc_obj$rowcoord, file.path(rv$afc_dir, "coords_classes.csv"), row.names = TRUE)
            ecrire_csv_6_decimales(rv$afc_obj$colcoord, file.path(rv$afc_dir, "coords_termes.csv"), row.names = TRUE)
            ecrire_csv_6_decimales(rv$afc_obj$termes_stats, file.path(rv$afc_dir, "stats_termes.csv"), row.names = FALSE)

            if (!is.null(rv$afc_obj$ca$eig)) {
              ecrire_csv_6_decimales(as.data.frame(rv$afc_obj$ca$eig), file.path(rv$afc_dir, "valeurs_propres.csv"), row.names = TRUE)
            }

            rv$afc_table_mots <- rv$afc_obj$termes_stats
          }

          if (!is.null(rv$afc_vars_obj) && !is.null(rv$afc_vars_obj$ca)) {

            afc_vars_png <- file.path(rv$afc_dir, "afc_variables_etoilees.png")

            activer_repel2 <- TRUE
            if (!is.null(input$afc_reduire_chevauchement)) activer_repel2 <- isTRUE(input$afc_reduire_chevauchement)

            top_mod <- 120
            if (!is.null(input$afc_top_modalites) && is.finite(input$afc_top_modalites)) top_mod <- as.integer(input$afc_top_modalites)

            png(afc_vars_png, width = 2000, height = 1600, res = 180)
            try(tracer_afc_variables_etoilees(rv$afc_vars_obj, axes = c(1, 2), top_modalites = top_mod, activer_repel = activer_repel2), silent = TRUE)
            dev.off()

            rv$afc_plot_vars <- afc_vars_png

            ecrire_csv_6_decimales(rv$afc_vars_obj$table, file.path(rv$afc_dir, "table_classes_variables.csv"), row.names = TRUE)
            ecrire_csv_6_decimales(rv$afc_vars_obj$rowcoord, file.path(rv$afc_dir, "coords_classes_vars.csv"), row.names = TRUE)
            ecrire_csv_6_decimales(rv$afc_vars_obj$colcoord, file.path(rv$afc_dir, "coords_modalites.csv"), row.names = TRUE)
            ecrire_csv_6_decimales(rv$afc_vars_obj$modalites_stats, file.path(rv$afc_dir, "stats_modalites.csv"), row.names = FALSE)

            if (!is.null(rv$afc_vars_obj$ca$eig)) {
              ecrire_csv_6_decimales(as.data.frame(rv$afc_vars_obj$ca$eig), file.path(rv$afc_dir, "valeurs_propres_vars.csv"), row.names = TRUE)
            }

            rv$afc_table_vars <- rv$afc_vars_obj$modalites_stats
          }

          avancer(0.76, "Concordancier HTML")
          rv$statut <- "Concordancier..."

          html_file <- file.path(rv$export_dir, "segments_par_classe.html")
          textes_index_ok <- rv$textes_indexation[docnames(dfm_ok)]
          names(textes_index_ok) <- docnames(dfm_ok)

          wordcloud_dir <- file.path(rv$export_dir, "wordclouds")
          dir.create(wordcloud_dir, showWarnings = FALSE, recursive = TRUE)
          cooc_dir <- file.path(rv$export_dir, "cooccurrences")
          dir.create(cooc_dir, showWarnings = FALSE, recursive = TRUE)

          classes_uniques <- sort(unique(as.integer(docvars(filtered_corpus_ok)$Classes)))

          for (cl in classes_uniques) {
            top_n_demande <- suppressWarnings(as.integer(input$top_n))
            if (!is.finite(top_n_demande) || is.na(top_n_demande)) top_n_demande <- 20L
            top_n_demande <- max(5L, top_n_demande)

            df_stats_cl <- subset(res_stats_df, Classe == cl & p <= input$max_p)
            if (nrow(df_stats_cl) > 0) {
              df_stats_cl <- df_stats_cl[order(-df_stats_cl$chi2), , drop = FALSE]
              df_stats_cl <- head(df_stats_cl, top_n_demande)

              wc_png <- file.path(wordcloud_dir, paste0("cluster_", cl, "_wordcloud.png"))
              try({
                png(wc_png, width = 800, height = 600)
                suppressWarnings(wordcloud(
                  words = df_stats_cl$Terme,
                  freq = df_stats_cl$chi2,
                  scale = c(10, 0.5),
                  min.freq = 0,
                  max.words = nrow(df_stats_cl),
                  colors = brewer.pal(8, "Dark2")
                ))
                dev.off()
              }, silent = TRUE)
            }

            tok_cl <- tok_ok[docvars(filtered_corpus_ok)$Classes == cl]
            cooc_png <- file.path(cooc_dir, paste0("cluster_", cl, "_fcm_network.png"))

            try({
              if (length(tok_cl) > 0) {
                fcm_cl <- fcm(tok_cl, context = "window", window = max(1, as.integer(input$window_cooc)), tri = FALSE)
                term_freq <- sort(colSums(fcm_cl), decreasing = TRUE)
                top_feat_demande <- suppressWarnings(as.integer(input$top_feat))
                if (!is.finite(top_feat_demande) || is.na(top_feat_demande)) top_feat_demande <- 20L
                top_feat_demande <- max(5L, top_feat_demande)

                # On borne aussi par top_n pour garder une cohérence entre nuage de mots et graphe de cooccurrences.
                top_feat_effectif <- min(top_feat_demande, top_n_demande)
                feat_sel <- names(term_freq)[seq_len(min(top_feat_effectif, length(term_freq)))]
                fcm_cl <- fcm_select(fcm_cl, feat_sel, selection = "keep")

                adj <- as.matrix(fcm_cl)
                g <- graph_from_adjacency_matrix(adj, mode = "undirected", weighted = TRUE, diag = FALSE)

                num_nodes <- length(V(g))
                palette_colors <- brewer.pal(min(8, num_nodes), "Set3")
                V(g)$color <- palette_colors[seq_along(V(g))]

                png(cooc_png, width = 1600, height = 1200)
                plot(
                  g,
                  layout = layout_with_fr(g),
                  main = paste("Cooccurrences - Classe", cl),
                  vertex.size = 16,
                  vertex.color = V(g)$color,
                  vertex.label = V(g)$name,
                  vertex.label.cex = 1,
                  edge.width = E(g)$weight / 2,
                  edge.color = "gray80"
                )
                dev.off()
              }
            }, silent = TRUE)
          }

          explor_assets <- NULL
          ok_chd_png <- generer_chd_explor_si_absente(rv)

          chd_png_rel <- NULL
          if (isTRUE(ok_chd_png) && file.exists(file.path(rv$export_dir, "explor", "chd.png"))) {
            chd_png_rel <- file.path("explor", "chd.png")
          }
          chd_html_rel <- generer_chd_html_explor(rv, chd_png_rel)

          wc_files <- list.files(wordcloud_dir, pattern = "\\.png$", full.names = FALSE)
          if (length(wc_files) > 0) {
            wc_classes <- gsub("^cluster_([0-9]+)_wordcloud\\.png$", "\\1", wc_files)
            wordclouds_df <- data.frame(
              classe = wc_classes,
              src = file.path("wordclouds", wc_files),
              stringsAsFactors = FALSE
            )
            wordclouds_df <- wordclouds_df[order(suppressWarnings(as.integer(wordclouds_df$classe))), , drop = FALSE]
          } else {
            wordclouds_df <- data.frame(classe = character(0), src = character(0), stringsAsFactors = FALSE)
          }

          cooc_files <- list.files(cooc_dir, pattern = "\\.png$", full.names = FALSE)
          if (length(cooc_files) > 0) {
            cooc_classes <- gsub("^cluster_([0-9]+)_fcm_network\\.png$", "\\1", cooc_files)
            coocs_df <- data.frame(
              classe = cooc_classes,
              src = file.path("cooccurrences", cooc_files),
              stringsAsFactors = FALSE
            )
            coocs_df <- coocs_df[order(suppressWarnings(as.integer(coocs_df$classe))), , drop = FALSE]
          } else {
            coocs_df <- data.frame(classe = character(0), src = character(0), stringsAsFactors = FALSE)
          }

          explor_assets <- list(
            chd = chd_png_rel,
            chd_html = chd_html_rel,
            wordclouds = wordclouds_df,
            coocs = coocs_df
          )
          rv$explor_assets <- explor_assets

          args_concordancier <- list(
            chemin_sortie = html_file,
            segments_by_class = segments_by_class,
            res_stats_df = res_stats_df,
            max_p = input$max_p,
            textes_indexation = textes_index_ok,
            spacy_tokens_df = rv$spacy_tokens_df,
            explor_assets = explor_assets,
            avancer = avancer,
            rv = rv
          )

          do.call(generer_concordancier_html, args_concordancier)

          rv$html_file <- html_file

          avancer(0.96, "ZIP")
          rv$statut <- "Création ZIP..."
          rv$zip_file <- file.path(rv$base_dir, "exports_rainette.zip")
          if (file.exists(rv$zip_file)) unlink(rv$zip_file)

          ancien_wd <- getwd()
          setwd(rv$base_dir)
          utils::zip(zipfile = rv$zip_file, files = "exports")
          setwd(ancien_wd)

          if (!(rv$exports_prefix %in% names(shiny::resourcePaths()))) {
            shiny::addResourcePath(rv$exports_prefix, rv$export_dir)
          }

          rv$statut <- "Analyse terminée."
          rv$progression <- 100
          ajouter_log(rv, "Analyse terminée.")
          showNotification("Analyse terminée.", type = "message", duration = 5)

        }, error = function(e) {
          rv$statut <- paste0("Erreur : ", e$message)
          ajouter_log(rv, paste0("ERREUR : ", e$message))
          showNotification(e$message, type = "error", duration = 8)
        })
      })
    })
}