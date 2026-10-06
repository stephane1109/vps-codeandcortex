"use strict";
const $ = (id) => document.getElementById(id);
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
  const busy = current.busy;
  $("empty-state").hidden = true; $("job-state").hidden = false;
  $("results-title").textContent = "#" + current.hashtag;
  $("status-message").textContent = current.message;
  $("count-captions").textContent = current.captions;
  $("count-processed").textContent = current.processed;
  $("count-discovered").textContent = current.discovered;
  $("progress").value = current.discovered ? 100 * current.processed / current.discovered : 0;
  $("progress-detail").textContent = current.errors ? `${current.errors} publication(s) n’ont pas pu être lues.` : `Objectif : jusqu’à ${current.limit} publications.`;
  const labels = {starting: "Préparation", discovering: "Recherche", attention: "À vous de jouer", collecting: "Collecte en cours", completed: "Terminé", partial: "Résultats partiels", failed: "Accès interrompu", stopped: "Arrêté"};
  $("status-badge").hidden = false; $("status-badge").textContent = labels[current.status] || "En cours";
  $("status-badge").className = "badge " + current.status;
  $("start-button").disabled = busy;
  ["hashtag", "limit", "limit-range", "include-sources"].forEach(id => $(id).disabled = busy);
  $("stop-button").hidden = !busy; $("stop-button").disabled = false;
  $("stop-button").textContent = "Arrêter la collecte";
  $("download").hidden = !current.can_download;
  $("download").href = `/api/jobs/${current.id}/download`;
  $("download").setAttribute("download", `tiktok_${current.hashtag}.txt`);
  $("retention").hidden = !current.can_download;
  $("browser-panel").hidden = current.status !== "attention";
  $("continue-button").disabled = !current.has_frame;
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
  if (frameBusy || pointer || !job || job.status !== "attention") return;
  frameBusy = true;
  const id = job.id;
  try {
    const response = await fetch(`/api/jobs/${id}/frame`, {cache: "no-store"});
    if (response.status !== 200 || job.id !== id || job.status !== "attention") return;
    const blob = await response.blob();
    if (pointer) return;
    const next = URL.createObjectURL(blob);
    $("browser-screen").src = next;
    $("browser-screen").hidden = false; $("screen-loading").hidden = true;
    if (frameUrl) URL.revokeObjectURL(frameUrl);
    frameUrl = next;
  } catch (_) { /* La prochaine actualisation réessaiera. */ }
  finally { frameBusy = false; }
}

async function poll() {
  if (polling || !job?.busy) return;
  polling = true;
  try { render(await api(`/api/jobs/${job.id}`)); errorAt("form-error", ""); }
  catch (error) { errorAt("form-error", error.message); }
  finally { polling = false; }
}
$("limit").addEventListener("input", () => $("limit-range").value = $("limit").value);
$("limit-range").addEventListener("input", () => $("limit").value = $("limit-range").value);
$("search-form").addEventListener("submit", async event => {
  event.preventDefault(); errorAt("form-error", "");
  $("start-button").disabled = true;
  try {
    render(await api("/api/jobs", {hashtag: $("hashtag").value.trim(), limit: Number($("limit").value), include_sources: $("include-sources").checked}));
  } catch (error) { errorAt("form-error", error.message); $("start-button").disabled = false; }
});
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
async function sendAction(action) {
  if (!job || job.status !== "attention") return;
  try { await api(`/api/jobs/${job.id}/action`, action); }
  catch (error) { errorAt("browser-error", error.message); }
}
function position(event) {
  const rect = $("browser-screen").getBoundingClientRect();
  return {x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))};
}
$("browser-screen").addEventListener("pointerdown", event => {
  if (event.button !== 0) return;
  event.preventDefault(); $("browser-screen").focus();
  pointer = {id: event.pointerId, points: [position(event)]};
  $("browser-screen").setPointerCapture(event.pointerId);
});
$("browser-screen").addEventListener("pointermove", event => {
  if (!pointer || pointer.id !== event.pointerId) return;
  const point = position(event), last = pointer.points.at(-1);
  if (Math.hypot(point.x - last.x, point.y - last.y) > 0.003) pointer.points.push(point);
  if (pointer.points.length > 70) pointer.points = pointer.points.filter((_, i) => i === 0 || i % 2 === 1);
});
$("browser-screen").addEventListener("pointerup", event => {
  if (!pointer || pointer.id !== event.pointerId) return;
  pointer.points.push(position(event));
  const points = pointer.points, start = points[0], end = points.at(-1);
  pointer = null;
  sendAction({kind: points.length > 3 || Math.hypot(start.x - end.x, start.y - end.y) > 0.007 ? "drag" : "click", points});
});
$("browser-screen").addEventListener("pointercancel", () => pointer = null);
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
api("/api/session").then(data => { if (data.job) { $("hashtag").value = data.job.hashtag; render(data.job); } }).catch(error => errorAt("form-error", error.message));
setInterval(poll, 1200);
