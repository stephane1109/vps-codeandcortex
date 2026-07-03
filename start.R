options(
  repos = c(CRAN = Sys.getenv("R_CRAN_MIRROR", unset = "https://cloud.r-project.org")),
  bspm.sudo = TRUE
)

port <- suppressWarnings(as.integer(Sys.getenv("PORT", "8000")))
if (!is.finite(port) || is.na(port) || port < 1) {
  port <- 8000L
}

shiny::runApp(
  appDir = normalizePath(getwd(), winslash = "/", mustWork = TRUE),
  host = "0.0.0.0",
  port = port,
  launch.browser = FALSE
)
