"use strict";
if (new URLSearchParams(location.search).has("controle")) document.body.classList.add("mode-controle");
const $ = (id) => document.getElementById(id);
let actionBusy = false, pendingSearch = null;
const actionQueue = [];
let job = null, polling = false, frameBusy = false, frameUrl = null, pointer = null, previewSignature = "";

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {cache: "no-store"} : {
    method: "POST", headers: {"Content-Type": "application/json", "X-ScrapTikTok": "1"}, body: JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Vérifiez le hashtag et le nombre de publications (1 à 300).";
    throw new Error(detail);
  }
  return data;
}
function errorAt(id, message) { $(id).textContent = message; $(id).hidden = !message; }
function render(current) {
  const previous = job?.status;
  job = current;
  const busy = current.busy || current.video_busy;
  $("empty-state").hidden = true; $("job-state").hidden = false;
  $("results-title").textContent = (current.libelle || (current.hashtags || [current.hashtag]).map(tag => "#" + tag).join(current.operator === "OR" ? " OU " : " ET ")) + (current.french_only ? " · français" : "");
  $("status-message").textContent = current.message;
  $("count-captions").textContent = current.captions;
  $("count-processed").textContent = current.processed;
  $("count-discovered").textContent = current.discovered;
  $("progress").value = current.discovered ? 100 * current.processed / current.discovered : 0;
  $("progress-detail").textContent = current.errors ? `${current.errors} publication(s) n’ont pas pu être lues.` : `Jusqu’à ${current.limit} publications par source. ${current.filtered || 0} texte(s) écarté(s) par le filtre.`;
  if (current.french_only) $("progress-detail").textContent += ` Filtre français : ${current.non_french || 0} texte(s) identifié(s) dans une autre langue écartés ; ${current.language_unknown || 0} texte(s) de langue indéterminée conservés.`;
  if (current.date_debut || current.date_fin) $("progress-detail").textContent += ` Période UTC : ${current.date_debut || "sans début"} → ${current.date_fin || "sans fin"} (inclus). ${current.hors_periode || 0} hors période, ${current.dates_indeterminees || 0} sans date exploitable.`;
  const labels = {starting: "Préparation", discovering: "Recherche", attention: "À vous de jouer", collecting: "Collecte en cours", completed: "Terminé", partial: "Résultats partiels", failed: "Accès interrompu", stopped: "Arrêté"};
  $("status-badge").hidden = false; $("status-badge").textContent = labels[current.status] || "En cours";
  $("status-badge").className = "badge " + current.status;
  $("start-button").disabled = busy;
  ["hashtag", "second-hashtag", "limit", "limit-range", "include-sources", "french-only", "source-collecte", "comptes", "enrichir", "collecter-commentaires", "collecter-reponses", "limite-commentaires", "date-debut", "date-fin", "effacer-periode"].forEach(id => $(id).disabled = busy);
  $("stop-button").hidden = !current.busy; $("stop-button").disabled = false;
  $("stop-button").textContent = "Arrêter la collecte";
  $("download").hidden = !current.can_download;
  $("download").href = `/api/jobs/${current.id}/download`;
  $("download").setAttribute("download", current.filename || `tiktok_${current.hashtag}.txt`);
  $("retention").hidden = !current.can_download;
  document.querySelectorAll('#liste-presse input').forEach(e => e.disabled = busy);
  $("download-archive").hidden = !current.archive_prete || busy;
  $("download-archive").href = `/api/jobs/${current.id}/archive`;
  $("video-options").hidden = !current.archive_prete || current.busy || !current.video_disponible;
  $("video-start").disabled = busy;
  $("video-stop").hidden = !current.video_busy;
  const etatsVideo = {en_cours: "Analyse audiovisuelle en cours…", termine: "Analyse terminée : les résultats sont dans l’archive.", partiel: "Analyse partielle : consultez le journal de l’archive pour les limites rencontrées.", echec: "L’analyse a échoué. Les exports de collecte restent disponibles.", interrompu: "Analyse interrompue. La dernière archive finalisée reste disponible."};
  $("video-status").textContent = etatsVideo[current.video_statut] || (current.archive_prete && !current.video_disponible ? "Le traitement audiovisuel peut être activé par l’administrateur du serveur." : "");
  $("browser-panel").hidden = current.status !== "attention";
  $("continue-button").disabled = !current.has_frame || !!pointer || actionBusy || actionQueue.length > 0;
  if (current.status === "attention") {
    errorAt("browser-error", current.action_error);
    if (previous !== "attention") $("browser-panel").scrollIntoView({behavior: "smooth", block: "start"});
    updateFrame();
  } else {
    $("browser-screen").hidden = true; $("screen-loading").hidden = false;
  }
  const signature = JSON.stringify(current.preview);
  if (signature !== previewSignature) {
    previewSignature = signature;
    $("preview").replaceChildren();
    current.preview.forEach(record => {
      const div = document.createElement("div"); div.className = "preview-item";
      const author = document.createElement("strong"); author.textContent = "@" + record.author;
      const text = document.createElement("p"); text.textContent = record.description;
      div.append(author, text); $("preview").append(div);
    });
  }
  $("preview-section").hidden = !current.preview.length;
}

async function updateFrame() {
  if (frameBusy || !job || job.status !== "attention") return;
  frameBusy = true;
  const id = job.id;
  try {
    const response = await fetch(`/api/jobs/${id}/frame`, {cache: "no-store", signal: AbortSignal.timeout(8000)});
    if (!response.ok) throw new Error("Image indisponible");
    if (response.status !== 200 || job.id !== id || job.status !== "attention") return;
    const blob = await response.blob();
    if (job?.id !== id || job.status !== "attention") return;
    const next = URL.createObjectURL(blob);
    $("browser-screen").src = next;
    $("browser-screen").hidden = false; $("screen-loading").hidden = true;
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    frameUrl = next;
    $("screen-status").textContent = "Image actualisée · Maintenez le curseur et faites-le glisser lentement.";
  } catch (_) { $("screen-status").textContent = "Actualisation interrompue. Nouvelle tentative en cours…"; }
  finally { frameBusy = false; }
}

async function poll() {
  if (polling || !(job?.busy || job?.video_busy)) return;
  polling = true;
  try { render(await api(`/api/jobs/${job.id}`)); errorAt("form-error", ""); }
  catch (error) { errorAt("form-error", error.message); }
  finally { polling = false; }
}
$("effacer-periode").addEventListener("click", () => { $("date-debut").value = ""; $("date-fin").value = ""; });
$("limit").addEventListener("input", () => $("limit-range").value = $("limit").value);
$("limit-range").addEventListener("input", () => $("limit").value = $("limit-range").value);
async function startSearch(settings) {
  $("start-button").disabled = true;
  try { render(await api("/api/jobs", settings)); }
  catch (error) { errorAt("form-error", error.message); $("start-button").disabled = false; }
}
$("search-form").addEventListener("submit", event => {
  event.preventDefault(); errorAt("form-error", "");
  const settings = {hashtag: $("hashtag").value.trim(), second_hashtag: $("second-hashtag").value.trim(), limit: Number($("limit").value), variables_txt: ["date", "profil", "url"].filter(v => $("txt-" + v).checked), french_only: $("french-only").checked, date_debut: $("date-debut").value || null, date_fin: $("date-fin").value || null,
    source_collecte: $("source-collecte").value, comptes: $("comptes").value.split(/[\s,;]+/).filter(Boolean),
    medias: Array.from(document.querySelectorAll('#liste-presse input:checked')).map(e => e.value),
    enrichir: $("enrichir").checked, collecter_commentaires: $("collecter-commentaires").checked,
    collecter_reponses: $("collecter-reponses").checked, limite_commentaires: Number($("limite-commentaires").value)};
  if (settings.date_debut && settings.date_fin && settings.date_debut > settings.date_fin) {
    errorAt("form-error", "La date de début doit précéder ou égaler la date de fin."); return;
  }
  if (settings.second_hashtag) {
    pendingSearch = settings;
    $("combination-description").textContent = `#${settings.hashtag.replace(/^#/, "")} et #${settings.second_hashtag.replace(/^#/, "")}`;
    $("combination-dialog").showModal();
  } else { startSearch(settings); }
});
$("combination-form").addEventListener("submit", event => {
  event.preventDefault();
  if (!pendingSearch) return;
  const settings = {...pendingSearch, operator: document.querySelector('input[name="operator"]:checked').value};
  pendingSearch = null;
  $("combination-dialog").close();
  startSearch(settings);
});
$("cancel-combination").addEventListener("click", () => $("combination-dialog").close());
$("combination-dialog").addEventListener("close", () => { pendingSearch = null; });
$("stop-button").addEventListener("click", async () => {
  $("stop-button").disabled = true; $("stop-button").textContent = "Arrêt en cours…";
  try { await api(`/api/jobs/${job.id}/stop`, {}); }
  catch (error) { errorAt("form-error", error.message); }
});
$("continue-button").addEventListener("click", async () => {
  $("continue-button").disabled = true;
  try { await api(`/api/jobs/${job.id}/continue`, {}); }
  catch (error) { errorAt("browser-error", error.message); }
});
function sendAction(action) {
  if (!job || job.status !== "attention") return;
  // Une seule requête en vol ; les mouvements intermédiaires sont regroupés.
  const pending = actionQueue.at(-1);
  if (action.kind === "pointer_move" && pending?.action.kind === "pointer_move") {
    pending.action = action;
  } else {
    actionQueue.push({id: job.id, action});
  }
  $("continue-button").disabled = true;
  flushActions();
}
async function flushActions() {
  if (actionBusy) return;
  actionBusy = true;
  try {
    while (actionQueue.length) {
      const next = actionQueue.shift();
      if (job?.id !== next.id || job.status !== "attention") continue;
      await api(`/api/jobs/${next.id}/action`, next.action);
    }
  } catch (error) {
    actionQueue.length = 0;
    pointer = null;
    errorAt("browser-error", error.message);
    // Libère le bouton distant même si le geste ou la connexion a été interrompu.
    if (job?.status === "attention") {
      try { await api(`/api/jobs/${job.id}/action`, {kind: "pointer_cancel"}); } catch (_) {}
    }
  } finally {
    actionBusy = false;
    $("continue-button").disabled = !!pointer || !job?.has_frame;
    updateFrame();
  }
}
function position(event) {
  const rect = $("browser-screen").getBoundingClientRect();
  return {x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))};
}
$("browser-screen").addEventListener("dragstart", event => event.preventDefault());
$("browser-screen").addEventListener("pointerdown", event => {
  if (event.button !== 0 || pointer || actionBusy || job?.status !== "attention") return;
  event.preventDefault(); $("browser-screen").focus({preventScroll: true});
  pointer = {id: event.pointerId};
  $("screen-container").setPointerCapture(event.pointerId);
  sendAction({kind: "pointer_down", points: [position(event)]});
});
window.addEventListener("pointermove", event => {
  if (!pointer || pointer.id !== event.pointerId) return;
  if (!(event.buttons & 1)) { cancelPointer(); return; }
  event.preventDefault();
  sendAction({kind: "pointer_move", points: [position(event)]});
});
window.addEventListener("pointerup", event => {
  if (!pointer || pointer.id !== event.pointerId) return;
  pointer = null;
  sendAction({kind: "pointer_up", points: [position(event)]});
  if ($("screen-container").hasPointerCapture(event.pointerId)) $("screen-container").releasePointerCapture(event.pointerId);
});
function cancelPointer() {
  if (!pointer) return;
  pointer = null;
  sendAction({kind: "pointer_cancel"});
}
window.addEventListener("pointercancel", cancelPointer);
$("screen-container").addEventListener("lostpointercapture", event => {
  if (!(event.buttons & 1)) cancelPointer();
});
window.addEventListener("blur", cancelPointer);
document.addEventListener("visibilitychange", () => { if (document.hidden) cancelPointer(); });
$("browser-screen").addEventListener("keydown", event => {
  if (["Enter", "Tab", "Backspace", "Escape"].includes(event.key)) {
    event.preventDefault(); sendAction({kind: "key", key: event.key});
  }
});
$("typing-form").addEventListener("submit", event => {
  event.preventDefault(); const text = $("remote-text").value; $("remote-text").value = "";
  if (text) sendAction({kind: "text", text});
});
document.querySelectorAll("[data-key]").forEach(button => button.addEventListener("click", () => sendAction({kind: "key", key: button.dataset.key})));
document.querySelectorAll("[data-scroll]").forEach(button => button.addEventListener("click", () => sendAction({kind: "scroll", delta: Number(button.dataset.scroll)})));
function actualiserSource() {
  const source = $("source-collecte").value;
  $("comptes-section").hidden = source !== "comptes";
  $("presse-section").hidden = source !== "presse";
  $("hashtag").required = source === "hashtags";
  $("hashtag-label").textContent = source === "hashtags" ? "Votre hashtag" : "Filtrer les légendes par hashtag (facultatif)";
}
$("source-collecte").addEventListener("change", actualiserSource);
$("collecter-reponses").addEventListener("change", () => { if ($("collecter-reponses").checked) $("collecter-commentaires").checked = true; });
$("video-start").addEventListener("click", async () => {
  $("video-start").disabled = true;
  try { render(await api(`/api/jobs/${job.id}/video`, {audio: $("video-audio").checked, ocr: $("video-ocr").checked, transcription: $("video-transcription").checked, embeddings: $("video-embeddings").checked, telecharger_modeles: $("video-modeles").checked})); }
  catch (erreur) { errorAt("form-error", erreur.message); $("video-start").disabled = false; }
});
$("video-stop").addEventListener("click", async () => {
  try { await api(`/api/jobs/${job.id}/video/stop`, {}); } catch (erreur) { errorAt("form-error", erreur.message); }
});
api("/api/presse").then(data => {
  data.medias.forEach(media => {
    const label = document.createElement("label"); label.className = "checkbox";
    const input = document.createElement("input"); input.type = "checkbox"; input.value = media.id;
    input.checked = !!job?.medias?.includes(media.id); input.disabled = !!(job?.busy || job?.video_busy);
    const texte = document.createElement("span"); texte.textContent = `${media.nom} (@${media.compte})`;
    label.append(input, texte); $("liste-presse").append(label);
  });
}).catch(erreur => errorAt("form-error", erreur.message));
api("/api/session").then(data => { if (data.job) { $("date-debut").value = data.job.date_debut || ""; $("date-fin").value = data.job.date_fin || ""; $("periode-options").open = !!(data.job.date_debut || data.job.date_fin); $("source-collecte").value = data.job.source_collecte || "hashtags"; $("comptes").value = (data.job.comptes || []).join(", "); $("enrichir").checked = !!data.job.enrichir; actualiserSource(); document.querySelectorAll('#liste-presse input').forEach(e => e.checked = (data.job.medias || []).includes(e.value)); $("hashtag").value = data.job.hashtag; $("second-hashtag").value = data.job.second_hashtag || ""; $("french-only").checked = !!data.job.french_only; const variables = data.job.variables_txt ?? (data.job.inclure_metadonnees_txt ? ["date", "profil", "url"] : data.job.include_sources !== false ? ["profil", "url"] : []); ["date", "profil", "url"].forEach(v => $("txt-" + v).checked = variables.includes(v)); document.querySelector(`input[name="operator"][value="${data.job.operator === "OR" ? "OR" : "AND"}"]`).checked = true; render(data.job); } }).catch(error => errorAt("form-error", error.message));
setInterval(poll, 1200);
setInterval(updateFrame, 350);
