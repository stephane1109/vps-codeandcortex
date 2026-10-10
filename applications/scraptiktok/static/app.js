"use strict";
import {appelerApi as api, initialiserNavigateur} from "/static/navigateur.js";
const $ = (id) => document.getElementById(id);
let pendingSearch = null, job = null, polling = false, previewSignature = "";
const navigateur = initialiserNavigateur(message => errorAt("browser-error", message));

function errorAt(id, message) {
  $(id).textContent = message; $(id).hidden = !message;

}
function render(current) {
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
  ["hashtag", "second-hashtag", "limit", "limit-range", "txt-date", "txt-profil", "txt-url", "french-only", "source-collecte", "comptes", "enrichir", "collecter-commentaires", "collecter-reponses", "limite-commentaires", "date-debut", "date-fin", "effacer-periode"].forEach(id => $(id).disabled = busy);
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
  navigateur.actualiser(current);
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
