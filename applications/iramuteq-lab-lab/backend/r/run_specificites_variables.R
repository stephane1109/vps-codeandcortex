#!/usr/bin/env Rscript
# Exécution indépendante du calcul historique de spécificité par terme.

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 4L) stop("Arguments requis : source.rds, variable, indice, sortie.")
source_path <- normalizePath(args[[1L]], mustWork = TRUE)
variable <- args[[2L]]
indice <- args[[3L]]
repertoire <- args[[4L]]
script_path <- sub("^--file=", "", grep("^--file=", commandArgs(FALSE), value = TRUE)[[1L]])
racine <- normalizePath(file.path(dirname(script_path), "..", ".."), mustWork = TRUE)
source(file.path(racine, "iramuteqlite", "calcul_specificites.R"), local = TRUE)
source(file.path(racine, "iramuteqlite", "specifilexicalevariables.R"), local = TRUE)
resultat <- ecrire_specificites_lexicales_variables(
  readRDS(source_path), variable, indice, repertoire)
cat(jsonlite::toJSON(resultat$summary, auto_unbox = TRUE, null = "null"))
