"use strict";
import {appelerApi, initialiserNavigateur} from "/static/navigateur.js";
// Le cadre est lié à la collecte affichée dans Streamlit, jamais à une recherche cachée.
const etat = document.getElementById("controle-etat");
const erreur = document.getElementById("browser-error");
const navigateur = initialiserNavigateur(message => {
  erreur.textContent = message;
  erreur.hidden = !message;
});
const parametres = new URLSearchParams(location.search);
let identifiant = parametres.get("collecte");
const instanceAttendue = parametres.get("instance") || "";
const sessionAttendue = parametres.get("session") || "";
let interrogation = false;
let collecte = null;
function afficher(instantane) {
  collecte = instantane;
  navigateur.actualiser(instantane);
  etat.textContent = instantane.status === "attention" ? "" : "Aucune intervention nécessaire pour cette collecte. Revenez aux résultats.";
  etat.hidden = instantane.status === "attention";
}
async function signaler(erreur) {
  let message = erreur.message;
  if (erreur.status === 404) {
    // Toujours vérifier le navigateur contre le serveur effectif.
    // Aucune action TikTok, aucune recherche ni création de collecte.
    try {
      const etatServeur = await appelerApi("/api/session");
      if (sessionAttendue && etatServeur.empreinte_session !== sessionAttendue) {
        message = "La fenêtre de contrôle n'utilise pas la même session privée que la collecte. " +
          "Ouvrez le navigateur depuis l'accueil sur le même domaine et actualisez l'application. " +
          "Ne relancez pas une collecte tant que celle-ci est active.";
      } else if (instanceAttendue && etatServeur.instance !== instanceAttendue) {
        message = "La fenêtre de contrôle arrive sur une autre instance du serveur. " +
          "Vérifiez dans Coolify qu'une seule réplique de ScrapTikTok fonctionne " +
          "(un seul conteneur actif pour cette URL). La collecte est conservée sur " +
          "l'instance qui l'a démarrée, pas sur cette instance.";
      } else {
        message = "Cette collecte n'est plus disponible dans la mémoire de ce moteur. " +
          "Il a peut-être redémarré pendant la vérification TikTok. " +
          "Vérifiez les journaux du déploiement avant de relancer une collecte.";
      }
    } catch (sessionErreur) {
      message = "Le navigateur ne peut pas retrouver la session de cette collecte : " +
        sessionErreur.message + ". Rechargez la page d'accueil sous le même domaine.";
    }
  }
  etat.textContent = "Le navigateur intégré ne peut pas s’afficher : " + message;
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
