"""Commentaires publics visibles, chargement progressif et diagnostics explicites."""
import hashlib
import time
from .engagement import convertir_compteur
from .reponses import rattacher_reponses

# Un marqueur comment-level peut être porté par le texte lui-même ou son conteneur.
OUTILS_COMMENTAIRES_JS = r"""
const visible = e => !!e && e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden';
const selecteurTexte = '[data-e2e="comment-text"], [data-e2e="comment-content"], [data-e2e="comment-level-1"], [data-e2e="comment-level-2"], [class*="PCommentText"], [class*="SpanCommentText"]';
const selecteurPanneau = '[data-e2e="comment-list"], [data-e2e="comment-list-container"], [class*="DivCommentListContainer"], [class*="DivCommentListWrapper"]';
const panneaux = Array.from(document.querySelectorAll(selecteurPanneau)).filter(visible);
const noeuds = Array.from(document.querySelectorAll(selecteurTexte)).filter(visible);
const textes = [...new Set(noeuds.map(e => {
  const enfant = e.querySelector('[data-e2e="comment-text"], [data-e2e="comment-content"], [class*="PCommentText"], [class*="SpanCommentText"]');
  if (enfant) return enfant;
  if (e.matches('p,span') || !e.children.length) return e;
  return e.querySelector('p');
}).filter(e => visible(e) && e.innerText?.trim()))];
function carte(e) {
  const explicite = e.closest('[data-comment-id], [data-e2e="comment-item"], [class*="DivCommentItemContainer"]');
  if (explicite) return explicite;
  let parent = e.parentElement;
  for (let n=0; parent && n<6; n++,parent=parent.parentElement) {
    if (parent.matches(selecteurPanneau)) break;
    if (parent.querySelector('a[href*="/@"]')) return parent;
  }
  return e.parentElement || e;
}
function identifiant(e) {
  if (!e) return null;
  const brut=e.getAttribute('data-comment-id');
  if (brut) return brut;
  return /^comment[-_]([0-9]+)$/.exec(e.id || '')?.[1] || null;
}
"""
SCRIPT_COMMENTAIRES = OUTILS_COMMENTAIRES_JS + r"""
return textes.map(e => {
  const c=carte(e);
  const reponse=!!e.closest('[data-e2e="comment-level-2"], [class*="DivReplyContainer"]') || !!c.closest('[data-e2e="comment-level-2"]');
  const parent=reponse ? c.parentElement?.closest('[data-comment-id], [data-e2e="comment-level-1"], [class*="DivCommentItemContainer"]') : null;
  const auteur=c.querySelector('[data-e2e="comment-username"] a, a[data-e2e="comment-username"], [data-e2e="comment-user-name"] a, a[href*="/@"]');
  let nom=null;
  try { nom=/\/@([^/]+)/.exec(new URL(auteur?.getAttribute('href'),location.href).pathname)?.[1] || null; } catch (_) {}
  const date=c.querySelector('[data-e2e="comment-time"], time, [class*="SpanCreatedTime"]');
  const aime=c.querySelector('[data-e2e="comment-like-count"], [class*="SpanLikeCount"], [class*="SpanCount"]');
  return {id:identifiant(c) || identifiant(e),parent_id:identifiant(parent),reponse,
    texte:e.innerText.trim(),auteur:nom,date_brute:date?.getAttribute('datetime') || date?.innerText || null,
    likes:aime?.innerText || null};
});
"""
SCRIPT_OUVERTURE = OUTILS_COMMENTAIRES_JS + r"""
if (textes.length || panneaux.length) return {statut:'visible'};
const cibles=Array.from(document.querySelectorAll('[data-e2e="browse-comment"], [data-e2e="comment-icon"], [data-e2e="comment-count"], [data-e2e="comment-button"], button[aria-label], [role="tab"][aria-label]'));
const cible=cibles.find(e=>visible(e) && (e.matches('[data-e2e="browse-comment"], [data-e2e="comment-icon"], [data-e2e="comment-count"], [data-e2e="comment-button"]') || /^(comments?|commentaires?)(\b|\s)/i.test(e.getAttribute('aria-label') || '')));
if (!cible) return {statut:'bouton_introuvable'};
(cible.closest('button,[role="button"],[role="tab"]') || cible).click();
return {statut:'ouverture_demandee'};
"""
SCRIPT_ETAT = OUTILS_COMMENTAIRES_JS + r"""
const messages=Array.from(document.querySelectorAll('[data-e2e="comment-empty"], [data-e2e="comment-disabled"], [data-e2e="comment-error"], [class*="DivCommentEmpty"], [role="alert"]')).filter(visible).map(e=>e.innerText || '');
// Examiner aussi les panneaux vides, sans prendre une phrase d’un commentaire pour un état.
if (!textes.length) messages.push(...panneaux.map(e=>e.innerText || ''));
const texte=messages.join('\n').toLowerCase();
return {panneau_visible:!!panneaux.length,elements_detectes:noeuds.length,textes_lisibles:textes.length,
 desactives:/comments? (are |have been )?(turned off|disabled)|commentaires? (sont )?désactivés/.test(texte),
 vide:/no comments? yet|be the first to comment|aucun commentaire|soyez le premier à commenter/.test(texte),
 erreur:/something went wrong|couldn.t load|unable to load|une erreur est survenue|impossible de charger/.test(texte)};
"""
SCRIPT_DEFILEMENT = OUTILS_COMMENTAIRES_JS + r"""
const candidats=[];
for (const origine of [...textes.slice(-1),...panneaux]) {
  for(let e=origine;e;e=e.parentElement) {
    if (visible(e) && e.scrollHeight>e.clientHeight+4 && /(auto|scroll|overlay)/.test(getComputedStyle(e).overflowY)) candidats.push(e);
  }
}
const e=candidats[0] || ((panneaux.length || textes.length) ? document.scrollingElement : null);
if(!e) return {conteneur:false,deplace:false};
const avant=e.scrollTop;
// Un petit recul en fin de liste permet au chargement suivant de revoir le bas du panneau.
if(e.scrollTop+e.clientHeight>=e.scrollHeight-4 && e.scrollTop>0) e.scrollTop=Math.max(0,e.scrollTop-160);
else e.scrollTop+=Math.max(400,e.clientHeight*0.8);
e.dispatchEvent(new Event('scroll',{bubbles:true}));
return {conteneur:true,deplace:e.scrollTop!==avant};
"""
SCRIPT_REPONSES = OUTILS_COMMENTAIRES_JS + r"""
const cibles=Array.from(document.querySelectorAll('[data-e2e="comment-more"], [data-e2e="view-more-1"], [data-e2e="view-more-2"]'));
for(const p of panneaux) cibles.push(...p.querySelectorAll('button,[role="button"]'));
const e=cibles.find(e=>visible(e) && !/hide|less|masquer|moins/i.test(e.innerText || '') && (e.matches('[data-e2e="comment-more"], [data-e2e="view-more-1"], [data-e2e="view-more-2"]') || /(?:view|see|voir|afficher).*(?:replies|réponses)/i.test(e.innerText || '')));
if(e){e.click();return true;} return false;
"""


def normaliser_commentaire(donnee, publication_id, date):
    texte = str(donnee.get("texte") or donnee.get("text") or "").strip()
    if not texte:
        return None
    # Les données issues d’une autre vidéo sont exclues.
    cible = donnee.get("aweme_id", donnee.get("publication_id"))
    if cible is not None and str(cible) != str(publication_id):
        return None
    identifiant = donnee.get("id") or donnee.get("cid")
    parent = donnee.get("parent_id") or donnee.get("reply_id")
    if str(parent) == "0": parent = None
    auteur = donnee.get("auteur")
    if not auteur and isinstance(donnee.get("user"), dict):
        auteur = donnee["user"].get("unique_id") or donnee["user"].get("uniqueId")
    if identifiant is None:
        contenu = str(publication_id) + "\0" + str(parent) + "\0" + str(auteur) + "\0" + texte
        identifiant = "local_" + hashlib.sha256(contenu.encode()).hexdigest()[:24]
    return {"id": str(identifiant), "publication_id": str(publication_id), "parent_id": str(parent) if parent else None,
            "est_reponse": bool(parent or donnee.get("reponse")), "auteur": auteur, "texte": texte,
            "date_brute": donnee.get("date_brute") or donnee.get("create_time"), "observe_le": date,
            "likes": convertir_compteur(donnee.get("likes", donnee.get("digg_count"))),
            "id_observe": not str(identifiant).startswith("local_"), "brut": dict(donnee), "source": "page_visible"}


MESSAGES = {
    "limite": "Limite de textes de commentaires atteinte.",
    "partiel": "Commentaires accessibles récupérés ; liste non exhaustive.",
    "vide_confirme": "TikTok affiche qu’aucun commentaire n’est disponible.",
    "desactives": "TikTok indique que les commentaires sont désactivés.",
    "verification_tiktok": "Un CAPTCHA empêche le chargement des commentaires.",
    "connexion_requise": "Une invitation à se connecter empêche l’accès aux commentaires dans cette session anonyme.",
    "erreur_chargement": "TikTok affiche une erreur de chargement des commentaires.",
    "page_differente": "Le navigateur n’affiche plus la publication attendue.",
    "panneau_introuvable": "Le panneau des commentaires n’a pas pu être ouvert.",
    "extraction_impossible": "Des éléments de commentaires sont présents mais aucun texte n’a pu être extrait.",
    "chargement_incomplet": "Aucun texte de commentaire chargé après plusieurs tentatives ; cela ne signifie pas que le compteur est nul.",
    "inaccessible": "Une erreur du navigateur a interrompu la lecture des commentaires.",
}


def collecter_commentaires(navigateur, publication, limite=50, reponses=False,
                           verifier=lambda: None, pause=None, interact=None):
    """Ouvrir le panneau et attendre ses chargements dans la session Selenium existante."""
    from scraptiktok import (canonical_post, utc_now, type_intervention_tiktok,
                            fermer_invitation_connexion, WebDriverException, est_erreur_session)
    if not 1 <= limite <= 500:
        raise ValueError("Limite de commentaires : 1 à 500.")
    pause = pause if pause is not None else time.sleep
    resultats = {}
    inactif = interventions = ouvertures = 0
    etat = {}
    statut = "chargement_incomplet"
    diagnostic = {"tours": 0, "defilements": 0, "ouvertures": 0, "elements_detectes": 0}
    annonces = (publication.get("engagement") or {}).get("commentaires", {}).get("valeur")
    try:
        for tour in range(min(60, max(20, limite // 5 + 12))):
            verifier()
            courant = canonical_post(navigateur.current_url)
            if not courant or courant[0] != str(publication["id"]):
                statut = "page_differente"
                break
            diagnostic["tours"] = tour + 1
            nature = type_intervention_tiktok(navigateur)
            if nature == "captcha":
                if interact is None or interventions >= 2:
                    statut = "verification_tiktok"
                    break
                interventions += 1
                interact("TikTok affiche un CAPTCHA pendant le chargement des commentaires. Terminez la vérification, puis continuez.")
                inactif = 0
                continue
            if nature == "connexion":
                fermer_invitation_connexion(navigateur)
            avant = len(resultats)
            donnees = navigateur.execute_script(SCRIPT_COMMENTAIRES) or []
            for donnee in donnees:
                if not isinstance(donnee, dict):
                    continue
                commentaire = normaliser_commentaire(donnee, publication["id"], utc_now())
                if commentaire and (reponses or not commentaire["est_reponse"]) and len(resultats) < limite:
                    resultats.setdefault(commentaire["id"], commentaire)
            etat = navigateur.execute_script(SCRIPT_ETAT) or {}
            diagnostic["elements_detectes"] = max(diagnostic["elements_detectes"], etat.get("elements_detectes", 0))
            if len(resultats) >= limite:
                statut = "limite"
                break
            inactif = inactif + 1 if len(resultats) == avant else 0
            if etat.get("desactives"):
                statut = "desactives"
                break
            if etat.get("erreur") and inactif >= 4:
                statut = "erreur_chargement"
                break
            # Une indication vide contradictoire avec le compteur mérite plusieurs attentes.
            if etat.get("vide") and not resultats and not annonces and inactif >= 3:
                statut = "vide_confirme"
                break
            if not donnees and not etat.get("panneau_visible") and ouvertures < 2:
                ouverture = navigateur.execute_script(SCRIPT_OUVERTURE) or {}
                if ouverture.get("statut") == "ouverture_demandee":
                    ouvertures += 1
                    diagnostic["ouvertures"] = ouvertures
                elif tour == 0:
                    diagnostic["ouverture_initiale"] = ouverture.get("statut")
            if inactif >= (6 if resultats else 10):
                if nature == "connexion" and type_intervention_tiktok(navigateur) == "connexion":
                    statut = "connexion_requise"
                elif resultats:
                    statut = "partiel"
                elif etat.get("elements_detectes"):
                    statut = "extraction_impossible"
                elif not etat.get("panneau_visible"):
                    statut = "panneau_introuvable"
                break
            if reponses:
                navigateur.execute_script(SCRIPT_REPONSES)
            defilement = navigateur.execute_script(SCRIPT_DEFILEMENT) or {}
            if defilement.get("deplace"):
                diagnostic["defilements"] += 1
            pause(0.8)
        else:
            statut = "partiel" if resultats else "chargement_incomplet"
    except WebDriverException as erreur:
        if est_erreur_session(erreur):
            raise
        statut = "inaccessible"
        diagnostic["exception"] = type(erreur).__name__
    return {"commentaires": rattacher_reponses(list(resultats.values())), "statut": statut,
            "message": MESSAGES[statut], "exhaustif": False, "limite": limite,
            "annonces": annonces, "recuperes": len(resultats), "diagnostic": diagnostic}
