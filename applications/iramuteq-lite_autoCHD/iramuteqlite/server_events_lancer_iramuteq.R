# Rôle du fichier: server_events_lancer_iramuteq.R porte le pipeline d'analyse IRaMuTeQ-lite.
# Ce script centralise une responsabilité métier/technique utilisée par l'application.
# Module server - événement principal `input$lancer`
# Ce fichier encapsule le pipeline principal lancé au clic sur "Lancer l'analyse"
# (préparation, CHD/AFC/NER, exports) pour alléger `app.R` à comportement constant.

register_events_lancer <- function(input, output, session, rv) {
    app_dir <- tryCatch(shiny::getShinyOption("appDir"), error = function(e) NULL)
    if (is.null(app_dir) || !nzchar(app_dir)) app_dir <- getwd()
    env_modules <- environment()

    if (!exists("ajouter_log", mode = "function", inherits = TRUE)) {
      ajouter_log <- function(rv, message) {
        if (is.null(rv)) return(invisible(NULL))
        msg <- as.character(message)
        msg <- msg[!is.na(msg)]
        msg <- msg[nzchar(msg)]
        if (!length(msg)) return(invisible(NULL))
        msg <- paste(msg, collapse = " ")

        horodatage <- format(Sys.time(), "%Y-%m-%d %H:%M:%S")
        msg_horodate <- paste0("[", horodatage, "] ", msg)

        precedent <- rv$logs
        if (is.null(precedent) || !length(precedent) || all(is.na(precedent)) || !any(nzchar(precedent))) {
          rv$logs <- msg_horodate
        } else {
          precedent <- precedent[!is.na(precedent)]
          precedent <- precedent[nzchar(precedent)]
          rv$logs <- paste(c(precedent, msg_horodate), collapse = "\n")
        }

        message("[IRaMuTeQ-lite] ", msg_horodate)
        flush.console()

        invisible(NULL)
      }
    }

    if (!exists("md5_fichier", mode = "function", inherits = TRUE)) {
      md5_fichier <- function(path) {
        if (is.null(path) || !nzchar(path) || !file.exists(path)) return(NA_character_)

        md5 <- tryCatch(unname(tools::md5sum(path)[[1]]), error = function(e) NA_character_)
        if (is.null(md5) || !length(md5) || is.na(md5) || !nzchar(md5)) return(NA_character_)
        as.character(md5)
      }
    }

    if (!exists("import_corpus_iramuteq", mode = "function", inherits = TRUE)) {
      import_corpus_iramuteq <- function(chemin_fichier) {
        lignes <- readLines(chemin_fichier, encoding = "UTF-8", warn = FALSE)
        if (length(lignes) == 0) stop("Corpus vide : aucun contenu lisible.")

        headers <- grepl("^\\*\\*\\*\\*", lignes)
        textes <- character(0)
        ids <- character(0)
        etoiles_par_doc <- vector("list", 0)

        if (any(headers)) {
          idx <- which(headers)
          bornes <- c(idx, length(lignes) + 1L)
          for (i in seq_along(idx)) {
            entete <- as.character(lignes[idx[[i]]])
            tokens_entete <- unlist(regmatches(entete, gregexpr("\\*[[:alnum:]_\\-]+", entete, perl = TRUE)), use.names = FALSE)
            tokens_entete <- unique(tokens_entete[grepl("^\\*[[:alnum:]_\\-]+$", tokens_entete)])

            debut <- idx[[i]] + 1L
            fin <- bornes[[i + 1L]] - 1L
            contenu <- if (debut <= fin) lignes[debut:fin] else character(0)
            contenu <- trimws(contenu)
            contenu <- contenu[nzchar(contenu)]
            if (length(contenu) == 0) next

            textes <- c(textes, paste(contenu, collapse = " "))
            ids <- c(ids, paste0("doc_", i))
            etoiles_par_doc[[length(etoiles_par_doc) + 1L]] <- tokens_entete
          }
        } else {
          lignes2 <- trimws(lignes)
          lignes2 <- lignes2[nzchar(lignes2)]
          if (length(lignes2) == 0) stop("Corpus vide : aucune ligne non vide.")
          textes <- lignes2
          ids <- paste0("doc_", seq_along(textes))
          etoiles_par_doc <- rep(list(character(0)), length(textes))
        }

        if (length(textes) == 0) stop("Corpus vide : aucune unité de texte détectée.")

        base_df <- data.frame(doc_id = ids, text = textes, stringsAsFactors = FALSE)

        noms_etoiles <- unique(unlist(lapply(etoiles_par_doc, function(tok) {
          tok <- tok[!is.na(tok) & nzchar(tok)]
          if (length(tok) == 0) return(character(0))
          sous <- sub("^\\*", "", tok)
          sous <- sub("_.*$", "", sous)
          sous <- sous[nzchar(sous)]
          paste0("*", sous)
        }), use.names = FALSE))

        if (length(noms_etoiles) > 0) {
          for (cn in noms_etoiles) base_df[[cn]] <- NA_character_
          for (i in seq_along(etoiles_par_doc)) {
            toks <- etoiles_par_doc[[i]]
            if (length(toks) == 0) next
            for (tk in toks) {
              corps <- sub("^\\*", "", tk)
              if (!nzchar(corps)) next
              var <- sub("_.*$", "", corps)
              val <- sub("^[^_]*_?", "", corps)
              if (!nzchar(var)) next
              if (!nzchar(val) || identical(val, var)) val <- "1"
              cn <- paste0("*", var)
              if (cn %in% names(base_df)) base_df[i, cn] <- val
            }
          }
        }

        quanteda::corpus(base_df, text_field = "text")
      }
    }

    if (!exists("split_segments", mode = "function", inherits = TRUE)) {
      split_segments <- function(corpus,
                                 segment_size = 40,
                                 remove_punct = FALSE,
                                 remove_numbers = FALSE,
                                 force_split_on_strong_punct = FALSE) {
        segment_size <- suppressWarnings(as.integer(segment_size))
        if (!is.finite(segment_size) || is.na(segment_size) || segment_size < 1) segment_size <- 40L

        docs <- as.character(corpus)
        dn <- as.character(quanteda::docnames(corpus))
        if (!length(dn) || any(!nzchar(dn))) dn <- paste0("doc_", seq_along(docs))

        out_text <- character(0)
        out_id <- character(0)
        out_src <- character(0)
        out_docvars <- list()
        dv_in <- tryCatch(quanteda::docvars(corpus), error = function(e) NULL)

        for (i in seq_along(docs)) {
          if (isTRUE(force_split_on_strong_punct)) {
            doc_with_newlines <- gsub("\r\n|\r|\n", " __NL_SEG_BREAK__ ", docs[[i]], perl = TRUE)
            tok_doc <- quanteda::tokens(
              doc_with_newlines,
              remove_punct = FALSE,
              remove_numbers = isTRUE(remove_numbers),
              remove_symbols = TRUE,
              remove_separators = TRUE,
              split_hyphens = FALSE
            )
            tok <- as.character(tok_doc[[1]])
            tok <- tok[nzchar(tok)]
            if (length(tok) == 0) next

            seg_tokens <- character(0)
            seg_idx <- 0L

            append_segment <- function(tokens_to_write) {
              seg <- paste(tokens_to_write, collapse = " ")
              if (!nzchar(seg)) return(invisible(NULL))
              seg_idx <<- seg_idx + 1L
              out_text <<- c(out_text, seg)
              out_id <<- c(out_id, paste0(dn[[i]], "_seg", seg_idx))
              out_src <<- c(out_src, dn[[i]])
              if (!is.null(dv_in) && nrow(dv_in) >= i) {
                out_docvars[[length(out_docvars) + 1L]] <<- dv_in[i, , drop = FALSE]
              } else {
                out_docvars[[length(out_docvars) + 1L]] <<- NULL
              }
            }

            rank_boundary <- function(token) {
              if (!nzchar(token)) return(4L)
              if (grepl("^[.!?…]+$", token)) return(1L)
              if (grepl("^[;:]+$", token)) return(2L)
              if (grepl("^[,]+$", token)) return(3L)
              4L
            }

            compute_state <- function(tokens_vec) {
              candidates <- list()
              non_punct_count <- 0L
              for (idx_tok in seq_along(tokens_vec)) {
                tk2 <- tokens_vec[[idx_tok]]
                if (identical(tk2, "__NL_SEG_BREAK__")) next
                is_punct2 <- grepl("^[[:punct:]]+$", tk2)
                if (!isTRUE(is_punct2)) non_punct_count <- non_punct_count + 1L
                boundary_rank <- if (isTRUE(is_punct2)) rank_boundary(tk2) else 4L
                candidates[[length(candidates) + 1L]] <- list(
                  pos = idx_tok,
                  count = non_punct_count,
                  rank = boundary_rank
                )
              }
              list(candidates = candidates, non_punct_count = non_punct_count)
            }

            choose_boundary <- function(candidates, target_size) {
              if (length(candidates) == 0) return(NULL)
              min_count <- max(1L, floor(target_size * 0.5))
              cand_ok <- Filter(function(x) x$count >= min_count, candidates)
              if (length(cand_ok) == 0) cand_ok <- candidates
              ord <- order(
                vapply(cand_ok, function(x) x$rank, integer(1)),
                vapply(cand_ok, function(x) abs(x$count - target_size), integer(1)),
                -vapply(cand_ok, function(x) x$pos, integer(1))
              )
              cand_ok[[ord[[1]]]]
            }

            flush_by_policy <- function() {
              state <- compute_state(seg_tokens)
              while (state$non_punct_count >= segment_size && length(state$candidates) > 0) {
                best <- choose_boundary(state$candidates, segment_size)
                if (is.null(best)) break
                write_tokens <- seg_tokens[seq_len(best$pos)]
                write_tokens <- write_tokens[write_tokens != "__NL_SEG_BREAK__"]
                if (isTRUE(remove_punct)) {
                  write_tokens <- write_tokens[!grepl("^[[:punct:]]+$", write_tokens)]
                }
                append_segment(write_tokens)
                if (best$pos < length(seg_tokens)) {
                  seg_tokens <<- seg_tokens[(best$pos + 1L):length(seg_tokens)]
                } else {
                  seg_tokens <<- character(0)
                }
                state <- compute_state(seg_tokens)
              }
            }

            for (k in seq_along(tok)) {
              tk <- tok[[k]]
              if (identical(tk, "__NL_SEG_BREAK__")) {
                flush_by_policy()
                if (length(seg_tokens) > 0) {
                  remain_tokens <- seg_tokens[seg_tokens != "__NL_SEG_BREAK__"]
                  if (isTRUE(remove_punct)) {
                    remain_tokens <- remain_tokens[!grepl("^[[:punct:]]+$", remain_tokens)]
                  }
                  append_segment(remain_tokens)
                  seg_tokens <- character(0)
                }
                next
              }
              seg_tokens <- c(seg_tokens, tk)
              flush_by_policy()
            }

            if (length(seg_tokens) > 0) {
              remain_tokens <- seg_tokens[seg_tokens != "__NL_SEG_BREAK__"]
              if (isTRUE(remove_punct)) {
                remain_tokens <- remain_tokens[!grepl("^[[:punct:]]+$", remain_tokens)]
              }
              append_segment(remain_tokens)
            }
          } else {
            tok_doc <- quanteda::tokens(
              docs[[i]],
              remove_punct = isTRUE(remove_punct),
              remove_numbers = isTRUE(remove_numbers),
              remove_symbols = TRUE,
              remove_separators = TRUE,
              split_hyphens = FALSE
            )
            tok <- as.character(tok_doc[[1]])
            tok <- tok[nzchar(tok)]
            if (length(tok) == 0) next

            nseg <- ceiling(length(tok) / segment_size)
            for (j in seq_len(nseg)) {
              deb <- ((j - 1L) * segment_size) + 1L
              fin <- min(j * segment_size, length(tok))
              seg <- paste(tok[deb:fin], collapse = " ")
              out_text <- c(out_text, seg)
              out_id <- c(out_id, paste0(dn[[i]], "_seg", j))
              out_src <- c(out_src, dn[[i]])
              if (!is.null(dv_in) && nrow(dv_in) >= i) {
                out_docvars[[length(out_docvars) + 1L]] <- dv_in[i, , drop = FALSE]
              } else {
                out_docvars[[length(out_docvars) + 1L]] <- NULL
              }
            }
          }
        }

        if (length(out_text) == 0) stop("Segmentation impossible : aucun segment généré.")

        corp <- quanteda::corpus(
          data.frame(doc_id = out_id, text = out_text, segment_source = out_src, stringsAsFactors = FALSE),
          text_field = "text"
        )
        quanteda::docvars(corp, "segment_source") <- out_src

        if (length(out_docvars) > 0 && any(vapply(out_docvars, Negate(is.null), logical(1)))) {
          idx_valid <- which(vapply(out_docvars, Negate(is.null), logical(1)))
          dv_seg <- do.call(rbind, out_docvars[idx_valid])
          if (!is.null(dv_seg) && nrow(dv_seg) == length(idx_valid)) {
            cn_copy <- setdiff(colnames(dv_seg), "segment_source")
            for (cn in cn_copy) {
              vals <- rep(NA, quanteda::ndoc(corp))
              vals[idx_valid] <- dv_seg[[cn]]
              quanteda::docvars(corp, cn) <- vals
            }
          }
        }
        corp
      }
    }

    if (!exists("split_segments_double_rst", mode = "function", inherits = TRUE)) {
      split_segments_double_rst <- function(corpus,
                                            rst1 = 12,
                                            rst2 = 14,
                                            remove_punct = FALSE,
                                            remove_numbers = FALSE,
                                            force_split_on_strong_punct = FALSE) {
        rst1 <- suppressWarnings(as.integer(rst1))
        rst2 <- suppressWarnings(as.integer(rst2))
        if (!is.finite(rst1) || is.na(rst1) || rst1 < 1) rst1 <- 12L
        if (!is.finite(rst2) || is.na(rst2) || rst2 < 1) rst2 <- 14L

        # Reproduction minimale du mode "double sur RST" :
        # 1) segmentation en blocs rst1,
        # 2) segmentation indépendante en blocs rst2,
        # 3) concaténation des deux jeux de segments pour l'analyse CHD.
        #
        # Note: re-segmenter rst1 -> rst2 rend rst2 inopérant quand rst2 > rst1
        # (les segments sont déjà trop courts). Ici, chaque RST est appliqué au
        # corpus d'origine pour conserver l'effet attendu des deux paramètres.
        corpus_rst1 <- split_segments(
          corpus,
          segment_size = rst1,
          remove_punct = isTRUE(remove_punct),
          remove_numbers = isTRUE(remove_numbers),
          force_split_on_strong_punct = isTRUE(force_split_on_strong_punct)
        )

        corpus_rst2 <- split_segments(
          corpus,
          segment_size = rst2,
          remove_punct = isTRUE(remove_punct),
          remove_numbers = isTRUE(remove_numbers),
          force_split_on_strong_punct = isTRUE(force_split_on_strong_punct)
        )

        txt1 <- as.character(corpus_rst1)
        txt2 <- as.character(corpus_rst2)

        id1 <- paste0(as.character(quanteda::docnames(corpus_rst1)), "_rst1")
        id2 <- paste0(as.character(quanteda::docnames(corpus_rst2)), "_rst2")

        df_out <- data.frame(
          doc_id = c(id1, id2),
          text = c(txt1, txt2),
          stringsAsFactors = FALSE
        )

        corp_out <- quanteda::corpus(df_out, text_field = "text")

        dv1 <- tryCatch(quanteda::docvars(corpus_rst1), error = function(e) NULL)
        dv2 <- tryCatch(quanteda::docvars(corpus_rst2), error = function(e) NULL)

        if (!is.null(dv1) && !is.null(dv2)) {
          cols <- union(colnames(dv1), colnames(dv2))
          for (cn in cols) {
            v1 <- if (cn %in% colnames(dv1)) as.character(dv1[[cn]]) else rep(NA_character_, nrow(dv1))
            v2 <- if (cn %in% colnames(dv2)) as.character(dv2[[cn]]) else rep(NA_character_, nrow(dv2))
            quanteda::docvars(corp_out, cn) <- c(v1, v2)
          }
        }

        quanteda::docvars(corp_out, "rst_source") <- c(rep("rst1", length(txt1)), rep("rst2", length(txt2)))
        corp_out
      }
    }

    if (!exists("calculer_stats_corpus", mode = "function", inherits = TRUE)) {
      calculer_stats_corpus <- function(chemin_fichier,
                                        corpus_segments,
                                        nom_corpus = NULL,
                                        tokens_stats = NULL,
                                        remove_punct = FALSE,
                                        remove_numbers = FALSE) {
        lignes <- tryCatch(readLines(chemin_fichier, encoding = "UTF-8", warn = FALSE), error = function(e) character(0))
        if (!is.null(tokens_stats)) {
          tokens <- unlist(tokens_stats, use.names = FALSE)
        } else {
          tokens_obj <- quanteda::tokens(
            corpus_segments,
            remove_punct = isTRUE(remove_punct),
            remove_numbers = isTRUE(remove_numbers),
            remove_symbols = TRUE,
            remove_separators = TRUE,
            split_hyphens = FALSE
          )
          tokens <- unlist(tokens_obj, use.names = FALSE)
        }
        tokens <- tolower(as.character(tokens))
        tokens <- tokens[nzchar(tokens)]

        n_tokens <- length(tokens)
        tab <- sort(table(tokens), decreasing = TRUE)
        n_formes <- length(tab)
        n_hapax <- if (length(tab) > 0) sum(tab == 1) else 0

        metrique <- c(
          "Nom du corpus",
          "Nombre de textes",
          "Nombre de mots dans le corpus",
          "Nombre de formes",
          "Nombre de segments de texte",
          "Nombre d'Hapax",
          "Loi de Zpif"
        )
        valeur <- c(
          ifelse(is.null(nom_corpus) || !nzchar(nom_corpus), basename(chemin_fichier), nom_corpus),
          as.character(sum(grepl("^\\*\\*\\*\\*", lignes))),
          as.character(n_tokens),
          as.character(n_formes),
          as.character(quanteda::ndoc(corpus_segments)),
          as.character(n_hapax),
          "N/A"
        )

        zipf <- if (length(tab) >= 2) {
          rang <- seq_along(tab)
          freq <- as.numeric(tab)
          fit <- tryCatch(stats::lm(log(freq) ~ log(rang)), error = function(e) NULL)
          pred <- if (is.null(fit)) rep(NA_real_, length(freq)) else as.numeric(exp(stats::predict(fit)))
          data.frame(
            rang = rang,
            frequence = freq,
            pred = pred,
            log_rang = log(rang),
            log_frequence = log(freq),
            log_pred = ifelse(is.na(pred), NA_real_, log(pred)),
            stringsAsFactors = FALSE
          )
        } else {
          NULL
        }

        list(table = data.frame(Metrique = metrique, Valeur = valeur, stringsAsFactors = FALSE), zipf = zipf)
      }
    }

    if (!exists("appliquer_nettoyage_iramuteq", mode = "function", inherits = TRUE)) {
      chemin_nettoyage_iramuteq <- file.path(app_dir, "iramuteqlite", "nettoyage_iramuteq.R")
      if (file.exists(chemin_nettoyage_iramuteq)) {
        source(chemin_nettoyage_iramuteq, encoding = "UTF-8", local = TRUE)
      }
    }

    if (!exists("appliquer_nettoyage_iramuteq", mode = "function", inherits = TRUE)) {
      appliquer_nettoyage_iramuteq <- function(textes,
                                               activer_nettoyage = FALSE,
                                               forcer_minuscules = FALSE,
                                               supprimer_chiffres = FALSE,
                                               supprimer_apostrophes = FALSE,
                                               remplacer_tirets_espaces = FALSE) {
        if (is.null(textes)) return(character(0))
        x <- as.character(textes)
        if (isTRUE(forcer_minuscules)) x <- tolower(x)
        x
      }
    }




    charger_lexique_fr <- function(app_dir) {
      chemin_lexique <- file.path(app_dir, "dictionnaires", "lexique_fr.csv")
      if (!file.exists(chemin_lexique)) {
        stop(paste0("Fichier lexique introuvable: ", chemin_lexique))
      }

      lexique <- utils::read.csv2(
        chemin_lexique,
        stringsAsFactors = FALSE,
        encoding = "UTF-8"
      )

      colonnes_requises <- c("c_mot", "c_lemme", "c_morpho")
      if (!all(colonnes_requises %in% names(lexique))) {
        stop("Le fichier lexique_fr.csv doit contenir les colonnes c_mot, c_lemme et c_morpho.")
      }

      lexique$c_mot <- tolower(trimws(as.character(lexique$c_mot)))
      lexique$c_lemme <- tolower(trimws(as.character(lexique$c_lemme)))
      lexique$c_morpho <- trimws(as.character(lexique$c_morpho))
      lexique <- lexique[nzchar(lexique$c_mot) & nzchar(lexique$c_lemme), c("c_mot", "c_lemme", "c_morpho"), drop = FALSE]
      lexique <- lexique[!duplicated(lexique$c_mot), , drop = FALSE]
      lexique
    }

    charger_expression_fr <- function(app_dir) {
      chemins_candidats <- c(
        file.path(app_dir, "dictionnaires", "expression_fr.csv"),
        file.path(app_dir, "dictionnaires", "expressions.csv")
      )
      chemin_expression <- chemins_candidats[file.exists(chemins_candidats)][1]
      if (is.na(chemin_expression) || !nzchar(chemin_expression)) {
        stop(
          paste0(
            "Fichier dictionnaire d'expressions introuvable. Chemins testés: ",
            paste(chemins_candidats, collapse = " | ")
          )
        )
      }

      expressions <- utils::read.csv2(
        chemin_expression,
        stringsAsFactors = FALSE,
        encoding = "UTF-8"
      )

      colonnes_requises <- c("dic_mot", "dic_norm")
      if (!all(colonnes_requises %in% names(expressions))) {
        stop("Le fichier expression_fr.csv (ou expressions.csv) doit contenir les colonnes dic_mot et dic_norm.")
      }

      expressions$dic_mot <- tolower(trimws(as.character(expressions$dic_mot)))
      expressions$dic_mot <- gsub("[’`´ʼʹ]", "'", expressions$dic_mot, perl = TRUE)
      expressions$dic_norm <- tolower(trimws(as.character(expressions$dic_norm)))
      expressions <- expressions[
        nzchar(expressions$dic_mot) & nzchar(expressions$dic_norm),
        c("dic_mot", "dic_norm"),
        drop = FALSE
      ]
      expressions <- expressions[!duplicated(expressions$dic_mot), , drop = FALSE]
      attr(expressions, "source_file") <- chemin_expression
      expressions
    }

    appliquer_dictionnaire_expressions <- function(textes, expressions_df) {
      if (is.null(textes) || length(textes) == 0 ||
          is.null(expressions_df) || !is.data.frame(expressions_df) || nrow(expressions_df) == 0) {
        return(list(textes = as.character(textes), n_patterns = 0L, n_occurrences = 0L))
      }

      textes_out <- as.character(textes)
      textes_out <- gsub("[’`´ʼʹ]", "'", textes_out, perl = TRUE)
      dic <- expressions_df
      ord <- order(nchar(dic$dic_mot), decreasing = TRUE)
      dic <- dic[ord, , drop = FALSE]
      n_occurrences <- 0L

      construire_motif_regex_expression <- function(motif) {
        accent_map <- list(
          a = "aàáâäãå",
          e = "eèéêë",
          i = "iìíîï",
          o = "oòóôöõø",
          u = "uùúûü",
          y = "yÿ",
          c = "cç",
          n = "nñ"
        )

        chars <- strsplit(motif, "", fixed = TRUE)[[1]]
        out <- character(length(chars))
        for (k in seq_along(chars)) {
          ch <- chars[[k]]
          ch_l <- tolower(ch)
          if (ch == "'") {
            out[[k]] <- "['’`´ʼʹ]"
          } else if (ch_l %in% names(accent_map)) {
            out[[k]] <- paste0("[", accent_map[[ch_l]], "]")
          } else if (ch_l == "œ") {
            out[[k]] <- "(?:œ|oe)"
          } else {
            chars_speciaux_regex <- c("\\", "^", "$", ".", "|", "?", "*", "+", "(", ")", "[", "]", "{", "}")
            out[[k]] <- if (ch %in% chars_speciaux_regex) paste0("\\", ch) else ch
          }
        }
        paste0(out, collapse = "")
      }

      for (i in seq_len(nrow(dic))) {
        motif <- dic$dic_mot[[i]]
        remplacement <- dic$dic_norm[[i]]
        motif_echappe <- construire_motif_regex_expression(motif)
        regex <- paste0("(?i)(?<![[:alnum:]_])", motif_echappe, "(?![[:alnum:]_])")

        matches <- gregexpr(regex, textes_out, perl = TRUE)
        captures <- regmatches(textes_out, matches)
        captures_count <- sum(lengths(captures), na.rm = TRUE)
        if (captures_count > 0L) {
          remplacements <- lapply(captures, function(vals) {
            if (!length(vals)) return(character(0))
            rep(remplacement, length(vals))
          })
          regmatches(textes_out, matches) <- remplacements
          n_occurrences <- n_occurrences + as.integer(captures_count)
        }
      }

      list(textes = textes_out, n_patterns = nrow(dic), n_occurrences = as.integer(n_occurrences))
    }

    lire_min_docfreq_manuel <- function(valeur_brute, valeur_defaut = 3L) {
      valeur <- suppressWarnings(as.integer(valeur_brute))
      if (length(valeur) != 1L || is.na(valeur) || !is.finite(valeur) || valeur < 1L) {
        return(as.integer(max(1L, valeur_defaut)))
      }
      as.integer(valeur)
    }

    lire_top_n_wordcloud <- function(input_top_n, valeur_defaut = 20L, min_value = 5L) {
      top_n <- suppressWarnings(as.integer(input_top_n))
      if (length(top_n) != 1L || is.na(top_n) || !is.finite(top_n)) {
        top_n <- as.integer(valeur_defaut)
      }
      as.integer(max(as.integer(min_value), top_n))
    }

    parser_pos_spacy <- function(textes, ids_docs, rv) {
      if (length(textes) == 0) {
        return(data.frame(doc_id = character(0), token = character(0), pos = character(0), stringsAsFactors = FALSE))
      }

      python_bin <- Sys.which("python3")
      if (!nzchar(python_bin)) python_bin <- Sys.which("python")
      if (!nzchar(python_bin)) {
        stop("Filtrage POS spaCy indisponible: aucun interpréteur Python (python3/python) trouvé.")
      }

      script_path <- file.path(app_dir, "spacy", "pos_spacy.py")
      if (!file.exists(script_path)) {
        stop(paste0("Filtrage POS spaCy indisponible: script Python introuvable (", script_path, ")."))
      }

      in_csv <- tempfile(pattern = "spacy_pos_in_", fileext = ".csv")
      out_csv <- tempfile(pattern = "spacy_pos_out_", fileext = ".csv")
      on.exit(unlink(c(in_csv, out_csv), force = TRUE), add = TRUE)

      in_df <- data.frame(
        doc_id = as.character(ids_docs),
        text = as.character(textes),
        stringsAsFactors = FALSE
      )
      utils::write.csv(in_df, in_csv, row.names = FALSE, fileEncoding = "UTF-8", na = "")

      cmd_args <- c(
        script_path,
        "--input-csv", in_csv,
        "--output-csv", out_csv,
        "--model", "fr_core_news_lg"
      )

      cmd_out <- suppressWarnings(
        system2(python_bin, args = cmd_args, stdout = TRUE, stderr = TRUE)
      )
      status <- attr(cmd_out, "status")
      if (is.null(status)) status <- 0L

      if (!identical(as.integer(status), 0L)) {
        stop(
          paste0(
            "Analyse POS spaCy impossible via script Python (code=", status, "). ",
            paste(cmd_out, collapse = " ")
          )
        )
      }

      if (!file.exists(out_csv)) {
        stop("Analyse POS spaCy incomplète: fichier de sortie Python introuvable.")
      }

      parsed <- tryCatch(
        utils::read.csv(out_csv, stringsAsFactors = FALSE, fileEncoding = "UTF-8"),
        error = function(e) {
          stop(paste0("Lecture sortie spaCy impossible: ", e$message))
        }
      )

      if (!is.data.frame(parsed) || !"token" %in% names(parsed) || !"pos" %in% names(parsed)) {
        stop("Analyse POS spaCy incomplète: colonnes 'token'/'pos' absentes.")
      }

      parsed$doc_id <- as.character(parsed$doc_id)
      parsed$token <- tolower(trimws(as.character(parsed$token)))
      parsed$pos <- toupper(trimws(as.character(parsed$pos)))
      parsed <- parsed[nzchar(parsed$token) & nzchar(parsed$pos), c("doc_id", "token", "pos"), drop = FALSE]
      parsed
    }

    executer_pipeline_iramuteq <- function(input, rv, textes_chd) {
      if (is.null(textes_chd)) {
        stop("IRaMuTeQ-lite: textes_chd manquant pour la préparation du pipeline.")
      }

      textes_chr <- as.character(textes_chd)
      ids_docs <- names(textes_chd)
      if (is.null(ids_docs) || length(ids_docs) != length(textes_chr)) {
        ids_docs <- paste0("doc_", seq_along(textes_chr))
      }

      textes_tok <- textes_chr

      if (isTRUE(input$retirer_stopwords)) {
        textes_tok <- gsub(
          pattern = "(?i)\\b(?:[cdjlmnst]|qu)['’`´ʼʹ](?=[[:alpha:]])",
          replacement = "",
          x = textes_tok,
          perl = TRUE
        )
      }

      tok <- quanteda::tokens(
        textes_tok,
        remove_punct = isTRUE(input$supprimer_ponctuation),
        remove_numbers = isTRUE(input$supprimer_chiffres)
      )
      quanteda::docnames(tok) <- ids_docs
      tok <- quanteda::tokens_tolower(tok)

      if (isTRUE(input$lexique_utiliser_lemmes)) {
        if (is.null(rv$lexique_fr_df) || !is.data.frame(rv$lexique_fr_df) || nrow(rv$lexique_fr_df) == 0) {
          rv$lexique_fr_df <- charger_lexique_fr(app_dir)
          ajouter_log(rv, paste0("Lexique (fr) chargé: ", nrow(rv$lexique_fr_df), " entrées."))
        }

        vocabulaire <- quanteda::featnames(quanteda::dfm(tok))
        idx <- match(vocabulaire, rv$lexique_fr_df$c_mot)
        a_remplacer <- !is.na(idx)

        if (any(a_remplacer)) {
          motifs <- vocabulaire[a_remplacer]
          remplacements <- rv$lexique_fr_df$c_lemme[idx[a_remplacer]]
          tok <- quanteda::tokens_replace(
            tok,
            pattern = motifs,
            replacement = remplacements,
            valuetype = "fixed",
            case_insensitive = FALSE
          )
          ajouter_log(rv, paste0("Lemmatisation lexique_fr appliquée (forme -> c_lemme) sur ", length(motifs), " formes du vocabulaire."))
        } else {
          ajouter_log(rv, "Lemmatisation lexique_fr activée, mais aucune forme du vocabulaire n'a trouvé de lemme.")
        }
      }

      if (isTRUE(input$retirer_stopwords)) {
        stop_fr <- quanteda::stopwords("fr")
        n_feat_avant_stop <- quanteda::nfeat(quanteda::dfm(tok))
        tok <- quanteda::tokens_remove(tok, pattern = stop_fr, valuetype = "fixed", case_insensitive = TRUE)
        n_feat_apres_stop <- quanteda::nfeat(quanteda::dfm(tok))
        ajouter_log(rv, paste0("Filtrage stopwords quanteda(fr) appliqué : ", n_feat_avant_stop, " -> ", n_feat_apres_stop, " termes uniques."))
      }

      dfm_obj <- quanteda::dfm(tok)
      quanteda::docnames(dfm_obj) <- ids_docs

      log_presence_expressions <- function(dfm_stage, label_stage) {
        expr_df <- rv$expressions_actives_df
        if (is.null(expr_df) || !is.data.frame(expr_df) || nrow(expr_df) == 0 || !"dic_norm" %in% names(expr_df)) {
          return(invisible(NULL))
        }
        expr_norm <- unique(tolower(trimws(as.character(expr_df$dic_norm))))
        expr_norm <- expr_norm[nzchar(expr_norm)]
        if (length(expr_norm) == 0) {
          return(invisible(NULL))
        }
        feats <- tolower(trimws(as.character(quanteda::featnames(dfm_stage))))
        presents <- intersect(expr_norm, feats)
        absents <- setdiff(expr_norm, feats)
        ajouter_log(
          rv,
          paste0(
            "Expressions (dic_norm) présentes ", label_stage, " : ",
            length(presents), "/", length(expr_norm),
            " | absentes=", length(absents), "."
          )
        )
        if (length(presents) > 0) {
          ajouter_log(rv, paste0("Exemples expressions présentes ", label_stage, " : ", paste(utils::head(presents, 10), collapse = ", "), "."))
        }
      }

      ajouter_log(
        rv,
        "Contrôle des expressions (dic_norm) exécuté à 3 étapes: avant filtres, après filtrage morphosyntaxique, puis après min_docfreq."
      )

      log_presence_expressions(dfm_obj, "avant filtres morpho/min_docfreq")

      source_dict_chd <- if (identical(input$source_dictionnaire, "spacy")) "lexique_fr" else input$source_dictionnaire
      if (isTRUE(input$filtrage_morpho) && identical(input$source_dictionnaire, "spacy")) {
        ajouter_log(rv, "Option spaCy ignorée pour CHD: spaCy est réservé à la détection NER. Bascule automatique sur lexique_fr.")
      }

      if (isTRUE(input$filtrage_morpho) && identical(source_dict_chd, "lexique_fr")) {
        if (is.null(rv$lexique_fr_df) || !is.data.frame(rv$lexique_fr_df) || nrow(rv$lexique_fr_df) == 0) {
          rv$lexique_fr_df <- charger_lexique_fr(app_dir)
          ajouter_log(rv, paste0("Lexique (fr) chargé pour filtrage morphosyntaxique: ", nrow(rv$lexique_fr_df), " entrées."))
        }

        morpho_selection <- toupper(trimws(as.character(input$pos_lexique_a_conserver)))
        morpho_selection <- unique(morpho_selection[nzchar(morpho_selection)])
        inclure_autre_forme <- isTRUE(input$morpho_conserver_hors_lexique) || ("AUTRE_FORME" %in% morpho_selection)
        if (isTRUE(inclure_autre_forme) && !("AUTRE_FORME" %in% morpho_selection)) {
          morpho_selection <- c(morpho_selection, "AUTRE_FORME")
        }
        morpho_selection_lexique <- setdiff(morpho_selection, "AUTRE_FORME")

        if (length(morpho_selection_lexique) > 0 || isTRUE(inclure_autre_forme)) {
          lex <- rv$lexique_fr_df
          lex_morpho <- toupper(trimws(as.character(lex$c_morpho)))
          exclure_etre_verbe <- isTRUE(input$morpho_exclure_etre_verbe)
          categorie_verbe_selectionnee <- any(morpho_selection_lexique %in% c("VER", "VERB", "AUX", "VER_SUP"))

          idx <- nzchar(lex_morpho) & lex_morpho %in% morpho_selection_lexique
          termes_autorises <- unique(c(
            tolower(trimws(as.character(lex$c_mot[idx]))),
            tolower(trimws(as.character(lex$c_lemme[idx])))
          ))
          termes_autorises <- termes_autorises[nzchar(termes_autorises)]
          if (isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee)) {
            termes_autorises <- setdiff(termes_autorises, c("être", "etre"))
          }

          toutes_formes_lexique <- unique(c(
            tolower(trimws(as.character(lex$c_mot))),
            tolower(trimws(as.character(lex$c_lemme)))
          ))
          toutes_formes_lexique <- toutes_formes_lexique[nzchar(toutes_formes_lexique)]

          featnames_dfm <- quanteda::featnames(dfm_obj)
          featnames_norm <- tolower(trimws(as.character(featnames_dfm)))
          featnames_core <- gsub("^[[:punct:]]+|[[:punct:]]+$", "", featnames_norm, perl = TRUE)
          is_punct_feature <- !nzchar(featnames_core)

          in_selection <- (featnames_norm %in% termes_autorises) | (featnames_core %in% termes_autorises)
          in_lexique <- (featnames_norm %in% toutes_formes_lexique) | (featnames_core %in% toutes_formes_lexique)

          keep_mask <- in_selection
          if (isTRUE(inclure_autre_forme)) {
            keep_mask <- keep_mask | (!in_lexique & !is_punct_feature)
          }

          pattern_keep <- featnames_dfm[keep_mask]
          n_feat_avant_morpho <- quanteda::nfeat(dfm_obj)
          dfm_obj <- quanteda::dfm_select(
            dfm_obj,
            pattern = pattern_keep,
            selection = "keep",
            valuetype = "fixed",
            case_insensitive = FALSE
          )
          n_feat_apres_morpho <- quanteda::nfeat(dfm_obj)

          repartition_categories <- character(0)
          if (length(morpho_selection_lexique) > 0) {
            feat_ret_norm <- featnames_norm[keep_mask]
            feat_ret_core <- featnames_core[keep_mask]
            repartition_categories <- vapply(
              morpho_selection_lexique,
              function(cat) {
                idx_cat <- idx & lex_morpho == cat
                termes_cat <- unique(c(
                  tolower(trimws(as.character(lex$c_mot[idx_cat]))),
                  tolower(trimws(as.character(lex$c_lemme[idx_cat])))
                ))
                termes_cat <- termes_cat[nzchar(termes_cat)]
                if (!length(termes_cat)) return("0")
                as.character(sum((feat_ret_norm %in% termes_cat) | (feat_ret_core %in% termes_cat)))
              },
              character(1)
            )
          }
          if (length(repartition_categories) > 0) {
            ajouter_log(
              rv,
              paste0(
                "Répartition des termes conservés par c_morpho: ",
                paste0(names(repartition_categories), "=", repartition_categories, collapse = "; "),
                "."
              )
            )
          }

          ajouter_log(
            rv,
            paste0(
              "Filtrage morphosyntaxique lexique_fr appliqué (c_morpho=",
              paste(morpho_selection, collapse = ","),
              " | inclure_autre_forme=",
              ifelse(isTRUE(inclure_autre_forme), "1", "0"),
              " | exclure_etre_verbe=",
              ifelse(isTRUE(exclure_etre_verbe) && isTRUE(categorie_verbe_selectionnee), "1", "0"),
              " | ponct_exclue_autre_forme=1",
              " | normalisation_bords_ponct=1",
              ") : ",
              n_feat_avant_morpho,
              " -> ",
              n_feat_apres_morpho,
              " termes uniques."
            )
          )
        } else {
          ajouter_log(rv, "Filtrage morphosyntaxique activé sans catégorie c_morpho sélectionnée : étape ignorée.")
        }
      }

      log_presence_expressions(dfm_obj, "après filtrage morphosyntaxique")

      min_docfreq_val <- lire_min_docfreq_manuel(input$min_docfreq, valeur_defaut = 3L)
      rv$min_docfreq_applique <- min_docfreq_val
      ajouter_log(rv, paste0("min_docfreq appliqué (IRaMuTeQ-lite) = ", min_docfreq_val, " (manuel)."))

      dfm_obj <- quanteda::dfm_trim(dfm_obj, min_docfreq = min_docfreq_val)
      log_presence_expressions(dfm_obj, paste0("après min_docfreq=", min_docfreq_val))
      if (quanteda::nfeat(dfm_obj) < 1L) {
        stop(paste0("Aucun terme ne reste après filtrage min_docfreq=", min_docfreq_val, ". Diminuer cette valeur."))
      }

      list(
        tok = tok,
        dfm_obj = dfm_obj,
        langue_reference = "fr",
        source_dictionnaire = as.character(source_dict_chd)
      )
    }




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

    observeEvent(input$modele_chd, {
      updateRadioButtons(
        session,
        "source_dictionnaire",
        choices = c("Lexique (fr)" = "lexique_fr"),
        selected = "lexique_fr"
      )
    }, ignoreInit = FALSE)

    output$ui_concordancier_iramuteq <- renderUI({
      req(rv$export_dir)

      if (!dir.exists(rv$export_dir)) {
        return(tags$div(
          style = "padding: 12px;",
          tags$p("Le dossier d'exports est introuvable pour cette session."),
          tags$p("Relancer l'analyse pour régénérer les exports.")
        ))
      }

      if (is.null(rv$exports_prefix) || !nzchar(rv$exports_prefix)) {
        return(tags$div(
          style = "padding: 12px;",
          tags$p("Préfixe de ressources invalide."),
          tags$p("Relancer l'analyse pour régénérer les exports.")
        ))
      }

      if (!(rv$exports_prefix %in% names(shiny::resourcePaths()))) {
        shiny::addResourcePath(rv$exports_prefix, rv$export_dir)
      }

      candidats_html <- c(
        rv$html_file,
        file.path(rv$export_dir, "segments_par_classe.html"),
        file.path(rv$export_dir, "concordancier.html")
      )
      candidats_dyn <- list.files(
        rv$export_dir,
        pattern = "(segments.*classe|concord).*\\.html$",
        ignore.case = TRUE,
        full.names = TRUE
      )
      candidats_html <- c(candidats_html, candidats_dyn)
      candidats_html <- unique(candidats_html[!is.na(candidats_html) & nzchar(candidats_html)])
      html_existant <- candidats_html[file.exists(candidats_html)]

      if (length(html_existant) == 0) {
        return(tags$pre(
          style = "padding: 12px; white-space: pre-wrap;",
          paste(
            "Concordancier indisponible",
            "Le fichier du concordancier HTML n'est pas disponible pour cette analyse.",
            "Relancer l'analyse puis vérifier les logs si le problème persiste.",
            sep = "\n\n"
          )
        ))
      }

      src_html <- html_existant[[1]]
      nom_html <- basename(src_html)
      src_dans_exports <- file.path(rv$export_dir, nom_html)

      if (!isTRUE(file.exists(src_dans_exports))) {
        ok_copy <- tryCatch(file.copy(src_html, src_dans_exports, overwrite = TRUE), error = function(e) FALSE)
        if (isTRUE(ok_copy)) src_html <- src_dans_exports
      } else {
        src_html <- src_dans_exports
      }

      tags$iframe(
        src = paste0("/", rv$exports_prefix, "/", basename(src_html)),
        style = "width: 100%; height: 70vh; border: 1px solid #999;"
      )
    })

    output$ui_wordcloud_iramuteq <- renderUI({
      req(rv$export_dir, rv$exports_prefix)
      token_cache <- rv$wordcloud_refresh_token

      wc_files <- list.files(
        file.path(rv$export_dir, "wordclouds"),
        pattern = "^cluster_[0-9]+_wordcloud\\.png$",
        full.names = FALSE
      )
      if (length(wc_files) == 0) {
        mode_label <- if (identical(rv$res_type, "iramuteq")) "IRaMuTeQ-lite" else "analyse"
        return(tags$p(paste0("Aucun nuage de mots disponible (", mode_label, ").")))
      }

      wc_classes <- gsub("^cluster_([0-9]+)_wordcloud\\.png$", "\\1", wc_files)
      order_idx <- order(suppressWarnings(as.integer(wc_classes)))

      tags$div(
        lapply(order_idx, function(i) {
          classe_lbl <- wc_classes[[i]]
          src_rel <- file.path("wordclouds", wc_files[[i]])
          tags$div(
            style = "text-align: center; margin-bottom: 18px;",
            tags$h4(paste("Classe", classe_lbl)),
            tags$img(
              src = paste0("/", rv$exports_prefix, "/", src_rel, "?v=", token_cache),
              style = "max-width: 100%; height: auto; border: 1px solid #999; display: inline-block;"
            )
          )
        })
      )
    })

    normaliser_id_classe_local <- function(x) {
      x_chr <- as.character(x)
      x_chr <- trimws(x_chr)

      x_num <- suppressWarnings(as.numeric(x_chr))
      need_extract <- is.na(x_num) & !is.na(x_chr) & nzchar(x_chr)

      if (any(need_extract)) {
        extrait <- sub("^.*?(\\d+).*$", "\\1", x_chr[need_extract])
        extrait[!grepl("\\d", x_chr[need_extract])] <- NA_character_
        x_num[need_extract] <- suppressWarnings(as.numeric(extrait))
      }

      x_num
    }

    observeEvent(input$lancer, {
      rv$logs <- ""

      if (exists("capturer_parametres_analyse", mode = "function", inherits = TRUE)) {
        tryCatch(
          capturer_parametres_analyse(),
          error = function(e) {
            if (exists("ajouter_log", mode = "function", inherits = TRUE)) {
              ajouter_log(rv, paste0("Capture des paramètres: erreur non bloquante - ", e$message))
            }
            invisible(NULL)
          }
        )
      }
      rv$statut <- "Vérification du fichier..."
      rv$progression <- 0

      rv$spacy_tokens_df <- NULL
      rv$lexique_fr_df <- NULL
      rv$expression_fr_df <- NULL
      rv$expressions_actives_df <- NULL
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
      rv$stats_corpus_df <- NULL
      rv$stats_zipf_df <- NULL

      ajouter_log(rv, "Clic sur 'Lancer l'analyse' reçu.")

      if (exists("packages_manquants", inherits = TRUE) && length(packages_manquants) > 0) {
        rv$statut <- "Impossible de lancer l'analyse : dépendances manquantes."
        ajouter_log(
          rv,
          paste0(
            "Packages R manquants détectés au démarrage : ",
            paste(packages_manquants, collapse = ", ")
          )
        )
        showNotification(
          paste0(
            "Installation requise des packages : ",
            paste(packages_manquants, collapse = ", ")
          ),
          type = "error",
          duration = 10
        )
        return(invisible(NULL))
      }

      modele_chd <- "iramuteq"
      mode_iramuteq <- TRUE
      source_dictionnaire <- if (is.null(input$source_dictionnaire) || !nzchar(input$source_dictionnaire)) "lexique_fr" else as.character(input$source_dictionnaire)
      if (identical(source_dictionnaire, "spacy")) source_dictionnaire <- "lexique_fr"
      updateRadioButtons(
        session,
        "source_dictionnaire",
        choices = c("Lexique (fr)" = "lexique_fr"),
        selected = "lexique_fr"
      )
      updateRadioButtons(
        session,
        "modele_chd",
        selected = "iramuteq"
      )

      if (is.null(input$fichier_corpus) || is.null(input$fichier_corpus$datapath) || !file.exists(input$fichier_corpus$datapath)) {
        rv$statut <- "Aucun fichier uploadé."
        rv$progression <- 0
        ajouter_log(rv, "Aucun fichier uploadé côté serveur. Sélectionner un .txt puis relancer.")
        showNotification("Aucun fichier uploadé. Choisir un .txt.", type = "error", duration = 6)
        return(invisible(NULL))
      }

        # Utilise une notification de progression non bloquante.
        # Fallback robuste : certaines versions de Shiny ignorent/acceptent mal
        # l'argument `style`; on force aussi l'option globale en amont.
        p <- tryCatch(
          Progress$new(session, min = 0, max = 1, style = "notification"),
          error = function(e) Progress$new(session, min = 0, max = 1)
        )
        on.exit(try(p$close(), silent = TRUE), add = TRUE)

        avancer <- function(valeur, detail) {
          valeur <- max(0, min(1, valeur))
          p$set(value = valeur, message = "Calculs CHD en cours", detail = detail)
          rv$progression <- round(valeur * 100)
        }

        tryCatch({

          avancer(0.02, "Préparation des répertoires")
          rv$statut <- "Préparation des répertoires..."

          rv$base_dir <- file.path(tempdir(), paste0("iramuteq_", session$token))
          rv$export_dir <- file.path(rv$base_dir, "exports")
          dir.create(rv$export_dir, showWarnings = FALSE, recursive = TRUE)
          ajouter_log(rv, paste0("export_dir = ", rv$export_dir))

          avancer(0.08, "Import du corpus")
          rv$statut <- "Import du corpus..."
          chemin_fichier <- input$fichier_corpus$datapath
          md5 <- md5_fichier(chemin_fichier)
          ajouter_log(rv, paste0("MD5 fichier = ", md5))

          corpus_importe <- import_corpus_iramuteq(chemin_fichier)
          ajouter_log(rv, paste0("Nombre de documents importés : ", quanteda::ndoc(corpus_importe)))

          avancer(0.14, "Segmentation")
          rv$statut <- "Segmentation..."
          segment_size <- input$segment_size
          classif_mode_iramuteq <- as.character(input$iramuteq_classif_mode)
          if (!classif_mode_iramuteq %in% c("simple", "double")) classif_mode_iramuteq <- "simple"

          rst1_iramuteq <- suppressWarnings(as.integer(input$iramuteq_rst1))
          if (is.na(rst1_iramuteq) || rst1_iramuteq < 2L) rst1_iramuteq <- 12L

          rst2_iramuteq <- suppressWarnings(as.integer(input$iramuteq_rst2))
          if (is.na(rst2_iramuteq) || rst2_iramuteq < 2L) rst2_iramuteq <- 14L

          # Stats corpus: calculées sur la segmentation brute (sans filtres CHD).
          # Le comptage lexical est ensuite fait sur les textes préparés pour
          # éviter un écart entre statistiques affichées et pipeline IRaMuTeQ-lite.
          corpus_stats <- split_segments(
            corpus_importe,
            segment_size = segment_size,
            remove_punct = FALSE,
            remove_numbers = FALSE,
            force_split_on_strong_punct = isTRUE(input$segmenter_sur_ponctuation_forte)
          )

          # CHD: segmentation selon les options de prétraitement demandées.
          # En mode double, on applique deux découpes successives contrôlées par rst1/rst2.
          if (identical(classif_mode_iramuteq, "double")) {
            corpus <- split_segments_double_rst(
              corpus_importe,
              rst1 = rst1_iramuteq,
              rst2 = rst2_iramuteq,
              remove_punct = isTRUE(input$supprimer_ponctuation),
              remove_numbers = isTRUE(input$supprimer_chiffres),
              force_split_on_strong_punct = isTRUE(input$segmenter_sur_ponctuation_forte)
            )
            ajouter_log(rv, paste0("Segmentation CHD double (RST): rst1=", rst1_iramuteq, " | rst2=", rst2_iramuteq, "."))
          } else {
            corpus <- split_segments(
              corpus_importe,
              segment_size = segment_size,
              remove_punct = isTRUE(input$supprimer_ponctuation),
              remove_numbers = isTRUE(input$supprimer_chiffres),
              force_split_on_strong_punct = isTRUE(input$segmenter_sur_ponctuation_forte)
            )
          }
          min_docfreq_val <- lire_min_docfreq_manuel(input$min_docfreq, valeur_defaut = 3L)
          rv$min_docfreq_applique <- min_docfreq_val
          ajouter_log(rv, paste0("Nombre de segments corpus (stats) : ", quanteda::ndoc(corpus_stats)))
          ajouter_log(rv, paste0("Nombre de segments analyse (CHD) : ", quanteda::ndoc(corpus)))

          stats_corpus <- NULL
          rv$min_docfreq_applique <- min_docfreq_val
          ajouter_log(rv, paste0("Nombre de segments après découpage : ", quanteda::ndoc(corpus)))

          ids_orig <- as.character(quanteda::docnames(corpus))
          ids_corpus <- ids_orig
          invalides <- is.na(ids_corpus) | !nzchar(trimws(ids_corpus))
          if (any(invalides)) {
            ids_corpus[invalides] <- paste0("doc_", which(invalides))
          }

          ids_uniques <- make.unique(ids_corpus, sep = "_dup")
          modif_ids <- any(ids_uniques != ids_orig)
          if (isTRUE(modif_ids)) {
            n_problemes <- sum(invalides) + sum(duplicated(ids_corpus))
            ajouter_log(rv, paste0("Docnames invalides/dupliqués détectés après segmentation : ", n_problemes, ". Renommage automatique via make.unique()."))
          }

          quanteda::docnames(corpus) <- ids_uniques
          ids_corpus <- as.character(quanteda::docnames(corpus))

          textes_orig <- as.character(corpus)

          if (isTRUE(input$expression_utiliser_dictionnaire)) {
            rv$expression_fr_df <- charger_expression_fr(app_dir)
            ajouter_log(rv, paste0("Expression (fr) chargé: ", nrow(rv$expression_fr_df), " entrées."))

            expr_session_df <- NULL
            add_expression_actif <- isTRUE(rv$utiliser_add_expression)
            if (isTRUE(add_expression_actif) && !is.null(rv$expression_annotations_df) && is.data.frame(rv$expression_annotations_df) && nrow(rv$expression_annotations_df) > 0) {
              expr_session_df <- rv$expression_annotations_df
              cols_need <- c("dic_mot", "dic_norm")
              if (all(cols_need %in% names(expr_session_df))) {
                expr_session_df <- expr_session_df[, cols_need, drop = FALSE]
                expr_session_df$dic_mot <- tolower(trimws(as.character(expr_session_df$dic_mot)))
                expr_session_df$dic_norm <- tolower(trimws(as.character(expr_session_df$dic_norm)))
                expr_session_df <- expr_session_df[nzchar(expr_session_df$dic_mot) & nzchar(expr_session_df$dic_norm), , drop = FALSE]
                expr_session_df <- expr_session_df[!duplicated(expr_session_df$dic_mot), , drop = FALSE]
              } else {
                expr_session_df <- NULL
              }
            }

            expressions_actives_df <- rv$expression_fr_df
            if (isTRUE(add_expression_actif) && !is.null(expr_session_df) && nrow(expr_session_df) > 0) {
              ajouter_log(rv, paste0("add_expression_fr.csv chargé: ", nrow(expr_session_df), " entrées."))
              deja_base <- expr_session_df$dic_mot %in% rv$expression_fr_df$dic_mot
              expr_session_ajouts <- expr_session_df[!deja_base, c("dic_mot", "dic_norm"), drop = FALSE]
              expressions_actives_df <- rbind(rv$expression_fr_df[, c("dic_mot", "dic_norm"), drop = FALSE], expr_session_ajouts)
              expressions_actives_df <- expressions_actives_df[!duplicated(expressions_actives_df$dic_mot), , drop = FALSE]
              ajouter_log(rv, paste0("Dictionnaire utilisateur ajouté au dictionnaire de base : +", nrow(expr_session_ajouts), " nouvelle(s) entrée(s) (", sum(deja_base), " déjà présentes ignorées)."))
            } else if (isTRUE(add_expression_actif)) {
              ajouter_log(rv, "add_expression_fr.csv activé mais vide/invalide ; utilisation du dictionnaire de base uniquement.")
            } else {
              ajouter_log(rv, "add_expression_fr.csv non activé ; utilisation du dictionnaire de base uniquement.")
            }
            rv$expressions_actives_df <- expressions_actives_df

            ajouter_log(
              rv,
              paste0(
                "Dictionnaire d'expressions chargé: ",
                nrow(expressions_actives_df),
                " entrées actives (base + ajouts utilisateur non présents dans la base).")
            )

            remplacements_expr <- appliquer_dictionnaire_expressions(textes_orig, expressions_actives_df)
            textes_orig <- remplacements_expr$textes
            ajouter_log(
              rv,
              paste0(
                "Dictionnaire d'expressions appliqué avant analyse : ",
                remplacements_expr$n_occurrences,
                " occurrence(s) remplacée(s) via ",
                remplacements_expr$n_patterns,
                " entrée(s) du dictionnaire (dic_mot -> dic_norm)."
              )
            )
            inclure_autre_forme_log <- identical(source_dictionnaire, "lexique_fr") &&
              (isTRUE(input$morpho_conserver_hors_lexique) || ("AUTRE_FORME" %in% toupper(trimws(as.character(input$pos_lexique_a_conserver)))))
            if (isTRUE(input$filtrage_morpho) && identical(source_dictionnaire, "lexique_fr") && !isTRUE(inclure_autre_forme_log)) {
              ajouter_log(rv, "Note: formes normalisées hors lexique (ex. gerald_darmanin) seront exclues si AUTRE_FORME n'est pas activé dans le filtrage morphosyntaxique.")
            }
          } else {
            rv$expressions_actives_df <- NULL
            ajouter_log(rv, "Dictionnaire d'expressions désactivé (expression_utiliser_dictionnaire=0).")
          }

          avancer(0.18, "Préparation texte (nettoyage / minuscules)")
          rv$statut <- "Préparation texte..."

          textes_nettoyes <- appliquer_nettoyage_iramuteq(
            textes = textes_orig,
            activer_nettoyage = isTRUE(input$nettoyage_caracteres),
            forcer_minuscules = TRUE,
            supprimer_chiffres = isTRUE(input$supprimer_chiffres),
            supprimer_apostrophes = isTRUE(input$supprimer_apostrophes),
            remplacer_tirets_espaces = isTRUE(input$remplacer_tirets_espaces)
          )

          textes_chd <- textes_nettoyes
          names(textes_chd) <- ids_corpus
          tokens_stats <- quanteda::tokens(
            textes_nettoyes,
            remove_punct = isTRUE(input$supprimer_ponctuation),
            remove_numbers = isTRUE(input$supprimer_chiffres),
            remove_symbols = TRUE,
            remove_separators = TRUE,
            split_hyphens = FALSE
          )
          stats_corpus <- calculer_stats_corpus(
            chemin_fichier = chemin_fichier,
            corpus_segments = corpus_stats,
            nom_corpus = input$fichier_corpus$name,
            tokens_stats = tokens_stats,
            remove_punct = isTRUE(input$supprimer_ponctuation),
            remove_numbers = isTRUE(input$supprimer_chiffres)
          )
          if (is.null(stats_corpus)) {
            rv$stats_corpus_df <- NULL
            rv$stats_zipf_df <- NULL
          } else {
            rv$stats_corpus_df <- stats_corpus$table
            rv$stats_zipf_df <- stats_corpus$zipf
          }
          ajouter_log(rv, "IRaMuTeQ-lite: préparation texte exécutée via iramuteqlite/nettoyage_iramuteq.R")
          ajouter_log(rv, "IRaMuTeQ-lite: paramètres CHD/DFM (min_docfreq, stopwords, ponctuation, dictionnaire) appliqués dans iramuteqlite/server_events_lancer_iramuteq.R")

          source_dictionnaire <- if (is.null(input$source_dictionnaire) || !nzchar(input$source_dictionnaire)) "lexique_fr" else as.character(input$source_dictionnaire)

          avancer(0.22, "Prétraitement + DFM")
          rv$statut <- "Prétraitement et DFM..."

          ajouter_log(
            rv,
            paste0(
              "Diagnostic pipeline: dictionnaire=", source_dictionnaire,
              " | langue UI=fr",
              " | filtrage_morpho=", ifelse(isTRUE(input$filtrage_morpho), "1", "0"),
              " | inclure_autre_forme=", ifelse(
                identical(source_dictionnaire, "lexique_fr") &&
                  (isTRUE(input$morpho_conserver_hors_lexique) || ("AUTRE_FORME" %in% toupper(trimws(as.character(input$pos_lexique_a_conserver))))) ,
                "1",
                "0"
              ),
              " | retirer_stopwords=", ifelse(isTRUE(input$retirer_stopwords), "1", "0"),
              " | supprimer_ponctuation=", ifelse(isTRUE(input$supprimer_ponctuation), "1", "0"),
              " | segmenter_sur_ponctuation_forte=", ifelse(isTRUE(input$segmenter_sur_ponctuation_forte), "1", "0"),
              " | supprimer_chiffres=", ifelse(isTRUE(input$supprimer_chiffres), "1", "0"),
              " | supprimer_apostrophes=", ifelse(isTRUE(input$supprimer_apostrophes), "1", "0"),
              " | remplacer_tirets_espaces=", ifelse(isTRUE(input$remplacer_tirets_espaces), "1", "0"),
              " | nettoyage_caracteres=", ifelse(isTRUE(input$nettoyage_caracteres), "1", "0")
            )
          )

          sortie_pipeline <- executer_pipeline_iramuteq(
            input = input,
            rv = rv,
            textes_chd = textes_chd
          )

          tok <- sortie_pipeline$tok
          dfm_obj <- sortie_pipeline$dfm_obj
          langue_reference <- sortie_pipeline$langue_reference
          source_dictionnaire <- sortie_pipeline$source_dictionnaire

          # Conserve les statistiques corpus calculées juste après segmentation,
          # afin d'afficher un "Nombre de mots dans le corpus" stable et
          # comparable au référentiel IRaMuTeQ. Le pipeline (stopwords,
          # lemmatisation, min_docfreq) reste appliqué uniquement à la CHD.
          n_tokens_pipeline <- length(unlist(tok, use.names = FALSE))
          ajouter_log(
            rv,
            paste0(
              "Nombre de mots conservés pour l'analyse après prétraitements : ",
              n_tokens_pipeline
            )
          )

          if (anyDuplicated(quanteda::docnames(dfm_obj)) > 0) {
            dups_dfm <- sum(duplicated(as.character(quanteda::docnames(dfm_obj))))
            quanteda::docnames(dfm_obj) <- make.unique(as.character(quanteda::docnames(dfm_obj)), sep = "_dup")
            ajouter_log(rv, paste0("DFM : docnames dupliqués détectés (", dups_dfm, "). Renommage automatique."))
          }

          included_segments <- as.character(quanteda::docnames(dfm_obj))
          included_segments <- included_segments[!is.na(included_segments) & nzchar(included_segments)]
          included_segments <- unique(included_segments)

          filtered_corpus <- corpus[included_segments]
          if (anyDuplicated(quanteda::docnames(filtered_corpus)) > 0) {
            dups_corpus <- sum(duplicated(as.character(quanteda::docnames(filtered_corpus))))
            quanteda::docnames(filtered_corpus) <- make.unique(as.character(quanteda::docnames(filtered_corpus)), sep = "_dup")
            ajouter_log(rv, paste0("Corpus filtré : docnames dupliqués détectés (", dups_corpus, "). Renommage automatique."))
          }

          tok <- tok[included_segments]
          if (anyDuplicated(quanteda::docnames(tok)) > 0) {
            dups_tok <- sum(duplicated(as.character(quanteda::docnames(tok))))
            quanteda::docnames(tok) <- make.unique(as.character(quanteda::docnames(tok)), sep = "_dup")
            ajouter_log(rv, paste0("Tokens : docnames dupliqués détectés (", dups_tok, "). Renommage automatique."))
          }

          segment_source <- as.character(quanteda::docnames(dfm_obj))
          if ("segment_source" %in% names(quanteda::docvars(filtered_corpus))) {
            ss <- as.character(quanteda::docvars(filtered_corpus)$segment_source)
            idx_ss <- match(as.character(quanteda::docnames(dfm_obj)), as.character(quanteda::docnames(filtered_corpus)))
            ss_aligne <- ss[idx_ss]
            ok_ss <- !is.na(ss_aligne) & nzchar(trimws(ss_aligne))
            segment_source[ok_ss] <- ss_aligne[ok_ss]
          }
          quanteda::docvars(dfm_obj, "segment_source") <- segment_source

          if (exists("supprimer_docs_vides_dfm", mode = "function", inherits = TRUE)) {
            res_docs <- supprimer_docs_vides_dfm(
              dfm_obj = dfm_obj,
              filtered_corpus = filtered_corpus,
              tok = tok,
              logger = function(msg) ajouter_log(rv, msg)
            )
            dfm_obj <- res_docs$dfm_obj
            filtered_corpus <- res_docs$filtered_corpus
            tok <- res_docs$tok
          } else {
            sommes_docs <- Matrix::rowSums(dfm_obj)
            idx_non_vides <- !is.na(sommes_docs) & (sommes_docs > 0)
            if (!any(idx_non_vides)) {
              stop("Le DFM ne contient aucun segment non vide après prétraitement.")
            }

            nb_vides <- sum(!idx_non_vides)
            if (nb_vides > 0) {
              ajouter_log(rv, paste0("Segments vides supprimés du DFM : ", nb_vides, "."))
            }

            dfm_obj <- dfm_obj[idx_non_vides, ]
            filtered_corpus <- filtered_corpus[idx_non_vides]
            tok <- tok[idx_non_vides]
          }

          ajouter_log(rv, paste0("Après suppression segments vides : ", quanteda::ndoc(dfm_obj), " docs ; ", quanteda::nfeat(dfm_obj), " termes."))

          rv$textes_indexation <- vapply(as.list(tok), function(x) paste(x, collapse = " "), FUN.VALUE = character(1))
          names(rv$textes_indexation) <- quanteda::docnames(dfm_obj)

          avancer(0.52, "Classification CHD IRaMuTeQ-lite")
          rv$statut <- "Classification en cours..."

          rv$res_type <- "iramuteq"
          ajouter_log(rv, "Mode : classification IRaMuTeQ-lite.")

          groupes <- NULL
          res_final <- NULL

          k_iramuteq <- suppressWarnings(as.integer(input$k_iramuteq))
          if (is.na(k_iramuteq) || k_iramuteq < 2L) k_iramuteq <- 10L

          mincl_mode_iramuteq <- as.character(input$iramuteq_mincl_mode)
          if (!mincl_mode_iramuteq %in% c("auto", "manuel")) mincl_mode_iramuteq <- "auto"

          mincl_iramuteq <- suppressWarnings(as.integer(input$iramuteq_mincl))
          if (is.na(mincl_iramuteq) || mincl_iramuteq < 1L) mincl_iramuteq <- 1L

          classif_mode_iramuteq <- as.character(input$iramuteq_classif_mode)
          if (!classif_mode_iramuteq %in% c("simple", "double")) classif_mode_iramuteq <- "simple"

          svd_method_iramuteq <- as.character(input$iramuteq_svd_method)
          if (!svd_method_iramuteq %in% c("irlba", "svdR")) svd_method_iramuteq <- "irlba"

          max_formes_iramuteq <- suppressWarnings(as.integer(input$iramuteq_max_formes))
          if (is.na(max_formes_iramuteq) || max_formes_iramuteq < 1L) max_formes_iramuteq <- 20000L

          stats_mode_iramuteq <- normaliser_mode_stats_chd_iramuteq(input$iramuteq_stats_mode)

          ajouter_log(
            rv,
            paste0(
              "Paramètres IRaMuTeQ-lite : k=", k_iramuteq,
              " | mincl_mode=", mincl_mode_iramuteq,
              if (identical(mincl_mode_iramuteq, "manuel")) paste0(" | mincl=", mincl_iramuteq) else "",
              " | classif_mode=", classif_mode_iramuteq,
              if (identical(classif_mode_iramuteq, "double")) paste0(" | rst1=", rst1_iramuteq, " | rst2=", rst2_iramuteq) else "",
              " | segmenter_sur_ponctuation_forte=", ifelse(isTRUE(input$segmenter_sur_ponctuation_forte), "1", "0"),
              " | svd_method=", svd_method_iramuteq,
              " | max_formes=", max_formes_iramuteq,
              " | stats_mode=", stats_mode_iramuteq
            )
          )

          res_ira <- lancer_moteur_chd_iramuteq(
            dfm_obj = dfm_obj,
            k = k_iramuteq,
            mincl_mode = mincl_mode_iramuteq,
            mincl = mincl_iramuteq,
            classif_mode = classif_mode_iramuteq,
            svd_method = svd_method_iramuteq,
            mode_patate = FALSE,
            binariser = TRUE,
            max_formes = max_formes_iramuteq
          )

          max_formes_info <- res_ira$max_formes_info
          if (is.list(max_formes_info) && all(c("max_formes", "n_feat_avant", "n_feat_apres") %in% names(max_formes_info))) {
            ajouter_log(
              rv,
              paste0(
                "Nombre maximum de formes analysées appliqué (chd_iramuteq.R) = ",
                max_formes_info$max_formes,
                " (",
                max_formes_info$n_feat_avant,
                " -> ",
                max_formes_info$n_feat_apres,
                ")."
              )
            )
          }

          if (!is.null(res_ira$dfm_utilise)) {
            dfm_obj <- res_ira$dfm_utilise
          }

          if (isTRUE(res_ira$fallback_mincl1)) {
            ajouter_log(
              rv,
              "Ajustement automatique: reconstruction des classes avec mincl=1 pour éviter une fusion excessive des classes terminales."
            )
          }

          groupes <- as.integer(res_ira$classes)
          if (all(is.na(groupes)) || length(unique(groupes[groupes > 0])) < 2) {
            stop("IRaMuTeQ-lite n'a pas pu produire au moins 2 classes exploitables.")
          }

          res_final <- res_ira
          rv$res_chd <- NULL
          rv$dfm_chd <- NULL
          rv$max_n_groups <- length(unique(groupes[groupes > 0]))
          rv$max_n_groups_chd <- rv$max_n_groups

          quanteda::docvars(filtered_corpus)$Classes <- groupes

          classes_calculees <- suppressWarnings(as.integer(quanteda::docvars(filtered_corpus)$Classes))
          idx_ok <- !is.na(classes_calculees) & classes_calculees > 0

          nb_non_assignes <- sum(!idx_ok)
          if (nb_non_assignes > 0) {
            ajouter_log(
              rv,
              paste0(
                "Segments non assignés à une classe terminale (Classe 0 / NA) : ",
                nb_non_assignes,
                ". Exclusion des calculs CHD/AFC."
              )
            )
          }
          filtered_corpus_ok <- filtered_corpus[idx_ok]
          dfm_ok <- dfm_obj[idx_ok, ]
          tok_ok <- tok[idx_ok]

          if (quanteda::ndoc(dfm_ok) < 2) stop("Après classification, il reste moins de 2 segments classés (hors NA).")
          if (quanteda::nfeat(dfm_ok) < 2) stop("Après classification, le DFM classé est trop pauvre (moins de 2 termes).")

          rv$clusters <- sort(unique(quanteda::docvars(filtered_corpus_ok)$Classes))
          rv$res <- res_final
          rv$dfm <- dfm_ok
          rv$filtered_corpus <- filtered_corpus_ok
          rv$res_stats_df <- NULL

          if (!is.null(rv$expressions_actives_df) && is.data.frame(rv$expressions_actives_df) && nrow(rv$expressions_actives_df) > 0 && "dic_norm" %in% names(rv$expressions_actives_df)) {
            expr_norm <- unique(tolower(trimws(as.character(rv$expressions_actives_df$dic_norm))))
            expr_norm <- expr_norm[nzchar(expr_norm)]
            if (length(expr_norm) > 0) {
              feats_ok <- tolower(trimws(as.character(quanteda::featnames(dfm_ok))))
              expr_dans_dfm_ok <- intersect(expr_norm, feats_ok)
              ajouter_log(
                rv,
                paste0(
                  "Expressions (dic_norm) conservées dans le DFM final CHD/AFC : ",
                  length(expr_dans_dfm_ok),
                  "/",
                  length(expr_norm),
                  "."
                )
              )
            }
          }

          avancer(0.58, "Finalisation du pipeline")
          rv$statut <- "Finalisation du pipeline..."

          avancer(0.62, "Exports + stats")
          rv$statut <- "Exports et statistiques..."

          segments_vec <- as.character(filtered_corpus_ok)
          ids_segments <- as.character(quanteda::docnames(filtered_corpus_ok))
          names(segments_vec) <- ids_segments
          if (!is.null(textes_chd) && length(textes_chd) > 0) {
            idx_chd <- match(ids_segments, names(textes_chd))
            ok_chd <- !is.na(idx_chd)
            if (any(ok_chd)) {
              segments_vec[ok_chd] <- as.character(textes_chd[idx_chd[ok_chd]])
            }
          }
          segments_by_class <- split(segments_vec, quanteda::docvars(filtered_corpus_ok)$Classes)

          segments_file <- file.path(rv$export_dir, "segments_par_classe.txt")
          writeLines(unlist(lapply(names(segments_by_class), function(cl) c(paste0("Classe ", cl, ":"), unname(segments_by_class[[cl]]), ""))), segments_file)

          ajouter_log(rv, "Statistiques CHD : calcul IRaMuTeQ-lite (contingence classe × terme).")
          res_stats_df <- construire_stats_classes_iramuteq(
            dfm_obj = dfm_ok,
            classes = quanteda::docvars(filtered_corpus_ok)$Classes,
            max_p = 1,
            stats_mode = stats_mode_iramuteq
          )
          res_stats_df$Classe <- normaliser_id_classe_local(res_stats_df$Classe)
          ord_stats <- with(
            res_stats_df,
            order(
              suppressWarnings(as.integer(Classe)),
              -suppressWarnings(as.numeric(chi2)),
              na.last = TRUE
            )
          )
          res_stats_df <- res_stats_df[ord_stats, , drop = FALSE]

          if (identical(source_dictionnaire, "lexique_fr") &&
              "Terme" %in% names(res_stats_df) &&
              exists("construire_type_lexique_fr", mode = "function", inherits = TRUE)) {
            if (is.null(rv$lexique_fr_df) || !is.data.frame(rv$lexique_fr_df) || nrow(rv$lexique_fr_df) == 0) {
              rv$lexique_fr_df <- charger_lexique_fr(app_dir)
              ajouter_log(rv, paste0("Lexique (fr) chargé pour typer les termes CHD: ", nrow(rv$lexique_fr_df), " entrées."))
            }
            res_stats_df$Type <- construire_type_lexique_fr(res_stats_df$Terme, rv$lexique_fr_df)
          }

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

          filtrer_affichage_pvalue <- isTRUE(input$filtrer_affichage_pvalue)

          termes_signif <- NULL
          if (isTRUE(filtrer_affichage_pvalue)) {
            termes_signif <- unique(subset(res_stats_df, p <= input$max_p)$Terme)
            termes_signif <- termes_signif[!is.na(termes_signif) & nzchar(termes_signif)]
            if (length(termes_signif) < 2) termes_signif <- NULL
          }

          tryCatch({
            groupes_docs <- quanteda::docvars(filtered_corpus_ok)$Classes

            obj <- executer_afc_classes(
              dfm_obj = dfm_ok,
              groupes = groupes_docs,
              termes_cibles = termes_signif,
              max_termes = 400,
              seuil_p = if (isTRUE(filtrer_affichage_pvalue)) input$max_p else 1,
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
                suffixes = c("_global", "_stats")
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

            obj$termes_stats <- tryCatch(
              construire_segments_exemples_afc(
                termes_stats = obj$termes_stats,
                dfm_obj = dfm_ok,
                corpus_obj = filtered_corpus_ok
              ),
              error = function(e_seg) {
                ajouter_log(rv, paste0("AFC classes × termes : enrichissement des segments ignoré (", e_seg$message, ")."))
                obj$termes_stats
              }
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
            if (!is.null(quanteda::docvars(filtered_corpus_ok)$Classes)) {
              objv <- executer_afc_variables_etoilees(
                corpus_aligne = filtered_corpus_ok,
                groupes = quanteda::docvars(filtered_corpus_ok)$Classes,
                max_modalites = 400,
                seuil_p = if (isTRUE(filtrer_affichage_pvalue)) input$max_p else 1,
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
            taille_sel_input <- as.character(input$afc_taille_mots)
            if (length(taille_sel_input) > 0 && !is.na(taille_sel_input[[1]]) && nzchar(taille_sel_input[[1]])) {
              taille_sel <- taille_sel_input[[1]]
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
          textes_index_ok <- rv$textes_indexation[quanteda::docnames(dfm_ok)]
          names(textes_index_ok) <- quanteda::docnames(dfm_ok)

          wordcloud_dir <- file.path(rv$export_dir, "wordclouds")
          dir.create(wordcloud_dir, showWarnings = FALSE, recursive = TRUE)
          anciens_wordclouds <- list.files(
            wordcloud_dir,
            pattern = "^cluster_[0-9]+_wordcloud\\.png$",
            full.names = TRUE
          )
          if (length(anciens_wordclouds) > 0) {
            suppressWarnings(unlink(anciens_wordclouds, force = TRUE))
          }
          cooc_dir <- file.path(rv$export_dir, "cooccurrences")
          dir.create(cooc_dir, showWarnings = FALSE, recursive = TRUE)

          classes_uniques <- sort(unique(as.integer(quanteda::docvars(filtered_corpus_ok)$Classes)))
          classes_uniques <- classes_uniques[is.finite(classes_uniques)]

          if (!identical(rv$res_type, "iramuteq")) {
            top_n_demande <- lire_top_n_wordcloud(input$top_n)
            for (cl in classes_uniques) {

            if (isTRUE(input$filtrer_affichage_pvalue)) {
              df_stats_cl <- subset(res_stats_df, Classe == cl & p <= input$max_p)
            } else {
              df_stats_cl <- subset(res_stats_df, Classe == cl)
            }
            if (nrow(df_stats_cl) > 0) {
              df_stats_cl <- df_stats_cl[order(-df_stats_cl$chi2), , drop = FALSE]
              df_stats_cl <- head(df_stats_cl, top_n_demande)

              wc_png <- file.path(wordcloud_dir, paste0("cluster_", cl, "_wordcloud.png"))
              try({
                png(wc_png, width = 800, height = 600)
                suppressWarnings(wordcloud(
                  words = df_stats_cl$Terme,
                  freq = df_stats_cl$chi2,
                  scale = c(8, 0.8),
                  min.freq = 0,
                  random.order = FALSE,
                  rot.per = 0,
                  max.words = nrow(df_stats_cl),
                  colors = brewer.pal(8, "Dark2")
                ))
                dev.off()
              }, silent = TRUE)
            }

            }

            # Cooccurrences Explor retirées du pipeline IRaMuTeQ-lite.
          } else {
            generer_wordclouds_iramuteq(
              res_stats_df = res_stats_df,
              classes_uniques = classes_uniques,
              wordcloud_dir = wordcloud_dir,
              top_n = lire_top_n_wordcloud(input$top_n),
              filtrer_pvalue = isTRUE(input$filtrer_affichage_pvalue),
              max_p = input$max_p
            )
            ajouter_log(rv, "Mode IRaMuTeQ-lite : nuages de mots générés via wordcloud_iramuteq.R.")
          }

          rv$wordcloud_refresh_token <- rv$wordcloud_refresh_token + 1

          explor_assets <- NULL
          ok_chd_png <- FALSE

          chd_png_rel <- NULL
          chd_html_rel <- NULL

          chd_png <- file.path(rv$export_dir, "dendrogramme_chd.png")
          ok_chd_png <- tryCatch({
            png(chd_png, width = 2200, height = 1500, res = 200)
            on.exit(try(dev.off(), silent = TRUE), add = TRUE)
            tracer_dendrogramme_iramuteq_ui(
              rv = rv,
              top_n_terms = 4,
              orientation = "horizontal",
              style_affichage = input$chd_dendro_style %||% "iramuteq_bars"
            )
            TRUE
          }, error = function(e) {
            ajouter_log(rv, paste0("Export dendrogramme PNG : ", e$message))
            FALSE
          })

          if (isTRUE(ok_chd_png) && file.exists(chd_png)) {
            chd_png_rel <- basename(chd_png)
          }

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

          coocs_df <- data.frame(classe = character(0), src = character(0), stringsAsFactors = FALSE)

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
            max_p = if (isTRUE(input$filtrer_affichage_pvalue)) input$max_p else 1,
            filtrer_pvalue = isTRUE(input$filtrer_affichage_pvalue),
            textes_indexation = textes_index_ok,
            spacy_tokens_df = rv$spacy_tokens_df,
            lexique_fr_df = rv$lexique_fr_df,
            source_dictionnaire = source_dictionnaire,
            avancer = avancer,
            rv = rv
          )

          # Priorité explicite au concordancier IRaMuTeQ-lite lorsque le mode
          # IRaMuTeQ est sélectionné dans l'UI (même si rv$res_type est désynchronisé).
          mode_iramuteq_actif <- identical(as.character(input$modele_chd), "iramuteq") ||
            identical(rv$res_type, "iramuteq")

          fonction_concordancier <- if (isTRUE(mode_iramuteq_actif)) {
            generer_concordancier_iramuteq_html
          } else {
            generer_concordancier_iramuteq_html
          }

          html_genere <- do.call(fonction_concordancier, args_concordancier)

          candidats_html <- unique(c(
            html_genere,
            html_file,
            file.path(rv$export_dir, "concordancier.html")
          ))
          candidats_html <- candidats_html[is.character(candidats_html) & !is.na(candidats_html) & nzchar(candidats_html)]
          html_existants <- candidats_html[file.exists(candidats_html)]

          if (length(html_existants) == 0) {
            html_fallback <- file.path(rv$export_dir, "concordancier.html")
            args_concordancier$chemin_sortie <- html_fallback
            ajouter_log(rv, "Concordancier HTML introuvable après la première génération. Nouvelle tentative vers exports/concordancier.html.")
            html_retry <- tryCatch(
              do.call(fonction_concordancier, args_concordancier),
              error = function(e) {
                ajouter_log(rv, paste0("Concordancier HTML : échec de la relance - ", e$message))
                NA_character_
              }
            )

            candidats_retry <- unique(c(html_retry, html_fallback, html_genere, html_file))
            candidats_retry <- candidats_retry[is.character(candidats_retry) & !is.na(candidats_retry) & nzchar(candidats_retry)]
            html_existants <- candidats_retry[file.exists(candidats_retry)]
          }

          if (length(html_existants) == 0 && !is.null(rv$afc_table_mots) && nrow(rv$afc_table_mots) > 0) {
            html_afc_fallback <- file.path(rv$export_dir, "concordancier_afc.html")
            ajouter_log(rv, "Concordancier HTML indisponible : tentative de fallback avec le concordancier AFC.")
            html_afc_genere <- tryCatch(
              generer_concordancier_afc_html(
                chemin_sortie = html_afc_fallback,
                afc_table_mots = rv$afc_table_mots,
                rv = rv,
                max_lignes_par_classe = 100
              ),
              error = function(e) {
                ajouter_log(rv, paste0("Concordancier AFC : échec - ", e$message))
                NA_character_
              }
            )

            candidats_afc <- unique(c(html_afc_genere, html_afc_fallback))
            candidats_afc <- candidats_afc[is.character(candidats_afc) & !is.na(candidats_afc) & nzchar(candidats_afc)]
            html_existants <- candidats_afc[file.exists(candidats_afc)]
          }

          if (length(html_existants) > 0) {
            rv$html_file <- html_existants[[1]]
            ajouter_log(rv, paste0("Concordancier HTML validé : ", rv$html_file))
          } else {
            html_diag <- file.path(rv$export_dir, "concordancier.html")
            diag_lines <- c(
              "<html><head><meta charset='utf-8'/>",
              "<style>body{font-family:Arial,sans-serif;line-height:1.5;padding:1rem 1.2rem;} code{background:#f7f7f7;padding:.1rem .3rem;border-radius:3px;}</style>",
              "</head><body>",
              "<h2>Concordancier indisponible</h2>",
              "<p>Le concordancier HTML n'a pas pu être généré automatiquement pour cette analyse.</p>",
              "<p>Vérifier le journal de l'analyse puis relance si nécessaire.</p>",
              paste0("<p><strong>Dossier d'exports :</strong> <code>", htmltools::htmlEscape(rv$export_dir), "</code></p>"),
              "</body></html>"
            )

            ok_diag <- tryCatch({
              writeLines(diag_lines, html_diag, useBytes = TRUE)
              file.exists(html_diag)
            }, error = function(e) {
              ajouter_log(rv, paste0("Concordancier HTML : impossible d'écrire le fichier de diagnostic - ", e$message))
              FALSE
            })

            rv$html_file <- if (isTRUE(ok_diag)) html_diag else html_file
            if (isTRUE(ok_diag)) {
              ajouter_log(rv, "Concordancier HTML introuvable après relance. Fichier de diagnostic généré dans exports/concordancier.html.")
            } else {
              ajouter_log(rv, "Concordancier HTML introuvable après relance. Vérifier les logs de génération du concordancier.")
            }
          }

          avancer(0.96, "ZIP")
          rv$statut <- "Création ZIP..."
          rv$zip_file <- file.path(rv$base_dir, "exports_iramuteq.zip")
          if (file.exists(rv$zip_file)) unlink(rv$zip_file)

          ancien_wd <- getwd()
          on.exit(setwd(ancien_wd), add = TRUE)
          setwd(rv$base_dir)
          utils::zip(zipfile = rv$zip_file, files = "exports")
          setwd(ancien_wd)

          exports_prefix <- as.character(rv$exports_prefix)
          if (length(exports_prefix) > 1) exports_prefix <- exports_prefix[[1]]
          if (!length(exports_prefix) || is.na(exports_prefix) || !nzchar(exports_prefix)) {
            # Fallback robuste: évite une erreur "missing value where TRUE/FALSE needed"
            # lorsque le token de session est indisponible.
            exports_prefix <- paste0("exports_", format(Sys.time(), "%Y%m%d%H%M%S"))
            rv$exports_prefix <- exports_prefix
          }

          if (!(exports_prefix %in% names(shiny::resourcePaths()))) {
            shiny::addResourcePath(exports_prefix, rv$export_dir)
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
}
