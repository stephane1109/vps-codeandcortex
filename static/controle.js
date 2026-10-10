"use strict";
import {appelerApi, initialiserNavigateur} from "/static/navigateur.js";
// Le cadre est lié à la collecte affichée dans Streamlit, jamais à une recherche cachée.
const etat = document.getElementById("controle-etat");
const erreur = document.getElementById("browser-error");
const navigateur = initialiserNavigateur(message => {
  erreur.textContent = message;
  erreur.hidden = !message;
});
let identifiant = new URLSearchParams(location.search).get("collecte");
let interrogation = false;
let collecte = null;
function afficher(instantane) {
  collecte = instantane;
  navigateur.actualiser(instantane);
  etat.textContent = instantane.status === "attention" ? "" : "Aucune intervention nécessaire pour cette collecte. Revenez aux résultats.";
  etat.hidden = instantane.status === "attention";
}
function signaler(erreur) {
  etat.textContent = "Le navigateur intégré ne peut pas s’afficher : " + erreur.message;
  etat.hidden = false;
}
async function actualiser() {
  if (interrogation || !identifiant) return;
  interrogation = true;
  try { afficher(await appelerApi(`/api/jobs/${identifiant}`)); }
  catch (erreur) { signaler(erreur); }
  finally { interrogation = false; }
}
async function initialiser() {
  try {
    if (identifiant && !/^[a-f0-9]{32}$/.test(identifiant)) throw new Error("Identifiant de collecte invalide.");
    if (!identifiant) {
      // Compatibilité avec un ancien lien de contrôle : reprise une seule fois.
      const session = await appelerApi("/api/session");
      if (!session.job) {
        etat.textContent = "Aucune collecte active dans cette session. Revenez à l’accueil pour lancer une recherche.";
        return;
      }
      identifiant = session.job.id;
    }
    await actualiser();
    setInterval(() => { if (collecte?.busy) actualiser(); }, 1200);
  } catch (erreur) { signaler(erreur); }
}
initialiser();
