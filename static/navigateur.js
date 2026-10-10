"use strict";
// Contrôle du navigateur intégré dans Streamlit ; aucune création de collecte.
const $ = id => document.getElementById(id);
export async function appelerApi(path, body) {
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

export function initialiserNavigateur(afficherErreur) {
  let job = null, actionBusy = false, frameBusy = false, frameUrl = null, pointer = null;
  const actionQueue = [];
  const api = appelerApi;
  const errorAt = (_id, message) => afficherErreur(message);
  function actualiser(collecte) {
    const precedent = job?.status;
    job = collecte;
    $("browser-panel").hidden = collecte.status !== "attention";
    $("continue-button").disabled = !collecte.has_frame || !!pointer || actionBusy || actionQueue.length > 0;
    if (collecte.status === "attention") {
      afficherErreur(collecte.action_error || "");
      if (precedent !== "attention") $("browser-panel").scrollIntoView({behavior:"smooth", block:"start"});
      actualiserImage();
    } else {
      $("browser-screen").hidden = true;
      $("screen-loading").hidden = false;
    }
  }
async function actualiserImage() {
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

$("continue-button").addEventListener("click", async () => {
  $("continue-button").disabled = true;
  try { await api(`/api/jobs/${job.id}/continue`, {}); }
  catch (error) { errorAt("browser-error", error.message); }
});
function envoyerAction(action) {
  if (!job || job.status !== "attention") return;
  // Une seule requête en vol ; les mouvements intermédiaires sont regroupés.
  const pending = actionQueue.at(-1);
  if (action.kind === "pointer_move" && pending?.action.kind === "pointer_move") {
    pending.action = action;
  } else {
    actionQueue.push({id: job.id, action});
  }
  $("continue-button").disabled = true;
  traiterActions();
}
async function traiterActions() {
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
    actualiserImage();
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
  envoyerAction({kind: "pointer_down", points: [position(event)]});
});
window.addEventListener("pointermove", event => {
  if (!pointer || pointer.id !== event.pointerId) return;
  if (!(event.buttons & 1)) { annulerPointeur(); return; }
  event.preventDefault();
  envoyerAction({kind: "pointer_move", points: [position(event)]});
});
window.addEventListener("pointerup", event => {
  if (!pointer || pointer.id !== event.pointerId) return;
  pointer = null;
  envoyerAction({kind: "pointer_up", points: [position(event)]});
  if ($("screen-container").hasPointerCapture(event.pointerId)) $("screen-container").releasePointerCapture(event.pointerId);
});
function annulerPointeur() {
  if (!pointer) return;
  pointer = null;
  envoyerAction({kind: "pointer_cancel"});
}
window.addEventListener("pointercancel", annulerPointeur);
$("screen-container").addEventListener("lostpointercapture", event => {
  if (!(event.buttons & 1)) annulerPointeur();
});
window.addEventListener("blur", annulerPointeur);
document.addEventListener("visibilitychange", () => { if (document.hidden) annulerPointeur(); });
$("browser-screen").addEventListener("keydown", event => {
  if (["Enter", "Tab", "Backspace", "Escape"].includes(event.key)) {
    event.preventDefault(); envoyerAction({kind: "key", key: event.key});
  }
});
$("typing-form").addEventListener("submit", event => {
  event.preventDefault(); const text = $("remote-text").value; $("remote-text").value = "";
  if (text) envoyerAction({kind: "text", text});
});
document.querySelectorAll("[data-key]").forEach(button => button.addEventListener("click", () => envoyerAction({kind: "key", key: button.dataset.key})));
document.querySelectorAll("[data-scroll]").forEach(button => button.addEventListener("click", () => envoyerAction({kind: "scroll", delta: Number(button.dataset.scroll)})));

  setInterval(actualiserImage, 350);
  return {actualiser};
}
