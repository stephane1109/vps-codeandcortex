#!/usr/bin/env Rscript

options(
  stringsAsFactors = FALSE,
  bspm.sudo = TRUE
)

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript launch_shiny_explorer.R <analysis_bundle.rds> <port> [host]")
}

bundle_path <- normalizePath(args[[1]], winslash = "/", mustWork = TRUE)
port <- suppressWarnings(as.integer(args[[2]]))
host <- if (length(args) >= 3) as.character(args[[3]]) else "127.0.0.1"

if (!is.finite(port) || is.na(port) || port < 1) {
  stop("Port Shiny invalide.")
}

source(file.path(getwd(), "backend", "shiny_explorer_app.R"), encoding = "UTF-8", local = TRUE)

app <- build_shiny_explorer_app(bundle_path)

options(
  shiny.host = host,
  shiny.port = port,
  shiny.launch.browser = FALSE
)

shiny::runApp(
  app,
  host = host,
  port = port,
  launch.browser = FALSE
)
