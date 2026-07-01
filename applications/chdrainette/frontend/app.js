const state = {
  corpusName: "",
  corpusText: "",
  currentJobId: "",
  currentResult: null,
  ticketSnapshot: null,
  jobTimer: null,
  ticketTimer: null,
  heartbeatTimer: null,
  history: [],
};

const els = {
  navLinks: [...document.querySelectorAll(".nav-link[data-panel-target]")],
  panels: [...document.querySelectorAll(".panel[data-panel]")],
  importCorpusBtn: document.getElementById("importCorpusBtn"),
  corpusFile: document.getElementById("corpusFile"),
  fileInfo: document.getElementById("fileInfo"),
  corpusPreview: document.getElementById("corpusPreview"),
  runAnalysisBtn: document.getElementById("runAnalysisBtn"),
  runStatus: document.getElementById("runStatus"),
  accessDot: document.getElementById("accessDot"),
  accessLabel: document.getElementById("accessLabel"),
  accessMessage: document.getElementById("accessMessage"),
  releaseAccessBtn: document.getElementById("releaseAccessBtn"),
  analysisHistory: document.getElementById("analysisHistory"),
  progress: document.getElementById("progress"),
  progressLabel: document.getElementById("progressLabel"),
  statusMessage: document.getElementById("statusMessage"),
  logs: document.getElementById("logs"),
  metricDocs: document.getElementById("metricDocs"),
  metricSegments: document.getElementById("metricSegments"),
  metricAnalyzed: document.getElementById("metricAnalyzed"),
  metricClasses: document.getElementById("metricClasses"),
  summaryTable: document.getElementById("summaryTable"),
  detailTable: document.getElementById("detailTable"),
  artifactList: document.getElementById("artifactList"),
  plotPlaceholder: document.getElementById("plotPlaceholder"),
  explorerPlot: document.getElementById("explorerPlot"),
  explorerK: document.getElementById("explorerK"),
  explorerKValue: document.getElementById("explorerKValue"),
  explorerMeasure: document.getElementById("explorerMeasure"),
  explorerTerms: document.getElementById("explorerTerms"),
  explorerTextSize: document.getElementById("explorerTextSize"),
  explorerSameScales: document.getElementById("explorerSameScales"),
  explorerShowNegative: document.getElementById("explorerShowNegative"),
  refreshExplorerBtn: document.getElementById("refreshExplorerBtn"),
  showExplorerCodeBtn: document.getElementById("showExplorerCodeBtn"),
  explorerCode: document.getElementById("explorerCode"),
  docsCluster: document.getElementById("docsCluster"),
  docsNDoc: document.getElementById("docsNDoc"),
  docsMaxChars: document.getElementById("docsMaxChars"),
  docsFilterTerm: document.getElementById("docsFilterTerm"),
  docsRandomSample: document.getElementById("docsRandomSample"),
  refreshDocsBtn: document.getElementById("refreshDocsBtn"),
  docsIntro: document.getElementById("docsIntro"),
  docsSample: document.getElementById("docsSample"),
  modeDecoupage: document.getElementById("modeDecoupage"),
  segmentSize: document.getElementById("segmentSize"),
  kValue: document.getElementById("kValue"),
  minSplitSegments: document.getElementById("minSplitSegments"),
  minDocfreq: document.getElementById("minDocfreq"),
  topN: document.getElementById("topN"),
  lemmatisation: document.getElementById("lemmatisation"),
  uposSelection: document.getElementById("uposSelection"),
};

const DEFAULT_TICKET_IDLE_RELEASE_MS = 900000;
const TICKET_SESSION_STORAGE_KEY = "chdrainette_ticket_session";
const HOME_DASHBOARD_MESSAGE_PREFIX = "codeandcortex-ticket";
let ticketReleasedLocally = false;
let idleReleaseTimerId = null;
let lastTicketInteractionAt = Date.now();

function switchPanel(target) {
  els.navLinks.forEach((button) => {
    button.classList.toggle("is-active", button.dataset.panelTarget === target);
  });
  els.panels.forEach((panel) => {
    const active = panel.dataset.panel === target;
    panel.classList.toggle("is-active", active);
    panel.hidden = !active;
  });
}

function selectedValues(select) {
  return [...select.selectedOptions].map((option) => option.value);
}

function readFileAsText(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(reader.error || new Error("Lecture impossible."));
    reader.readAsText(file, "utf-8");
  });
}

function setProgress(value, label = "") {
  const progressValue = Number.isFinite(Number(value)) ? Number(value) : 0;
  els.progress.value = progressValue;
  els.progressLabel.textContent = label || `${progressValue}%`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function tableFromRows(rows) {
  if (!rows || !rows.length) {
    return "<p class='empty-state'>Aucune donnée disponible.</p>";
  }
  const columns = Object.keys(rows[0]);
  const head = columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns.map((column) => `<td>${escapeHtml(row[column])}</td>`).join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="data-table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function artifactListHtml(artifacts) {
  const visible = (artifacts || []).filter((item) => !String(item.relativePath || "").endsWith("analysis_bundle.rds"));
  if (!visible.length) {
    return "<p class='empty-state'>Aucun export disponible.</p>";
  }
  return visible
    .map((item) => {
      const size = Number(item.sizeBytes || 0);
      const sizeText = size > 1024 * 1024
        ? `${(size / (1024 * 1024)).toFixed(2)} Mo`
        : size > 1024
          ? `${(size / 1024).toFixed(1)} Ko`
          : `${size} o`;
      return `
        <div class="artifact-item">
          <div>
            <strong>${escapeHtml(item.relativePath)}</strong><br />
            <span class="muted">${escapeHtml(item.mimeType || "")} · ${sizeText}</span>
          </div>
          <a href="${item.downloadUrl}" target="_blank" rel="noopener noreferrer">Télécharger</a>
        </div>
      `;
    })
    .join("");
}

function addHistoryEntry(jobId, corpusName) {
  state.history.unshift({
    jobId,
    corpusName,
    at: new Date().toLocaleString("fr-FR"),
  });
  if (state.history.length > 8) {
    state.history = state.history.slice(0, 8);
  }
  renderHistory();
}

function renderHistory() {
  if (!state.history.length) {
    els.analysisHistory.innerHTML = '<p class="muted analysis-history-empty">Les analyses lancées s’afficheront ici.</p>';
    return;
  }
  els.analysisHistory.innerHTML = state.history
    .map(
      (entry) => `
        <div class="history-item">
          <strong>${escapeHtml(entry.corpusName)}</strong><br />
          <span class="muted">${escapeHtml(entry.at)} · ${escapeHtml(entry.jobId)}</span>
        </div>
      `
    )
    .join("");
}

function configPayload() {
  return {
    mode_decoupage: els.modeDecoupage.value,
    segment_size: Number(els.segmentSize.value || 40),
    k: Number(els.kValue.value || 6),
    min_split_segments: Number(els.minSplitSegments.value || 12),
    min_docfreq: Number(els.minDocfreq.value || 1),
    top_n: Number(els.topN.value || 20),
    lemmatisation: Boolean(els.lemmatisation.checked),
    upos_a_conserver: selectedValues(els.uposSelection),
  };
}

function explorerPlotParams() {
  return new URLSearchParams({
    k: String(els.explorerK.value),
    measure: els.explorerMeasure.value,
    n_terms: String(els.explorerTerms.value),
    same_scales: String(els.explorerSameScales.checked),
    show_negative: String(els.explorerShowNegative.checked),
    text_size: String(els.explorerTextSize.value),
  });
}

function explorerDocsParams() {
  return new URLSearchParams({
    k: String(els.explorerK.value),
    cluster: String(els.docsCluster.value || 1),
    ndoc: String(els.docsNDoc.value || 100),
    nchar: String(els.docsMaxChars.value || 1000),
    random_sample: String(els.docsRandomSample.checked),
    filter_term: els.docsFilterTerm.value || "",
  });
}

function syncExplorerUi() {
  els.explorerKValue.textContent = els.explorerK.value;
  const docprop = els.explorerMeasure.value === "docprop";
  els.explorerSameScales.disabled = docprop;
  if (docprop) {
    els.explorerSameScales.checked = true;
  }
}

function ticketStatusClasses(status) {
  if (status === "actif") return { dot: "is-active", label: "Application active" };
  if (status === "attente") return { dot: "is-waiting", label: "Application occupée" };
  if (status === "occupee") return { dot: "is-waiting", label: "Application occupée" };
  if (status === "disponible") return { dot: "", label: "Application disponible" };
  if (status === "erreur") return { dot: "is-error", label: "Accès indisponible" };
  return { dot: "", label: "Statut inconnu" };
}

async function callTicketApi(path, { method = "GET" } = {}) {
  const sessionId = window.localStorage.getItem(TICKET_SESSION_STORAGE_KEY) || "";
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    cache: "no-store",
    headers: sessionId ? { "X-App-Ticket-Session": sessionId } : undefined,
  });

  const payload = await response.json().catch(() => ({}));
  if (payload?.session_id) {
    window.localStorage.setItem(TICKET_SESSION_STORAGE_KEY, String(payload.session_id));
  }
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `Erreur HTTP ${response.status}`);
  }
  return payload;
}

function hasLiveTicket(snapshot = state.ticketSnapshot) {
  return Boolean(snapshot?.enabled) && ["actif", "attente"].includes(String(snapshot?.statut || ""));
}

function rememberTicketSnapshot(snapshot) {
  state.ticketSnapshot = snapshot;
  if (hasLiveTicket(snapshot)) {
    ticketReleasedLocally = false;
  }
  return snapshot;
}

function updateReleaseAccessButton() {
  const busy = Boolean(state.currentJobId);
  if (ticketReleasedLocally) {
    els.releaseAccessBtn.textContent = "Reprendre l'accès";
    els.releaseAccessBtn.disabled = busy;
    return;
  }
  els.releaseAccessBtn.textContent = "Libérer l'accès";
  els.releaseAccessBtn.disabled = !hasLiveTicket() || busy;
}

function resolveIdleReleaseMs(snapshot = state.ticketSnapshot) {
  return Math.max(60000, Number(snapshot?.idle_release_ms || DEFAULT_TICKET_IDLE_RELEASE_MS));
}

function rememberUserInteraction() {
  lastTicketInteractionAt = Date.now();
  scheduleIdleRelease();
}

function dashboardMessageTargetOrigin() {
  if (!document.referrer) {
    return "*";
  }
  try {
    return new URL(document.referrer).origin || "*";
  } catch (_error) {
    return "*";
  }
}

function notifyHomeDashboard(eventName) {
  if (!window.opener || typeof window.opener.postMessage !== "function") {
    return;
  }
  window.opener.postMessage(
    {
      type: `${HOME_DASHBOARD_MESSAGE_PREFIX}:${eventName}`,
      appId: "chdrainette",
      at: Date.now(),
    },
    dashboardMessageTargetOrigin(),
  );
}

async function autoReleaseTicketAfterInactivity() {
  if (state.currentJobId || !hasLiveTicket()) {
    return;
  }
  const idleReleaseMs = resolveIdleReleaseMs();
  if (Date.now() - lastTicketInteractionAt < idleReleaseMs) {
    scheduleIdleRelease();
    return;
  }

  try {
    rememberTicketSnapshot(await callTicketApi("/api/tickets/release", { method: "POST" }));
    window.localStorage.removeItem(TICKET_SESSION_STORAGE_KEY);
    ticketReleasedLocally = true;
    notifyHomeDashboard("released");
    renderTicketStatus();
  } catch (_error) {
    scheduleIdleRelease();
  }
}

function scheduleIdleRelease() {
  if (idleReleaseTimerId) {
    clearTimeout(idleReleaseTimerId);
    idleReleaseTimerId = null;
  }
  if (state.currentJobId || !hasLiveTicket()) {
    return;
  }

  const idleReleaseMs = resolveIdleReleaseMs();
  const remainingMs = Math.max(1000, idleReleaseMs - (Date.now() - lastTicketInteractionAt));
  idleReleaseTimerId = setTimeout(() => {
    void autoReleaseTicketAfterInactivity();
  }, remainingMs);
}

function releaseTicketOnPageHide() {
  if (state.currentJobId || !hasLiveTicket()) {
    return;
  }
  const sessionId = window.localStorage.getItem(TICKET_SESSION_STORAGE_KEY) || "";
  window.localStorage.removeItem(TICKET_SESSION_STORAGE_KEY);
  notifyHomeDashboard("released");
  void fetch("/api/tickets/release", {
    method: "POST",
    credentials: "same-origin",
    keepalive: true,
    headers: sessionId ? { "X-App-Ticket-Session": sessionId } : undefined,
  }).catch(() => {});
}

function updateRunAvailability() {
  const snapshot = state.ticketSnapshot;
  const hasCorpus = Boolean(state.corpusText.trim());
  const hasActiveTicket = !snapshot || snapshot.enabled === false || snapshot.statut === "actif";
  const busy = Boolean(state.currentJobId);
  els.runAnalysisBtn.disabled = !hasCorpus || !hasActiveTicket || busy;
}

function scheduleTicketLoop() {
  if (state.heartbeatTimer) {
    clearInterval(state.heartbeatTimer);
    state.heartbeatTimer = null;
  }
  if (state.ticketTimer) {
    clearTimeout(state.ticketTimer);
    state.ticketTimer = null;
  }

  const snapshot = state.ticketSnapshot;
  if (!snapshot || snapshot.enabled === false) {
    updateReleaseAccessButton();
    return;
  }

  if (snapshot.statut === "actif") {
    state.heartbeatTimer = setInterval(() => {
      callTicketApi("/api/tickets/heartbeat", { method: "POST" })
        .then((payload) => {
          rememberTicketSnapshot(payload);
          renderTicketStatus();
        })
        .catch(() => {});
    }, Number(snapshot.heartbeat_ms || 300000));
  } else {
    const refresh = Number(snapshot.wait_refresh_ms || 10000);
    state.ticketTimer = setTimeout(refreshTicketStatus, refresh);
  }
}

function renderTicketStatus() {
  const snapshot = state.ticketSnapshot;
  const status = ticketStatusClasses(snapshot?.statut);
  els.accessDot.className = `status-dot ${status.dot}`.trim();
  els.accessLabel.textContent = status.label;

  if (!snapshot) {
    els.accessMessage.textContent = "Vérification du ticket en cours.";
    updateReleaseAccessButton();
    updateRunAvailability();
    return;
  }

  const extra = [];
  if (ticketReleasedLocally && !hasLiveTicket(snapshot)) {
    extra.push("Accès libéré pour cette session.");
    extra.push("Cliquez sur « Reprendre l'accès » pour revenir dans la file.");
  }
  if (snapshot.statut === "actif") {
    extra.push(`${snapshot.active || 0} utilisateur(s) actif(s) sur ${snapshot.max_active || 1}.`);
  }
  if (snapshot.statut === "attente" && snapshot.position) {
    extra.push(`Position dans la file : ${snapshot.position}.`);
  }
  if (snapshot.message) {
    extra.push(snapshot.message);
  }
  els.accessMessage.textContent = extra.join(" ");
  updateReleaseAccessButton();
  updateRunAvailability();
  scheduleIdleRelease();
  scheduleTicketLoop();
}

async function refreshTicketStatus() {
  try {
    let payload = await callTicketApi("/api/tickets/status");
    const shouldClaim =
      !ticketReleasedLocally &&
      (payload.statut === "inconnu" || (!payload.ticket_id && payload.enabled !== false));
    if (shouldClaim) {
      payload = await callTicketApi("/api/tickets/claim", { method: "POST" });
    }
    rememberTicketSnapshot(payload);
    renderTicketStatus();
  } catch (error) {
    rememberTicketSnapshot({
      enabled: true,
      statut: "erreur",
      message: error instanceof Error ? error.message : "Erreur ticket.",
    });
    renderTicketStatus();
  }
}

async function releaseAccess() {
  try {
    if (ticketReleasedLocally) {
      rememberTicketSnapshot(await callTicketApi("/api/tickets/claim", { method: "POST" }));
      renderTicketStatus();
      return;
    }

    rememberTicketSnapshot(await callTicketApi("/api/tickets/release", { method: "POST" }));
    window.localStorage.removeItem(TICKET_SESSION_STORAGE_KEY);
    ticketReleasedLocally = true;
    notifyHomeDashboard("released");
    renderTicketStatus();
  } catch (error) {
    els.accessMessage.textContent = error instanceof Error ? error.message : "Libération impossible.";
    updateReleaseAccessButton();
  }
}

async function runAnalysis() {
  if (!state.corpusText.trim()) {
    els.runStatus.textContent = "Importez d’abord un corpus texte.";
    return;
  }
  els.runStatus.textContent = "Lancement du job CHD Rainette...";
  els.runAnalysisBtn.disabled = true;
  setProgress(5, "5%");
  els.statusMessage.textContent = "Initialisation du job.";
  els.logs.textContent = "[info] Lancement du job CHD Rainette...";

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        corpusName: state.corpusName || "corpus.txt",
        corpusText: state.corpusText,
        config: configPayload(),
      }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Lancement impossible.");
    }
    const payload = await response.json();
    state.currentJobId = payload.jobId;
    updateReleaseAccessButton();
    addHistoryEntry(payload.jobId, state.corpusName || "corpus.txt");
    pollJobStatus(payload.jobId);
  } catch (error) {
    els.runStatus.textContent = error instanceof Error ? error.message : "Lancement impossible.";
    els.statusMessage.textContent = els.runStatus.textContent;
    updateRunAvailability();
  }
}

function stopJobPolling() {
  if (state.jobTimer) {
    clearTimeout(state.jobTimer);
    state.jobTimer = null;
  }
}

async function pollJobStatus(jobId) {
  stopJobPolling();
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/status`);
    const payload = await response.json();
    setProgress(payload.progress || 0, `${payload.progress || 0}%`);
    els.statusMessage.textContent = payload.message || "";
    if (payload.logs?.length) {
      els.logs.textContent = payload.logs.join("\n");
    }

    const stateName = String(payload.state || "").toLowerCase();
    if (stateName === "completed" && payload.result) {
      state.currentJobId = "";
      state.currentResult = payload.result;
      els.runStatus.textContent = "Analyse terminée.";
      renderResult(payload.result);
      updateReleaseAccessButton();
      updateRunAvailability();
      return;
    }
    if (stateName === "error" || stateName === "failed") {
      state.currentJobId = "";
      els.runStatus.textContent = payload.message || "Analyse en erreur.";
      updateReleaseAccessButton();
      updateRunAvailability();
      return;
    }
    state.jobTimer = setTimeout(() => pollJobStatus(jobId), 3000);
  } catch (error) {
    state.currentJobId = "";
    els.runStatus.textContent = error instanceof Error ? error.message : "Lecture du statut impossible.";
    updateReleaseAccessButton();
    updateRunAvailability();
  }
}

function renderResult(result) {
  const metadata = result.metadata || {};
  els.metricDocs.textContent = metadata.n_documents_imported ?? "—";
  els.metricSegments.textContent = metadata.n_segments_created ?? "—";
  els.metricAnalyzed.textContent = metadata.n_segments_analyzed ?? "—";
  els.metricClasses.textContent = metadata.n_classes ?? "—";
  els.summaryTable.innerHTML = tableFromRows(result.summaryRows || []);
  els.detailTable.innerHTML = tableFromRows(result.detailRows || []);
  els.artifactList.innerHTML = artifactListHtml(result.artifacts || []);
  configureExplorer(metadata);
  refreshExplorer();
}

function configureExplorer(metadata) {
  const maxK = Math.max(2, Number(metadata.n_classes || 2));
  els.explorerK.max = String(maxK);
  els.explorerK.value = String(maxK);
  els.explorerKValue.textContent = String(maxK);
  els.docsCluster.innerHTML = Array.from({ length: maxK }, (_item, index) => {
    const value = index + 1;
    return `<option value="${value}">Cluster ${value}</option>`;
  }).join("");
  switchPanel("explorateur");
}

async function refreshExplorer() {
  if (!state.currentResult) {
    return;
  }
  syncExplorerUi();
  const jobId = state.currentResult.jobId || state.currentJobId || state.history[0]?.jobId;
  if (!jobId) {
    return;
  }
  els.plotPlaceholder.hidden = false;
  els.plotPlaceholder.textContent = "Génération du graphe Rainette...";
  els.explorerPlot.hidden = true;

  const plotUrl = `/api/jobs/${encodeURIComponent(jobId)}/explorer/plot?${explorerPlotParams().toString()}&ts=${Date.now()}`;
  els.explorerPlot.onload = () => {
    els.plotPlaceholder.hidden = true;
    els.explorerPlot.hidden = false;
  };
  els.explorerPlot.src = plotUrl;

  await refreshDocs();
}

async function refreshDocs() {
  if (!state.currentResult) {
    return;
  }
  const jobId = state.currentResult.jobId || state.history[0]?.jobId;
  if (!jobId) {
    return;
  }
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/explorer/docs?${explorerDocsParams().toString()}`);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Documents indisponibles.");
    }
    const payload = await response.json();
    const currentK = Number(payload.currentK || els.explorerK.value || 2);
    if (Number(els.docsCluster.value || 1) > currentK) {
      els.docsCluster.value = "1";
    }
    if (Array.isArray(payload.clusterChoices)) {
      const currentValue = String(els.docsCluster.value || "1");
      els.docsCluster.innerHTML = payload.clusterChoices
        .map((value) => `<option value="${value}" ${String(value) === currentValue ? "selected" : ""}>Cluster ${value}</option>`)
        .join("");
    }
    els.docsIntro.innerHTML = payload.introHtml || "Aucune information disponible.";
    els.docsSample.innerHTML = payload.documentsHtml || '<p class="empty-state">Aucun document à afficher.</p>';
  } catch (error) {
    els.docsIntro.textContent = error instanceof Error ? error.message : "Lecture des documents impossible.";
    els.docsSample.innerHTML = '<p class="empty-state">Impossible de charger les segments du cluster.</p>';
  }
}

async function refreshExplorerCode() {
  if (!state.currentResult) {
    return;
  }
  const jobId = state.currentResult.jobId || state.history[0]?.jobId;
  if (!jobId) {
    return;
  }
  try {
    const response = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/explorer/code?${explorerPlotParams().toString()}`);
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Code indisponible.");
    }
    const payload = await response.json();
    els.explorerCode.textContent = `${payload.plotCode || ""}\n\n${payload.cutreeCode || ""}`.trim() || "Aucun code disponible.";
  } catch (error) {
    els.explorerCode.textContent = error instanceof Error ? error.message : "Code indisponible.";
  }
}

function bindEvents() {
  els.navLinks.forEach((button) => {
    button.addEventListener("click", () => switchPanel(button.dataset.panelTarget));
  });

  els.importCorpusBtn.addEventListener("click", () => els.corpusFile.click());
  els.corpusFile.addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const text = await readFileAsText(file);
      state.corpusName = file.name;
      state.corpusText = text;
      els.fileInfo.textContent = `${file.name} · ${(file.size / 1024).toFixed(1)} Ko`;
      els.corpusPreview.textContent = text.split(/\r?\n/).slice(0, 50).join("\n") || "(fichier vide)";
      updateRunAvailability();
    } catch (error) {
      els.fileInfo.textContent = error instanceof Error ? error.message : "Lecture du fichier impossible.";
    }
  });

  els.modeDecoupage.addEventListener("change", () => {
    const fixed = els.modeDecoupage.value === "segment_size";
    els.segmentSize.disabled = !fixed;
  });

  els.lemmatisation.addEventListener("change", () => {
    els.uposSelection.disabled = !els.lemmatisation.checked;
  });

  els.explorerK.addEventListener("input", syncExplorerUi);
  els.explorerMeasure.addEventListener("change", syncExplorerUi);
  els.refreshExplorerBtn.addEventListener("click", refreshExplorer);
  els.refreshDocsBtn.addEventListener("click", refreshDocs);
  els.showExplorerCodeBtn.addEventListener("click", refreshExplorerCode);
  els.runAnalysisBtn.addEventListener("click", runAnalysis);
  els.releaseAccessBtn.addEventListener("click", releaseAccess);
  window.addEventListener("pointerdown", rememberUserInteraction, { passive: true });
  window.addEventListener("keydown", rememberUserInteraction);
  window.addEventListener("scroll", rememberUserInteraction, { passive: true });
  window.addEventListener("pagehide", releaseTicketOnPageHide);
  window.addEventListener("beforeunload", releaseTicketOnPageHide);
}

function init() {
  bindEvents();
  renderHistory();
  syncExplorerUi();
  els.segmentSize.disabled = false;
  els.uposSelection.disabled = !els.lemmatisation.checked;
  lastTicketInteractionAt = Date.now();
  updateReleaseAccessButton();
  refreshTicketStatus();
  updateRunAvailability();
}

init();
