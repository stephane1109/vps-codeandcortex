# Comparaison exhaustive du découpage optimisé avec le découpage précédent.
# Les textes, les identifiants et les variables étoilées doivent rester identiques.
# L'ancienne fonction est conservée ci-dessous pour éviter une comparaison
# dépendant d'un dépôt externe ou de l'historique Git.

if (!requireNamespace("quanteda", quietly = TRUE)) {
  stop("Le package quanteda est nécessaire aux tests de segmentation.")
}
source(file.path("backend", "r", "pipeline_corpus.R"))

segmenter_reference_avant_optimisation <- function(corpus,
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
      if (!length(tok)) next

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
          candidates[[length(candidates) + 1L]] <- list(pos = idx_tok, count = non_punct_count, rank = boundary_rank)
        }
        list(candidates = candidates, non_punct_count = non_punct_count)
      }

      choose_boundary <- function(candidates, target_size) {
        if (!length(candidates)) return(NULL)
        min_count <- max(1L, floor(target_size * 0.5))
        cand_ok <- Filter(function(x) x$count >= min_count, candidates)
        if (!length(cand_ok)) cand_ok <- candidates
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
      if (!length(tok)) next
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

  if (!length(out_text)) stop("Segmentation impossible : aucun segment généré.")

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


# Corpus de référence contenant les différentes ponctuations et retours à la ligne.
textes_test <- c(
  paste(rep("Des lycéens manifestent. La police intervient, puis la foule se disperse !", 8L), collapse = " "),
  paste(rep("Une question ? Des réponses : oui ; non, peut-être... encore.", 8L), collapse = " "),
  paste(rep("Concert, scène, journaliste, spectateurs et téléphones.", 10L), collapse = "\n"),
  "\n\nPremière phrase.\nSeconde phrase !\n\nTroisième phrase ?",
  "., ; : ! ? ...",
  "Un seul mot",
  "12 34 56. Exemple de ponctuation suivie de 78.",
  paste(rep("mot", 110L), collapse = " ")
)
corpus_test <- quanteda::corpus(
  data.frame(doc_id = paste0("doc_", seq_along(textes_test)), text = textes_test, stringsAsFactors = FALSE),
  text_field = "text"
)
quanteda::docvars(corpus_test, "*profil") <- paste0("media_", seq_along(textes_test))
quanteda::docvars(corpus_test, "*annee") <- rep(c("2025", "2026"), length.out = length(textes_test))
quanteda::docvars(corpus_test, "*id") <- as.character(seq_along(textes_test))

comparer_segments <- function(taille, ponctuation, chiffres, forte) {
  arguments <- list(
    corpus = corpus_test,
    segment_size = taille,
    remove_punct = ponctuation,
    remove_numbers = chiffres,
    force_split_on_strong_punct = forte
  )
  reference <- do.call(segmenter_reference_avant_optimisation, arguments)
  optimise <- do.call(split_segments, arguments)

  stopifnot(identical(as.character(optimise), as.character(reference)))
  stopifnot(identical(quanteda::docnames(optimise), quanteda::docnames(reference)))
  stopifnot(identical(
    as.data.frame(quanteda::docvars(optimise)),
    as.data.frame(quanteda::docvars(reference))
  ))
  invisible(TRUE)
}

for (taille in c(1L, 2L, 5L, 12L, 40L, 60L)) {
  for (forte in c(FALSE, TRUE)) {
    for (ponctuation in c(FALSE, TRUE)) {
      for (chiffres in c(FALSE, TRUE)) {
        comparer_segments(taille, ponctuation, chiffres, forte)
      }
    }
  }
}

# Contrôler la double RST sans modifier sa fonction ni les valeurs RST1 et RST2.
for (forte in c(FALSE, TRUE)) {
  for (ponctuation in c(FALSE, TRUE)) {
    double_optimise <- split_segments_double_rst(
      corpus_test,
      rst1 = 12L,
      rst2 = 14L,
      remove_punct = ponctuation,
      remove_numbers = FALSE,
      force_split_on_strong_punct = forte
    )
    rst1_reference <- segmenter_reference_avant_optimisation(
      corpus_test, segment_size = 12L,
      remove_punct = ponctuation,
      force_split_on_strong_punct = forte
    )
    rst2_reference <- segmenter_reference_avant_optimisation(
      corpus_test, segment_size = 14L,
      remove_punct = ponctuation,
      force_split_on_strong_punct = forte
    )
    stopifnot(identical(
      as.character(double_optimise),
      c(as.character(rst1_reference), as.character(rst2_reference))
    ))
    stopifnot(identical(
      quanteda::docvars(double_optimise, "rst_source"),
      c(rep("rst1", quanteda::ndoc(rst1_reference)),
        rep("rst2", quanteda::ndoc(rst2_reference)))
    ))
    stopifnot(identical(
      quanteda::docvars(double_optimise, "*profil"),
      c(quanteda::docvars(rst1_reference, "*profil"),
        quanteda::docvars(rst2_reference, "*profil"))
    ))
  }
}

cat("Segmentation optimisée : textes, identifiants et métadonnées identiques à la référence.\n")


# Les mêmes résultats doivent être obtenus de part et d'autre de 512 documents.
corpus_lots <- quanteda::corpus(
  data.frame(
    doc_id = paste0("lot_", seq_len(515L)),
    text = rep("Une scène est filmée. La foule manifeste, puis elle repart !", 515L),
    stringsAsFactors = FALSE
  ),
  text_field = "text"
)
quanteda::docvars(corpus_lots, "*profil") <- rep("presse", 515L)

for (forte in c(FALSE, TRUE)) {
  arguments_lots <- list(
    corpus = corpus_lots,
    segment_size = 12L,
    remove_punct = TRUE,
    remove_numbers = TRUE,
    force_split_on_strong_punct = forte
  )
  ancien <- do.call(segmenter_reference_avant_optimisation, arguments_lots)
  nouveau <- do.call(split_segments, arguments_lots)
  stopifnot(identical(as.character(nouveau), as.character(ancien)))
  stopifnot(identical(quanteda::docnames(nouveau), quanteda::docnames(ancien)))
  stopifnot(identical(as.data.frame(quanteda::docvars(nouveau)),
                      as.data.frame(quanteda::docvars(ancien))))
  durees <- attr(nouveau, "durees_segmentation")
  stopifnot(all(c("tokenisation", "decoupage", "assemblage") %in% names(durees)))
  stopifnot(all(is.finite(durees) & durees >= 0))
}
cat("Tokenisation par lots et mesures de durée : comparaisons conformes.\n")
