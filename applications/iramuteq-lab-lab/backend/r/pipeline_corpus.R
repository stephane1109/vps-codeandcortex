# Importation et segmentation des corpus IRAMUTEQ Lab.
# Les fonctions sont extraites sans modification de leur comportement.

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
      tokens_entete <- extraire_tokens_entete_iramuteq(entete)
      debut <- idx[[i]] + 1L
      fin <- bornes[[i + 1L]] - 1L
      contenu <- if (debut <= fin) lignes[debut:fin] else character(0)
      contenu <- trimws(contenu)
      contenu <- contenu[nzchar(contenu)]
      if (!length(contenu)) next
      textes <- c(textes, paste(contenu, collapse = " "))
      ids <- c(ids, paste0("doc_", i))
      etoiles_par_doc[[length(etoiles_par_doc) + 1L]] <- tokens_entete
    }
  } else {
    lignes2 <- trimws(lignes)
    lignes2 <- lignes2[nzchar(lignes2)]
    textes <- lignes2
    ids <- paste0("doc_", seq_along(textes))
    etoiles_par_doc <- rep(list(character(0)), length(textes))
  }

  if (!length(textes)) stop("Corpus vide : aucune unite de texte detectee.")

  base_df <- data.frame(doc_id = ids, text = textes, stringsAsFactors = FALSE)
  noms_etoiles <- unique(unlist(lapply(etoiles_par_doc, function(tok) {
    tok <- tok[!is.na(tok) & nzchar(tok)]
    if (!length(tok)) return(character(0))
    sous <- sub("^\\*", "", tok)
    sous <- sub("_.*$", "", sous)
    sous <- sous[nzchar(sous)]
    paste0("*", sous)
  }), use.names = FALSE))

  if (length(noms_etoiles)) {
    for (cn in noms_etoiles) base_df[[cn]] <- NA_character_
    for (i in seq_along(etoiles_par_doc)) {
      toks <- etoiles_par_doc[[i]]
      if (!length(toks)) next
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

split_segments_double_rst <- function(corpus,
                                      rst1 = 12,
                                      rst2 = 14,
                                      remove_punct = FALSE,
                                      remove_numbers = FALSE,
                                      force_split_on_strong_punct = FALSE) {
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
  corp_out <- quanteda::corpus(
    data.frame(doc_id = c(id1, id2), text = c(txt1, txt2), stringsAsFactors = FALSE),
    text_field = "text"
  )
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
