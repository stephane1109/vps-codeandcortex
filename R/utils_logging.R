horodater <- function() format(Sys.time(), "%Y-%m-%d %H:%M:%S")

normaliser_niveau_log <- function(niveau = "info") {
  niveau <- trimws(tolower(as.character(niveau %||% "info")))
  if (!niveau %in% c("info", "debug", "warn", "error", "step")) {
    niveau <- "info"
  }
  niveau
}

ajouter_log <- function(rv, texte, niveau = "info") {
  niveau <- normaliser_niveau_log(niveau)
  prefixe <- paste0("[", niveau, "]")
  rv$logs <- paste(rv$logs, paste0("[", horodater(), "] ", prefixe, " ", texte), sep = "\n")
}

ajouter_log_debug <- function(rv, texte) {
  if (!is.null(rv$debug_mode) && isTRUE(rv$debug_mode)) {
    ajouter_log(rv, texte, niveau = "debug")
  }
}

ajouter_etape <- function(rv, texte) {
  ajouter_log(rv, texte, niveau = "step")
}
