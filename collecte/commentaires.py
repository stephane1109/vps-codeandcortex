"""Commentaires visibles et réponses, limites explicites et provenance conservée."""
import hashlib
from .engagement import convertir_compteur
from .reponses import rattacher_reponses

SCRIPT_COMMENTAIRES = """
return Array.from(document.querySelectorAll('[data-e2e="comment-level-1"], [data-e2e="comment-level-2"]')).filter(e=>e.getClientRects().length).map(e=>({
 id:e.getAttribute('data-comment-id') || null,
 parent_id:e.matches('[data-e2e="comment-level-2"]') ? e.closest('[data-e2e="comment-level-1"]')?.getAttribute('data-comment-id') || null : null,
 reponse:e.matches('[data-e2e="comment-level-2"]'),
 texte:e.querySelector('[data-e2e="comment-text"]')?.innerText || '',
 auteur:e.querySelector('a[href*="/@"]')?.getAttribute('href')?.split('/@')[1]?.split('/')[0] || null,
 date_brute:e.querySelector('[data-e2e="comment-time"]')?.innerText || null,
 likes:e.querySelector('[data-e2e="comment-like-count"]')?.innerText || null
}));
"""
SCRIPT_DEFILEMENT = """
const e=document.querySelector('[data-e2e="comment-list"]') || document.querySelector('[class*="DivCommentListContainer"]');
if(e){e.scrollTop+=600; return true;} return false;
"""
SCRIPT_REPONSES = """
const e=Array.from(document.querySelectorAll('[data-e2e="comment-more"]')).find(e=>e.getClientRects().length); if(e){e.click();return true;}return false;
"""

def normaliser_commentaire(donnee, publication_id, date):
    texte = str(donnee.get("texte") or donnee.get("text") or "").strip()
    if not texte:
        return None
    # Les données issues d’une réponse JSON d’une autre vidéo sont exclues.
    if donnee.get("aweme_id") is not None and str(donnee["aweme_id"]) != str(publication_id):
        return None
    identifiant = donnee.get("id") or donnee.get("cid")
    parent = donnee.get("parent_id") or donnee.get("reply_id")
    if str(parent) == "0": parent = None
    auteur = donnee.get("auteur")
    if not auteur and isinstance(donnee.get("user"), dict): auteur = donnee["user"].get("unique_id") or donnee["user"].get("uniqueId")
    brut = dict(donnee)
    if identifiant is None:
        contenu = str(publication_id) + "\0" + str(parent) + "\0" + str(auteur) + "\0" + texte
        identifiant = "local_" + hashlib.sha256(contenu.encode()).hexdigest()[:24]
    return {"id": str(identifiant), "publication_id": str(publication_id), "parent_id": str(parent) if parent else None,
            "est_reponse": bool(parent or donnee.get("reponse")), "auteur": auteur, "texte": texte,
            "date_brute": donnee.get("date_brute") or donnee.get("create_time"), "observe_le": date,
            "likes": convertir_compteur(donnee.get("likes", donnee.get("digg_count"))),
            "id_observe": not str(identifiant).startswith("local_"), "brut": brut, "source": "page_visible"}

def collecter_commentaires(navigateur, publication, limite=50, reponses=False, verifier=lambda: None, pause=None):
    from scraptiktok import canonical_post, utc_now
    if not 1 <= limite <= 500: raise ValueError("Limite de commentaires : 1 à 500.")
    courant = canonical_post(navigateur.current_url)
    if not courant or courant[0] != publication["id"]:
        return {"commentaires": [], "statut": "page_differente", "exhaustif": False}
    resultats = {}; inactif = 0
    for _ in range(min(30, limite // 5 + 3)):
        verifier(); avant = len(resultats)
        for donnee in navigateur.execute_script(SCRIPT_COMMENTAIRES) or []:
            commentaire = normaliser_commentaire(donnee, publication["id"], utc_now())
            if commentaire and (reponses or not commentaire["est_reponse"]) and len(resultats) < limite: resultats.setdefault(commentaire["id"], commentaire)
        if len(resultats) >= limite: break
        inactif = inactif + 1 if len(resultats) == avant else 0
        if inactif >= 3: break
        if reponses: navigateur.execute_script(SCRIPT_REPONSES)
        navigateur.execute_script(SCRIPT_DEFILEMENT)
        if pause: pause(0.8)
    return {"commentaires": rattacher_reponses(list(resultats.values())),
            "statut": "limite" if len(resultats) >= limite else "partiel" if resultats else "indisponible_ou_vide",
            "exhaustif": False, "limite": limite}
