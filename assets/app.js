(function () {
  const body = document.body;
  const catalogEndpoint = body.dataset.catalogEndpoint || "/api/tickets/apps";
  const dashboardEndpoint = body.dataset.dashboardEndpoint || "/api/tickets/dashboard";
  const localPendingMs = Math.max(5000, Number.parseInt(body.dataset.localPendingMs || "15000", 10) || 15000);
  const localFallbackMs = Math.max(localPendingMs, Number.parseInt(body.dataset.localFallbackMs || "300000", 10) || 300000);
  const localStorageKey = "codeandcortex-dashboard-local-tickets";
  const note = document.getElementById("dashboard-note");
  const catalogueRoot = document.getElementById("catalogue-applications");
  const globalActive = document.getElementById("global-active");
  const globalQueue = document.getElementById("global-queue");
  const globalServer = document.getElementById("global-server");
  let cards = [];
  let appIds = [];

  function safeParseJson(value) {
    try {
      return JSON.parse(value);
    } catch (error) {
      return {};
    }
  }

  function readLocalTickets() {
    return safeParseJson(window.localStorage.getItem(localStorageKey) || "{}");
  }

  function writeLocalTickets(payload) {
    window.localStorage.setItem(localStorageKey, JSON.stringify(payload));
  }

  function cleanupLocalTickets() {
    const now = Date.now();
    const payload = readLocalTickets();
    let dirty = false;

    Object.entries(payload).forEach(([appId, item]) => {
      const expiresAt = Number(item && item.expiresAt || 0);
      if (!expiresAt || expiresAt <= now) {
        delete payload[appId];
        dirty = true;
      }
    });

    if (dirty) {
      writeLocalTickets(payload);
    }

    return payload;
  }

  function getLocalTicket(appId) {
    const payload = cleanupLocalTickets();
    return payload[appId] || null;
  }

  function setLocalTicket(appId) {
    const payload = cleanupLocalTickets();
    const now = Date.now();
    payload[appId] = {
      pendingUntil: now + localPendingMs,
      expiresAt: now + localFallbackMs,
    };
    writeLocalTickets(payload);
  }

  function clearLocalTicket(appId) {
    const payload = readLocalTickets();
    if (!payload[appId]) return;
    delete payload[appId];
    writeLocalTickets(payload);
  }

  function extractMaxActive(card) {
    const meta = card.querySelector("[data-status-meta]");
    const text = meta ? meta.textContent || "" : "";
    const match = text.match(/\/\s*(\d+)/);
    return match ? Math.max(1, Number.parseInt(match[1], 10) || 1) : 1;
  }

  function isUnavailableState(state) {
    return state === "unavailable" || state === "degraded";
  }

  function isBusyState(state, active, queued) {
    if ((queued || 0) > 0) return true;
    if ((active || 0) > 0) return true;
    return state === "busy" || state === "active" || state === "queued" || state === "full";
  }

  function badgeClassFromState(state, queued) {
    if (isUnavailableState(state)) return "indisponible";
    if (queued > 0 || state === "queued" || state === "full") return "attente";
    if (state === "busy" || state === "active") return "attente";
    return "libre";
  }

  function labelFromState(state, queued) {
    if (isUnavailableState(state)) return "Synchronisation";
    if (queued > 0 || state === "queued" || state === "full") return "File d'attente";
    if (state === "busy" || state === "active") return "En cours";
    return "Libre";
  }

  function buildLocalPayload(card) {
    return {
      state: "busy",
      stateLabel: "Ouverture",
      active: 1,
      maxActive: extractMaxActive(card),
      queued: 0,
      metaText: "Ouverture en cours...",
    };
  }

  function resolvePayload(card, payload) {
    const appId = card.dataset.appId;
    const localTicket = appId ? getLocalTicket(appId) : null;

    if (payload && !isUnavailableState(payload.state)) {
      if (isBusyState(payload.state, payload.active, payload.queued)) {
        clearLocalTicket(appId);
        return payload;
      }
      if (localTicket && Date.now() < Number(localTicket.pendingUntil || 0)) {
        return buildLocalPayload(card);
      }
      clearLocalTicket(appId);
      return payload;
    }

    if (localTicket) {
      return buildLocalPayload(card);
    }

    return null;
  }

  function decorateCard(card, payload) {
    const dot = card.querySelector("[data-status-dot]");
    const label = card.querySelector("[data-status-label]");
    const meta = card.querySelector("[data-status-meta]");
    if (!dot || !label || !meta || !payload) return;

    const stateClass = badgeClassFromState(payload.state, payload.queued || 0);
    dot.className = "pastille-etat " + stateClass;
    label.textContent = payload.stateLabel || labelFromState(payload.state, payload.queued || 0);
    meta.textContent = payload.metaText || `${payload.active || 0} / ${payload.maxActive || 0} actif · ${payload.queued || 0} attente`;

    card.classList.remove("libre", "occupee", "attente", "indisponible");
    card.classList.add(stateClass);
  }

  function decorateGlobal(payload) {
    if (!payload) return;
    globalActive.textContent = `${payload.activeUsers || 0} · charge ${payload.activeLoad || 0}/${payload.maxLoad || 0}`;
    globalQueue.textContent = `${payload.totalQueued || 0}`;
    globalServer.textContent = payload.serverLabel || "Disponible";
  }

  function applyDashboard(payload) {
    if (!payload || typeof payload !== "object") return;
    decorateGlobal(payload.global || null);

    cards.forEach((card) => {
      const appId = card.dataset.appId;
      const appPayload = payload.apps && payload.apps[appId];
      const resolvedPayload = resolvePayload(card, appPayload);
      if (resolvedPayload) {
        decorateCard(card, resolvedPayload);
      }
    });

    if (note) {
      if (payload.global && payload.global.serverState === "degraded") {
        note.textContent = payload.global.message || "Synchronisation Redis temporairement indisponible : la page conserve le dernier état connu et met à jour la pastille d'une application que vous venez d'ouvrir.";
      } else {
        note.textContent = "Les indicateurs sont synchronisés avec Redis et se mettent à jour automatiquement.";
      }
    }
  }

  function applyLocalFallbackStates() {
    cards.forEach((card) => {
      const appId = card.dataset.appId;
      if (!appId || !getLocalTicket(appId)) return;
      decorateCard(card, buildLocalPayload(card));
    });
  }

  function markDashboardUnavailable(message) {
    globalServer.textContent = "Synchronisation indisponible";
    applyLocalFallbackStates();
    if (note) {
      note.textContent = message || "API dashboard indisponible pour le moment.";
    }
  }

  function familyClassName(familyId) {
    if (familyId === "extraire") return "famille-extraire";
    if (familyId === "calculer") return "famille-calculer";
    if (familyId === "multimodale") return "famille-multimodale";
    return "famille-generique";
  }

  function renderTicketCard(entry) {
    const href = entry.href || "#";
    const metaText = entry.defaultMetaText || `0 / ${entry.defaultMaxActive || 1} actif · 0 attente`;
    return `
      <a href="${href}" class="carte-application libre" target="_blank" rel="noopener noreferrer" data-app-id="${entry.appId}">
        <span class="ruban-statut">
          <span class="pastille-etat libre" data-status-dot aria-hidden="true"></span>
          <span class="statut" data-status-label>Libre</span>
        </span>
        <i class="icone ${entry.iconClass}"></i>
        <span class="contenu-carte">
          <span class="titre-application">${entry.label}</span>
          <span class="meta-application" data-status-meta>${metaText}</span>
          <span class="description-application">${entry.description || ""}</span>
        </span>
      </a>
    `;
  }

  function renderStaticCard(entry) {
    if (entry.disabled) {
      return `
        <div class="carte-application indisponible en-construction" aria-disabled="true">
          <span class="ruban-statut">
            <span class="pastille-etat indisponible" aria-hidden="true"></span>
            <span class="statut">${entry.statusLabel || "En construction"}</span>
          </span>
          <i class="icone ${entry.iconClass}"></i>
          <span class="contenu-carte">
            <span class="titre-application">${entry.label}</span>
            <span class="meta-application">${entry.metaText || ""}</span>
            <span class="description-application">${entry.description || ""}</span>
          </span>
        </div>
      `;
    }

    return `
      <a href="${entry.href || "#"}" class="carte-application libre" target="_blank" rel="noopener noreferrer">
        <span class="ruban-statut">
          <span class="pastille-etat libre" aria-hidden="true"></span>
          <span class="statut">${entry.statusLabel || "Libre"}</span>
        </span>
        <i class="icone ${entry.iconClass}"></i>
        <span class="contenu-carte">
          <span class="titre-application">${entry.label}</span>
          <span class="meta-application">${entry.metaText || ""}</span>
          <span class="description-application">${entry.description || ""}</span>
        </span>
      </a>
    `;
  }

  function renderCatalog(payload) {
    if (!catalogueRoot) return;
    const families = Array.isArray(payload && payload.families) ? payload.families : [];
    catalogueRoot.innerHTML = families.map((family) => `
      <section class="famille-applications ${familyClassName(family.id)}" aria-label="Applications ${family.label}">
        <div class="famille-entete">
          <h2 class="famille-titre">${family.label}</h2>
        </div>
        <div class="grille-applications">
          ${(family.entries || []).map((entry) => entry.ticketed ? renderTicketCard(entry) : renderStaticCard(entry)).join("")}
        </div>
      </section>
    `).join("");

    cards = Array.from(catalogueRoot.querySelectorAll("[data-app-id]"));
    appIds = cards.map((card) => card.dataset.appId).filter(Boolean);
    cards.forEach((card) => {
      card.addEventListener("click", () => {
        const appId = card.dataset.appId;
        if (!appId) return;
        setLocalTicket(appId);
        decorateCard(card, buildLocalPayload(card));
        window.setTimeout(refreshDashboard, 1200);
      });
    });
  }

  async function refreshDashboard() {
    if (!appIds.length) return;

    const url = new URL(dashboardEndpoint, window.location.origin);
    url.searchParams.set("applications", appIds.join(","));

    try {
      const response = await fetch(url.toString(), {
        headers: { "Accept": "application/json" },
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      applyDashboard(payload);
    } catch (error) {
      markDashboardUnavailable("API dashboard indisponible : vérifie le service racine du dépôt, l'endpoint `/api/tickets/dashboard` et la variable REDIS_URL du dashboard.");
    }
  }

  async function bootstrap() {
    try {
      const response = await fetch(catalogEndpoint, {
        headers: { "Accept": "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      renderCatalog(payload);
      await refreshDashboard();
      window.setInterval(refreshDashboard, 2000);
    } catch (error) {
      if (note) {
        note.textContent = "Impossible de charger le catalogue dynamique du dashboard.";
      }
      globalServer.textContent = "Catalogue indisponible";
    }
  }

  window.addEventListener("storage", () => {
    refreshDashboard();
  });

  window.addEventListener("message", (event) => {
    const payload = event && event.data;
    if (!payload || typeof payload !== "object") return;
    if (typeof payload.type !== "string" || !payload.type.startsWith("codeandcortex-ticket:")) return;
    const appId = String(payload.appId || payload.applicationId || "").trim();
    if (appId) clearLocalTicket(appId);
    refreshDashboard();
  });

  window.addEventListener("focus", () => {
    refreshDashboard();
  });

  bootstrap();
})();
