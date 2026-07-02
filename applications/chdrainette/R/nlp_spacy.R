# Module NLP - exécution spaCy (filtrage POS et NER)
# Ce fichier encapsule les appels aux scripts Python externes (`spacy_preprocess.py`
# et `ner.py`) pour produire le texte filtré (tokens/POS/lemmes) et les entités nommées.

executer_spacy_filtrage <- function(ids, textes, pos_a_conserver, utiliser_lemmes, lower_input, modele_spacy, rv) {
  script_spacy <- tryCatch(normalizePath("spacy_preprocess.py", mustWork = TRUE), error = function(e) NA_character_)
  if (is.na(script_spacy) || !file.exists(script_spacy)) stop("Script spaCy introuvable : spacy_preprocess.py (à la racine du projet).")

  python_cmd <- "python3"

  in_tsv <- file.path(tempdir(), paste0("spacy_in_", Sys.getpid(), ".tsv"))
  out_tsv <- file.path(tempdir(), paste0("spacy_out_", Sys.getpid(), ".tsv"))
  tok_tsv <- file.path(tempdir(), paste0("spacy_tokens_", Sys.getpid(), ".tsv"))

  df_in <- data.frame(doc_id = ids, text = textes, stringsAsFactors = FALSE)

  write.table(
    df_in, file = in_tsv, sep = "\t", quote = FALSE,
    row.names = FALSE, col.names = TRUE, fileEncoding = "UTF-8"
  )

  if (is.null(pos_a_conserver) || length(pos_a_conserver) == 0) pos_a_conserver <- c("NOUN", "ADJ")

  args <- c(
    script_spacy,
    "--input", in_tsv,
    "--output", out_tsv,
    "--modele", modele_spacy,
    "--pos_keep", paste(pos_a_conserver, collapse = ","),
    "--lemmes", ifelse(isTRUE(utiliser_lemmes), "1", "0"),
    "--lower_input", ifelse(isTRUE(lower_input), "1", "0"),
    "--output_tokens", tok_tsv
  )

  ajouter_log(rv, paste0("spaCy : exécution (", python_cmd, " ", paste(args, collapse = " "), ")"))

  sortie <- tryCatch(system2(python_cmd, args = args, stdout = TRUE, stderr = TRUE), error = function(e) stop("Erreur exécution spaCy : ", e$message))
  if (!is.null(sortie) && length(sortie) > 0) ajouter_log(rv, paste(sortie, collapse = "\n"))

  if (!file.exists(out_tsv)) stop("spaCy n'a pas produit de fichier de sortie.")

  df_out <- read.delim(out_tsv, sep = "\t", stringsAsFactors = FALSE, quote = "", fileEncoding = "UTF-8")
  if (!all(c("doc_id", "text") %in% names(df_out))) stop("Sortie spaCy invalide : colonnes attendues 'doc_id' et 'text'.")

  df_tok <- NULL
  if (file.exists(tok_tsv)) {
    df_tok <- read.delim(tok_tsv, sep = "\t", stringsAsFactors = FALSE, quote = "", fileEncoding = "UTF-8")
    colonnes_attendues <- c("doc_id", "token", "lemma", "pos")
    if (!all(colonnes_attendues %in% names(df_tok))) df_tok <- NULL
  }

  res <- setNames(df_out$text, df_out$doc_id)
  list(textes = res[ids], tokens_df = df_tok)
}

executer_spacy_ner <- function(ids, textes, modele_spacy, rv) {
  script_ner <- tryCatch(normalizePath("ner.py", mustWork = TRUE), error = function(e) NA_character_)
  if (is.na(script_ner) || !file.exists(script_ner)) stop("Script NER introuvable : ner.py (à la racine du projet).")

  python_cmd <- "python3"

  in_tsv <- file.path(tempdir(), paste0("ner_in_", Sys.getpid(), ".tsv"))
  out_tsv <- file.path(tempdir(), paste0("ner_out_", Sys.getpid(), ".tsv"))

  df_in <- data.frame(doc_id = ids, text = textes, stringsAsFactors = FALSE)

  write.table(
    df_in, file = in_tsv, sep = "\t", quote = FALSE,
    row.names = FALSE, col.names = TRUE, fileEncoding = "UTF-8"
  )

  args <- c(
    script_ner,
    "--input", in_tsv,
    "--output", out_tsv,
    "--modele", modele_spacy
  )

  ajouter_log(rv, paste0("NER : exécution (", python_cmd, " ", paste(args, collapse = " "), ")"))

  sortie <- tryCatch(system2(python_cmd, args = args, stdout = TRUE, stderr = TRUE), error = function(e) stop("Erreur exécution NER : ", e$message))
  if (!is.null(sortie) && length(sortie) > 0) ajouter_log(rv, paste(sortie, collapse = "\n"))

  if (!file.exists(out_tsv)) stop("NER n'a pas produit de fichier de sortie.")

  df_ent <- read.delim(out_tsv, sep = "\t", stringsAsFactors = FALSE, quote = "", fileEncoding = "UTF-8")
  colonnes_attendues <- c("doc_id", "ent_text", "ent_label", "start_char", "end_char")
  if (!all(colonnes_attendues %in% names(df_ent))) stop("Sortie NER invalide : colonnes attendues 'doc_id, ent_text, ent_label, start_char, end_char'.")

  df_ent$doc_id <- trimws(as.character(df_ent$doc_id))
  df_ent$ent_text <- trimws(gsub("\\s+", " ", as.character(df_ent$ent_text), perl = TRUE))
  df_ent$ent_label <- as.character(df_ent$ent_label)
  df_ent <- df_ent[!is.na(df_ent$ent_text) & nzchar(df_ent$ent_text), , drop = FALSE]
  df_ent
}
