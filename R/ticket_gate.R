ticket_env_int <- function(name, default) {
  value <- suppressWarnings(as.integer(Sys.getenv(name, unset = as.character(default))))
  if (is.na(value)) {
    return(default)
  }
  value
}


ticket_env_bool <- function(name, default) {
  value <- Sys.getenv(name, unset = "")
  if (!nzchar(value)) {
    return(default)
  }
  !(tolower(trimws(value)) %in% c("0", "false", "no", "off"))
}


ticket_mask_redis_url <- function(value) {
  if (is.null(value) || !nzchar(trimws(value))) {
    return("(absente)")
  }
  sub("://([^@/]+)@", "://***@", trimws(value))
}


ticket_first_diagnostic_line <- function(value, fallback = "Diagnostic Redis indisponible.") {
  text <- trimws(value %||% "")
  if (!nzchar(text)) {
    return(fallback)
  }
  lines <- trimws(strsplit(text, "\n", fixed = TRUE)[[1]])
  lines <- lines[nzchar(lines)]
  if (!length(lines)) {
    return(fallback)
  }
  lines[[1]]
}


ticket_runtime_diagnostic <- function(cfg, base_message = "") {
  redis_url <- trimws(Sys.getenv("REDIS_URL", unset = ""))
  redis_cli <- Sys.which("redis-cli")
  python3 <- Sys.which("python3")
  redis_helper <- ticket_redis_helper_path()
  details <- c(
    if (nzchar(trimws(base_message))) trimws(base_message),
    sprintf("APP_TICKET_ID=%s", cfg$app_id),
    sprintf("REDIS_URL=%s", ticket_mask_redis_url(redis_url)),
    sprintf("python3=%s", if (nzchar(python3)) python3 else "(absent)"),
    sprintf("redis-helper=%s", if (file.exists(redis_helper)) redis_helper else sprintf("(absent: %s)", redis_helper)),
    sprintf("redis-cli=%s", if (nzchar(redis_cli)) redis_cli else "(absent)"),
    sprintf("APP_TICKET_ENFORCED=%s", if (isTRUE(cfg$enabled)) "1" else "0")
  )
  paste(details, collapse = "\n")
}


ticket_random_id <- function(length = 32L) {
  alphabet <- c(letters[1:6], as.character(0:9))
  paste(sample(alphabet, size = length, replace = TRUE), collapse = "")
}


ticket_config <- function(default_app_id, app_label) {
  ttl_seconds <- max(60L, ticket_env_int("APP_TICKET_TTL_SECONDS", 300L))
  wait_stale_default <- min(ttl_seconds, 120L)
  list(
    enabled = ticket_env_bool("APP_TICKET_ENFORCED", TRUE),
    app_id = trimws(Sys.getenv("APP_TICKET_ID", unset = default_app_id)) %||% default_app_id,
    app_label = app_label,
    max_active = max(1L, ticket_env_int("APP_TICKET_MAX_ACTIVE", 1L)),
    cost = max(0L, ticket_env_int("APP_TICKET_COST", 4L)),
    global_capacity = max(1L, ticket_env_int("CAPACITE_SERVEUR", 6L)),
    ttl_seconds = ttl_seconds,
    max_waiting = max(0L, ticket_env_int("APP_TICKET_MAX_WAITING", 20L)),
    wait_refresh_ms = max(2000L, ticket_env_int("APP_TICKET_WAIT_REFRESH_MS", 10000L)),
    heartbeat_ms = max(30000L, ticket_env_int("APP_TICKET_HEARTBEAT_MS", 30000L)),
    release_url = trimws(Sys.getenv("APP_TICKET_RELEASE_URL", unset = "")),
    hidden_release_seconds = max(0L, ticket_env_int("APP_TICKET_HIDDEN_RELEASE_SECONDS", 0L)),
    wait_stale_seconds = max(30L, ticket_env_int("APP_TICKET_WAIT_STALE_SECONDS", wait_stale_default))
  )
}


ticket_redis_helper_path <- function() {
  configured <- trimws(Sys.getenv("APP_TICKET_REDIS_HELPER", unset = ""))
  if (nzchar(configured)) {
    return(configured)
  }
  default_path <- "/app/backend/redis_ticket_cli.py"
  if (file.exists(default_path)) {
    return(default_path)
  }
  "backend/redis_ticket_cli.py"
}


ticket_python3 <- function() {
  python3 <- Sys.which("python3")
  if (!nzchar(python3)) {
    stop("python3 absent : installe python3 dans l'image Docker CHD Rainette.", call. = FALSE)
  }
  python3
}


ticket_redis_cli <- function() {
  redis_cli <- Sys.which("redis-cli")
  if (!nzchar(redis_cli)) {
    stop("redis-cli absent : installe le package redis-tools dans l'image Docker.", call. = FALSE)
  }
  redis_cli
}


ticket_redis_url <- function() {
  redis_url <- trimws(Sys.getenv("REDIS_URL", unset = ""))
  if (!nzchar(redis_url)) {
    stop("REDIS_URL absent : configure une URL Redis complète avec mot de passe dans Coolify.", call. = FALSE)
  }
  redis_url
}


ticket_redis_exec_python <- function(args) {
  helper_path <- ticket_redis_helper_path()
  if (!file.exists(helper_path)) {
    stop(sprintf("Helper Redis Python absent : %s", helper_path), call. = FALSE)
  }
  output <- tryCatch(
    system2(
      ticket_python3(),
      c(helper_path, args),
      stdout = TRUE,
      stderr = TRUE
    ),
    error = function(exc) structure(c(conditionMessage(exc)), status = 1L)
  )
  status <- attr(output, "status")
  if (is.null(status)) {
    status <- 0L
  }
  if (!identical(as.integer(status), 0L)) {
    stop(sprintf("Connexion Redis impossible via le helper Python : %s", paste(output, collapse = "\n")), call. = FALSE)
  }
  output
}


ticket_redis_exec_cli <- function(args) {
  output <- tryCatch(
    system2(
      ticket_redis_cli(),
      c("-u", ticket_redis_url(), "--raw", args),
      stdout = TRUE,
      stderr = TRUE
    ),
    error = function(exc) structure(c(conditionMessage(exc)), status = 1L)
  )
  status <- attr(output, "status")
  if (is.null(status)) {
    status <- 0L
  }
  if (!identical(as.integer(status), 0L)) {
    stop(sprintf("Connexion Redis impossible via REDIS_URL : %s", paste(output, collapse = "\n")), call. = FALSE)
  }
  output
}


ticket_redis_exec <- function(args) {
  python_error <- NULL
  python_output <- tryCatch(
    ticket_redis_exec_python(args),
    error = function(exc) {
      python_error <<- conditionMessage(exc)
      NULL
    }
  )
  if (!is.null(python_output)) {
    return(python_output)
  }

  cli_output <- tryCatch(
    ticket_redis_exec_cli(args),
    error = function(exc) {
      stop(
        sprintf(
          "Redis indisponible. Erreur helper Python : %s\nErreur redis-cli : %s",
          python_error %||% "(non disponible)",
          conditionMessage(exc)
        ),
        call. = FALSE
      )
    }
  )
  cli_output
}


ticket_safe_int <- function(value, default = 0L) {
  parsed <- suppressWarnings(as.integer(value))
  if (is.na(parsed)) {
    default
  } else {
    parsed
  }
}


ticket_keys <- function(app_id) {
  list(
    active = sprintf("app:%s:tickets:actifs", app_id),
    waiting = sprintf("app:%s:tickets:attente", app_id)
  )
}


ticket_ticket_key <- function(ticket_id) {
  sprintf("ticket:%s", ticket_id)
}


ticket_session_key <- function(app_id, session_id) {
  sprintf("session:%s:%s:ticket", app_id, session_id)
}


ticket_global_active_key <- function() {
  "tickets:global:actifs"
}


ticket_exists <- function(key) {
  ticket_safe_int(ticket_redis_exec(c("EXISTS", key))[1], 0L) > 0L
}


ticket_get <- function(key) {
  value <- ticket_redis_exec(c("GET", key))
  if (!length(value)) {
    return("")
  }
  trimws(value[1])
}


ticket_setex <- function(key, ttl_seconds, value) {
  invisible(ticket_redis_exec(c("SETEX", key, as.character(ttl_seconds), as.character(value))))
}


ticket_expire <- function(key, ttl_seconds) {
  invisible(ticket_redis_exec(c("EXPIRE", key, as.character(ttl_seconds))))
}


ticket_del <- function(...) {
  keys <- Filter(nzchar, unlist(list(...), use.names = FALSE))
  if (!length(keys)) {
    return(invisible(NULL))
  }
  invisible(ticket_redis_exec(c("DEL", keys)))
}


ticket_zrem <- function(key, member) {
  invisible(ticket_redis_exec(c("ZREM", key, member)))
}


ticket_zadd <- function(key, score, member) {
  invisible(ticket_redis_exec(c("ZADD", key, format(score, scientific = FALSE, trim = TRUE), member)))
}


ticket_list_members <- function(key) {
  values <- ticket_redis_exec(c("ZRANGE", key, "0", "-1"))
  values[nzchar(values)]
}


ticket_zcard <- function(key) {
  ticket_safe_int(ticket_redis_exec(c("ZCARD", key))[1], 0L)
}


ticket_hgetall <- function(key) {
  raw <- ticket_redis_exec(c("HGETALL", key))
  if (!length(raw)) {
    return(list())
  }
  raw <- raw[nzchar(raw)]
  if (!length(raw)) {
    return(list())
  }
  result <- list()
  for (index in seq(1L, length(raw), by = 2L)) {
    field <- raw[index]
    value <- if (index + 1L <= length(raw)) raw[index + 1L] else ""
    result[[field]] <- value
  }
  result
}


ticket_hset_map <- function(key, mapping) {
  flat <- as.vector(rbind(names(mapping), unname(as.character(mapping))))
  invisible(ticket_redis_exec(c("HSET", key, flat)))
}


ticket_timeout_seconds <- function(cfg, status) {
  if (identical(status, "attente")) {
    return(cfg$wait_stale_seconds)
  }
  cfg$ttl_seconds
}


ticket_drop <- function(cfg, ticket_id) {
  data <- ticket_hgetall(ticket_ticket_key(ticket_id))
  session_id <- trimws(data$session_id %||% "")
  keys <- ticket_keys(cfg$app_id)
  ticket_zrem(keys$active, ticket_id)
  ticket_zrem(keys$waiting, ticket_id)
  ticket_zrem(ticket_global_active_key(), ticket_id)
  ticket_del(ticket_ticket_key(ticket_id))
  if (nzchar(session_id)) {
    ticket_del(ticket_session_key(cfg$app_id, session_id))
  }
}


ticket_cleanup_expired <- function(cfg) {
  keys <- ticket_keys(cfg$app_id)
  now <- as.integer(Sys.time())
  seen <- character()
  for (key in c(keys$active, keys$waiting, ticket_global_active_key())) {
    members <- ticket_list_members(key)
    for (ticket_id in members) {
      if (ticket_id %in% seen) {
        next
      }
      seen <- c(seen, ticket_id)
      hash_key <- ticket_ticket_key(ticket_id)
      if (!ticket_exists(hash_key)) {
        ticket_zrem(keys$active, ticket_id)
        ticket_zrem(keys$waiting, ticket_id)
        ticket_zrem(ticket_global_active_key(), ticket_id)
        next
      }
      data <- ticket_hgetall(hash_key)
      status <- trimws(data$status %||% "")
      if (!nzchar(status)) {
        status <- "attente"
      }
      heartbeat_at <- ticket_safe_int(data$updated_at %||% data$created_at %||% now, now)
      if ((now - heartbeat_at) > ticket_timeout_seconds(cfg, status)) {
        ticket_drop(cfg, ticket_id)
      }
    }
  }
}


ticket_active_count <- function(cfg) {
  ticket_zcard(ticket_keys(cfg$app_id)$active)
}


ticket_waiting_count <- function(cfg) {
  ticket_zcard(ticket_keys(cfg$app_id)$waiting)
}


ticket_active_load <- function() {
  total <- 0L
  for (ticket_id in ticket_list_members(ticket_global_active_key())) {
    data <- ticket_hgetall(ticket_ticket_key(ticket_id))
    if (length(data)) {
      total <- total + ticket_safe_int(data$cost %||% 0L, 0L)
    }
  }
  total
}


ticket_waiting_position <- function(cfg, ticket_id) {
  waiting <- ticket_list_members(ticket_keys(cfg$app_id)$waiting)
  if (!(ticket_id %in% waiting)) {
    return(NULL)
  }
  match(ticket_id, waiting)
}


ticket_can_activate <- function(cfg) {
  ticket_active_count(cfg) < cfg$max_active && (ticket_active_load() + cfg$cost <= cfg$global_capacity)
}


ticket_promote_waiting <- function(cfg) {
  keys <- ticket_keys(cfg$app_id)
  for (ticket_id in ticket_list_members(keys$waiting)) {
    if (!ticket_can_activate(cfg)) {
      break
    }
    hash_key <- ticket_ticket_key(ticket_id)
    if (!ticket_exists(hash_key)) {
      ticket_zrem(keys$waiting, ticket_id)
      next
    }
    now <- as.integer(Sys.time())
    ticket_hset_map(hash_key, c(status = "actif", updated_at = now))
    ticket_expire(hash_key, cfg$ttl_seconds)
    ticket_zrem(keys$waiting, ticket_id)
    ticket_zadd(keys$active, as.numeric(now), ticket_id)
    ticket_zadd(ticket_global_active_key(), as.numeric(now), ticket_id)
  }
}


ticket_touch_existing <- function(cfg, ticket_id, session_key) {
  data <- ticket_hgetall(ticket_ticket_key(ticket_id))
  status <- trimws(data$status %||% "")
  if (!nzchar(status)) {
    status <- "attente"
  }
  now <- as.integer(Sys.time())
  timeout <- ticket_timeout_seconds(cfg, status)
  ticket_hset_map(ticket_ticket_key(ticket_id), c(updated_at = now))
  ticket_expire(ticket_ticket_key(ticket_id), timeout)
  ticket_expire(session_key, timeout)
  invisible(data)
}


ticket_snapshot <- function(cfg, ticket_id = NULL, message = "") {
  active <- ticket_active_count(cfg)
  queued <- ticket_waiting_count(cfg)
  if (is.null(ticket_id) || !nzchar(ticket_id)) {
    return(list(
      enabled = TRUE,
      ticket_id = NULL,
      statut = "inconnu",
      position = NULL,
      active = active,
      queued = queued,
      max_active = cfg$max_active,
      wait_refresh_ms = cfg$wait_refresh_ms,
      heartbeat_ms = cfg$heartbeat_ms,
      message = message
    ))
  }
  data <- ticket_hgetall(ticket_ticket_key(ticket_id))
  list(
    enabled = TRUE,
    ticket_id = ticket_id,
    statut = trimws(data$status %||% "inconnu"),
    position = ticket_waiting_position(cfg, ticket_id),
    active = active,
    queued = queued,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = trimws(data$message %||% message)
  )
}


ticket_disabled_snapshot <- function(cfg, message) {
  list(
    enabled = FALSE,
    ticket_id = NULL,
    statut = "disabled",
    position = NULL,
    active = 0L,
    queued = 0L,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = message
  )
}


ticket_error_snapshot <- function(cfg, message) {
  list(
    enabled = TRUE,
    ticket_id = NULL,
    statut = "erreur",
    position = NULL,
    active = 0L,
    queued = 0L,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = message
  )
}


ticket_released_snapshot <- function(cfg, message) {
  active <- 0L
  queued <- 0L
  safe_counts <- tryCatch(
    list(active = ticket_active_count(cfg), queued = ticket_waiting_count(cfg)),
    error = function(...) list(active = 0L, queued = 0L)
  )
  active <- safe_counts$active
  queued <- safe_counts$queued
  list(
    enabled = TRUE,
    ticket_id = NULL,
    statut = "released",
    position = NULL,
    active = active,
    queued = queued,
    max_active = cfg$max_active,
    wait_refresh_ms = cfg$wait_refresh_ms,
    heartbeat_ms = cfg$heartbeat_ms,
    message = message
  )
}


ticket_claim_or_refresh <- function(cfg, session_id) {
  ticket_redis_exec(c("PING"))
  ticket_cleanup_expired(cfg)
  ticket_promote_waiting(cfg)

  session_key <- ticket_session_key(cfg$app_id, session_id)
  existing_ticket <- trimws(ticket_get(session_key))

  if (nzchar(existing_ticket) && ticket_exists(ticket_ticket_key(existing_ticket))) {
    ticket_touch_existing(cfg, existing_ticket, session_key)
    ticket_promote_waiting(cfg)
    return(ticket_snapshot(cfg, existing_ticket))
  }

  if (nzchar(existing_ticket)) {
    ticket_del(session_key)
  }

  if (ticket_waiting_count(cfg) >= cfg$max_waiting) {
    return(list(
      enabled = TRUE,
      ticket_id = NULL,
      statut = "refuse",
      position = NULL,
      active = ticket_active_count(cfg),
      queued = ticket_waiting_count(cfg),
      max_active = cfg$max_active,
      wait_refresh_ms = cfg$wait_refresh_ms,
      heartbeat_ms = cfg$heartbeat_ms,
      message = "File d'attente pleine pour cette application."
    ))
  }

  ticket_id <- ticket_random_id()
  status <- if (ticket_waiting_count(cfg) == 0L && ticket_can_activate(cfg)) "actif" else "attente"
  now <- as.integer(Sys.time())
  ticket_hset_map(
    ticket_ticket_key(ticket_id),
    c(
      ticket_id = ticket_id,
      session_id = session_id,
      application_id = cfg$app_id,
      application_label = cfg$app_label,
      cost = cfg$cost,
      status = status,
      created_at = now,
      updated_at = now
    )
  )
  timeout <- ticket_timeout_seconds(cfg, status)
  ticket_expire(ticket_ticket_key(ticket_id), timeout)
  ticket_setex(session_key, timeout, ticket_id)

  keys <- ticket_keys(cfg$app_id)
  if (identical(status, "actif")) {
    ticket_zadd(keys$active, as.numeric(now), ticket_id)
    ticket_zadd(ticket_global_active_key(), as.numeric(now), ticket_id)
  } else {
    ticket_zadd(keys$waiting, as.numeric(now), ticket_id)
  }

  ticket_promote_waiting(cfg)
  ticket_snapshot(cfg, ticket_id)
}


ticket_release <- function(cfg, session_id) {
  if (is.null(session_id) || !nzchar(session_id)) {
    return(FALSE)
  }
  tryCatch(
    {
      ticket_redis_exec(c("PING"))
      session_key <- ticket_session_key(cfg$app_id, session_id)
      ticket_id <- trimws(ticket_get(session_key))
      if (nzchar(ticket_id)) {
        keys <- ticket_keys(cfg$app_id)
        ticket_zrem(keys$active, ticket_id)
        ticket_zrem(keys$waiting, ticket_id)
        ticket_zrem(ticket_global_active_key(), ticket_id)
        ticket_del(ticket_ticket_key(ticket_id), session_key)
      }
      ticket_promote_waiting(cfg)
      TRUE
    },
    error = function(...) FALSE
  )
}


ticket_session_id <- function(session) {
  if (is.null(session$userData$ticket_session_id) || !nzchar(session$userData$ticket_session_id)) {
    session$userData$ticket_session_id <- sprintf("%s-%s", session$token, ticket_random_id(12L))
  }
  session$userData$ticket_session_id
}


ticket_resume_session <- function(session) {
  session$userData$ticket_released <- FALSE
  session$userData$ticket_session_id <- sprintf("%s-%s", session$token, ticket_random_id(12L))
  session$userData$ticket_release_sent <- FALSE
  invisible(session$userData$ticket_session_id)
}


ticket_set_released <- function(session, value = TRUE) {
  session$userData$ticket_released <- isTRUE(value)
}


ticket_is_released <- function(session) {
  isTRUE(session$userData$ticket_released)
}


ticket_release_hook_ui <- function(cfg, session) {
  if (!cfg$enabled || !nzchar(cfg$release_url) || ticket_is_released(session)) {
    return(NULL)
  }
  session_id <- ticket_session_id(session)
  hidden_ms <- max(0L, cfg$hidden_release_seconds) * 1000L
  tags$script(HTML(sprintf(
    "(function(){const releaseUrl=%s;const applicationId=%s;const sessionId=%s;const hiddenMs=%s;
      if(!releaseUrl||!applicationId||!sessionId){return;}
      let sent=false;let hiddenTimer=null;
      function buildUrl(){const sep=releaseUrl.indexOf('?')>=0?'&':'?';return releaseUrl+sep+'application_id='+encodeURIComponent(applicationId)+'&session_id='+encodeURIComponent(sessionId);}
      function sendRelease(){if(sent){return;}sent=true;const url=buildUrl();
        try{if(navigator.sendBeacon){const ok=navigator.sendBeacon(url,new Blob([''],{type:'text/plain;charset=UTF-8'}));if(ok){return;}}}catch(error){}
        try{fetch(url,{method:'POST',mode:'no-cors',keepalive:true,body:''}).catch(()=>{});}catch(error){}
      }
      function clearHiddenTimer(){if(hiddenTimer!==null){window.clearTimeout(hiddenTimer);hiddenTimer=null;}}
      function scheduleHiddenRelease(){clearHiddenTimer();if(!hiddenMs||hiddenMs<=0){return;}hiddenTimer=window.setTimeout(function(){sendRelease();},hiddenMs);}
      document.addEventListener('visibilitychange',function(){if(document.visibilityState==='hidden'){scheduleHiddenRelease();}else{clearHiddenTimer();sent=false;}});
      window.addEventListener('pagehide',sendRelease);
      window.addEventListener('beforeunload',sendRelease);
    })();",
    shQuote(cfg$release_url, type = "sh"),
    shQuote(cfg$app_id, type = "sh"),
    shQuote(session_id, type = "sh"),
    as.character(hidden_ms)
  )))
}


ticket_sidebar_ui <- function(snapshot) {
  status <- snapshot$statut %||% "erreur"
  diagnostic_summary <- ticket_first_diagnostic_line(snapshot$message)
  card_class <- switch(
    status,
    disabled = "ticket-status-card is-disabled",
    actif = "ticket-status-card is-active",
    attente = "ticket-status-card is-waiting",
    refuse = "ticket-status-card is-error",
    released = "ticket-status-card is-released",
    "ticket-status-card is-error"
  )
  dot_class <- switch(
    status,
    disabled = "ticket-status-dot is-disabled",
    actif = "ticket-status-dot is-active",
    attente = "ticket-status-dot is-waiting",
    released = "ticket-status-dot is-released",
    "ticket-status-dot is-error"
  )
  title <- switch(
    status,
    disabled = "Accès libre",
    actif = "Application active",
    attente = "Application occupée",
    refuse = "File d'attente pleine",
    released = "Accès libéré",
    "Accès indisponible"
  )
  detail <- switch(
    status,
    disabled = "Le contrôle d'accès n'est pas appliqué pour cette application.",
    actif = sprintf("%s utilisateur(s) actif(s) sur %s autorisé(s).", snapshot$active, snapshot$max_active),
    attente = sprintf("Position actuelle dans la file : %s.", snapshot$position %||% "?"),
    refuse = "Impossible d'ajouter un nouvel utilisateur pour le moment.",
    released = "Cette page n'occupe plus l'application.",
    sprintf("Le ticket courant n'a pas pu être validé : %s", diagnostic_summary)
  )
  note <- switch(
    status,
    disabled = "Contrôle d'accès désactivé pour cette application.",
    actif = sprintf("Accès actif (%s / %s).", snapshot$active, snapshot$max_active),
    attente = sprintf("Application occupée. Position dans la file : %s.", snapshot$position %||% "?"),
    refuse = "File d'attente pleine pour cette application.",
    released = "Accès libéré pour cette page.",
    "Contrôle d'accès temporairement indisponible. Le diagnostic Redis complet est affiché ci-dessous."
  )
  actions <- switch(
    status,
    actif = tags$div(
      class = "ticket-actions",
      actionButton("ticket_release_btn", "Libérer l'accès", class = "btn-primary")
    ),
    attente = tags$div(
      class = "ticket-actions",
      actionButton("ticket_leave_waiting_btn", "Quitter la file d'attente", class = "btn-secondary")
    ),
    released = tags$div(
      class = "ticket-actions",
      actionButton("ticket_resume_btn", "Reprendre l'accès", class = "btn-primary")
    ),
    NULL
  )

  tags$div(
    class = "sidebar-group ticket-access-group",
    tags$h3(class = "ticket-access-title", "Accès utilisateur"),
    tags$div(
      class = "ticket-status-shell",
      tags$div(
        class = card_class,
        tags$span(class = dot_class),
        tags$div(
          class = "ticket-status-meta",
          tags$strong(title),
          tags$br(),
          detail
        )
      ),
      tags$p(class = "ticket-status-note", note),
      if (nzchar(snapshot$message %||% "") && status %in% c("refuse", "erreur")) {
        tags$div(
          class = "ticket-status-message",
          tags$strong("Diagnostic Redis"),
          tags$pre(snapshot$message)
        )
      },
      actions
    )
  )
}
