"""Lire les pages de publications déjà reçues par Chrome, sans rejouer de requête."""
import base64
import json
import re
import threading
import time
from urllib.parse import urlsplit


def commande_cdp(methode, parametres=None):
    """Adapter une commande Chrome au canal DevTools fourni par Selenium."""
    resultat = yield {"method": methode, "params": parametres or {}}
    return resultat


class ReponseRecue:
    """Événement brut : seuls le chemin, le statut et l'identifiant sont retenus."""
    event_class = "Network.responseReceived"

    @classmethod
    def from_json(cls, donnees):
        return donnees


def extraire_page_publications(donnees, compte):
    """Conserver les publications du compte et les indicateurs bruts de pagination."""
    from scraptiktok import canonical_post, liens_donnees_publications
    if not isinstance(donnees, dict):
        return None
    elements = donnees.get("itemList")
    code = donnees.get("statusCode")
    code = code if isinstance(code, (int, str)) and re.fullmatch(r"\d{1,10}", str(code)) else None
    valide = isinstance(elements, list) and code in (None, 0, "0")
    liens = []
    if valide:
        for url in liens_donnees_publications([json.dumps(elements)]):
            identite = canonical_post(url)
            if identite and identite[2].casefold() == compte.casefold():
                liens.append(identite[1])
    # Une liste concernant un autre auteur ne renseigne pas la fin de ce profil.
    concordante = valide and (not elements or bool(liens))
    suite_brute = donnees.get("hasMore")
    suite = (True if suite_brute in (True, 1, "1", "true") else
             False if suite_brute in (False, 0, "0", "false") else None) if concordante else None
    curseur = donnees.get("cursor")
    curseur = str(curseur) if isinstance(curseur, (str, int)) and re.fullmatch(r"\d{1,32}", str(curseur)) else None
    return {"liens": liens, "code_tiktok": code, "suite": suite,
            "curseur": curseur if concordante else None, "liste_valide": bool(concordante)}


class ObservationProfil:
    """Observer uniquement les réponses publiques de pagination, en mémoire bornée."""
    def __init__(self, navigateur, compte, rapport, delai=20):
        self.navigateur, self.compte, self.rapport = navigateur, compte, rapport
        self.delai = max(1, delai)
        self.connexion = None
        self.abonnement = None
        self.actif = False
        self.attente = {}
        self.verrou = threading.Lock()
        self.derniere_page = None
        self.rapport.update(actif=False, pages=[], erreurs_lecture=0, reponses_ecartees=0)

    def demarrer(self):
        """Brancher l'observation avant la navigation ; conserver le repli HTML."""
        try:
            _, self.connexion = self.navigateur.start_devtools()
            self.actif = True
            self.abonnement = self.connexion.add_callback(ReponseRecue, self.recevoir)
            self.connexion.execute(commande_cdp("Network.enable", {
                "maxTotalBufferSize": 16 * 1024 * 1024,
                "maxResourceBufferSize": 4 * 1024 * 1024}))
            self.rapport["actif"] = True
        except Exception as erreur:
            # Ce complément ne doit jamais supprimer les liens lisibles dans le HTML.
            self.rapport["indisponibilite"] = type(erreur).__name__
            self.fermer()

    def recevoir(self, evenement):
        """Recevoir des identifiants ; aucun appel Selenium depuis ce callback."""
        reponse = evenement.get("response", {})
        try:
            url = urlsplit(reponse.get("url", ""))
        except ValueError:
            return
        if not self.accepter_reponse(url):
            return
        identifiant = evenement.get("requestId")
        if not isinstance(identifiant, str):
            return
        with self.verrou:
            if not self.actif:
                return
            if len(self.attente) >= 32:
                self.rapport["reponses_ecartees"] += 1
                return
            # Aucune URL signée, aucun en-tête et aucun cookie ne sont conservés.
            self.attente[identifiant] = {"statut_http": reponse.get("status"),
                                         "debut": time.monotonic()}

    def lire(self):
        """Lire les corps depuis le worker, après leur arrivée dans le navigateur."""
        if not self.actif:
            return []
        with self.verrou:
            en_attente = list(self.attente.items())[:8]
        liens = []
        for identifiant, infos in en_attente:
            statut = infos["statut_http"]
            if not isinstance(statut, (int, float)) or not 200 <= statut < 300:
                page = {"statut_http": statut, "liste_valide": False, "nombre_liens": 0,
                        "suite": None, "curseur": None}
            else:
                try:
                    corps = self.connexion.execute(commande_cdp("Network.getResponseBody", {"requestId": identifiant}))
                except Exception:
                    # ResponseReceived précède parfois la fin du corps : le relire
                    # au prochain passage, sans réémettre la requête réseau.
                    if time.monotonic() - infos["debut"] < self.delai:
                        continue
                    self.rapport["erreurs_lecture"] += 1
                    page = {"statut_http": statut, "liste_valide": False, "nombre_liens": 0,
                            "erreur": "corps_indisponible", "suite": None, "curseur": None}
                else:
                    try:
                        texte = corps.get("body", "")
                        if len(texte) > 6 * 1024 * 1024:
                            raise ValueError("Réponse trop volumineuse")
                        if corps.get("base64Encoded"):
                            texte = base64.b64decode(texte, validate=True).decode("utf-8")
                        page = self.analyser_page(json.loads(texte))
                        if page is None:
                            raise ValueError("Format inconnu")
                        nouveaux = page.pop("liens")
                        liens.extend(nouveaux)
                        page.update(statut_http=statut, nombre_liens=len(nouveaux))
                    except (ValueError, TypeError, UnicodeError, RecursionError):
                        self.rapport["erreurs_lecture"] += 1
                        page = {"statut_http": statut, "liste_valide": False, "nombre_liens": 0,
                                "erreur": "format_indetermine", "suite": None, "curseur": None}
            with self.verrou:
                self.attente.pop(identifiant, None)
            self.rapport["pages"].append(page)
            self.rapport["pages"] = self.rapport["pages"][-100:]
            if page["liste_valide"]:
                self.derniere_page = page
        return liens

    def accepter_reponse(self, url):
        """Observer les deux chemins de pagination publique des profils TikTok.

        Selon le compte et la version du site, la grille charge ses vidéos
        depuis /api/post/item_list ou /api/creator/item_list. Ne pas inventer
        une requête : lire uniquement les réponses reçues par Chrome.
        """
        return (url.scheme == "https" and url.hostname in {"www.tiktok.com", "tiktok.com"}
                and url.path.rstrip("/") in {"/api/post/item_list", "/api/creator/item_list"})

    def analyser_page(self, donnees):
        """Décoder la réponse correspondant au parcours observé."""
        return extraire_page_publications(donnees, self.compte)

    def fermer(self):
        """Retirer l'observateur avant le prochain compte ou la lecture des légendes."""
        with self.verrou:
            self.actif = False
            self.attente.clear()
        if self.connexion is not None and self.abonnement is not None:
            try:
                self.connexion.remove_callback(ReponseRecue, self.abonnement)
                self.connexion.execute(commande_cdp("Network.disable"))
            except Exception:
                pass
        self.abonnement = None
