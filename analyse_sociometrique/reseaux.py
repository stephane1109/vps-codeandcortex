"""Réseaux à partir de commentaires déjà collectés, sans inférer d'identités.

Les auteurs issus de liens de profils Selenium sont pseudonymisés par collecte.
Les commentaires Research ne contiennent pas d'identifiants de comptes vérifiés.
"""
from collections import Counter, defaultdict
from hashlib import sha256
from itertools import combinations
from io import StringIO
import csv
import json
import re
from xml.etree import ElementTree as ET

NOMS = ("auteurs_videos", "videos_communes", "reponses")
COMPTE = re.compile(r"[A-Za-z0-9_.]{2,30}\Z")


def identifier_auteur(commentaire):
    """Accepter seulement un identifiant lu dans le lien de profil visible."""
    if commentaire.get("source") != "page_visible":
        return None
    valeur = commentaire.get("auteur")
    if not isinstance(valeur, str):
        return None
    valeur = valeur.strip().lstrip("@").casefold()
    if not COMPTE.fullmatch(valeur) or valeur in {
        "inconnu", "unknown", "anonymous", "indetermine",
    }:
        return None
    return valeur


def pseudonymiser(auteur, graine):
    """Conserver une identité pseudonyme cohérente uniquement dans une collecte."""
    return "auteur_" + sha256((str(graine) + "\0" + auteur).encode()).hexdigest()[:16]


def construire_reseau(commentaires, publications, mode, graine, seuil=1):
    """Calculer le biparti, la projection vidéos ou les réponses observées."""
    if mode not in NOMS:
        raise ValueError("Type de réseau inconnu.")
    if not 1 <= seuil <= 1000:
        raise ValueError("Seuil invalide, entre 1 et 1000.")
    videos = {str(v["id"]) for v in publications if isinstance(v, dict) and v.get("id") is not None}
    commentaires_uniques = {}
    for commentaire in commentaires[:100000]:
        if not isinstance(commentaire, dict):
            continue
        vid = str(commentaire.get("publication_id") or "")
        ident = str(commentaire.get("id") or "")
        if vid in videos and ident:
            commentaires_uniques.setdefault((vid, ident), commentaire)
    participations = defaultdict(Counter)
    participation_videos = defaultdict(set)
    reponses = []
    inconnus = 0
    for (vid, cid), commentaire in commentaires_uniques.items():
        auteur = identifier_auteur(commentaire)
        if auteur:
            pseudo = pseudonymiser(auteur, graine)
            participations[vid][pseudo] += 1
            participation_videos[pseudo].add(vid)
        else:
            inconnus += 1
        parent = str(commentaire.get("parent_id") or "").strip()
        if parent and parent not in ("0", cid):
            reponses.append((vid, cid, parent))
    noeuds = {}
    liens = []
    diagnostics = []
    if len(commentaires) > 100000:
        diagnostics.append("Analyse limitée aux 100 000 premiers commentaires.")
    if mode == "auteurs_videos":
        for vid, auteurs in sorted(participations.items()):
            video = "video:" + vid
            noeuds[video] = {"id": video, "label": "Vidéo " + vid, "type": "video"}
            for pseudo, poids in sorted(auteurs.items()):
                auteur = "auteur:" + pseudo
                noeuds[auteur] = {"id": auteur, "label": pseudo, "type": "auteur"}
                liens.append({"source": auteur, "cible": video,
                              "poids": poids, "relation": "commentaire"})
    elif mode == "videos_communes":
        relations = Counter()
        tronque = False
        for ensemble in participation_videos.values():
            for paire in combinations(sorted(ensemble), 2):
                if paire not in relations and len(relations) >= 120000:
                    tronque = True
                    continue
                relations[paire] += 1
        if tronque:
            diagnostics.append("Projection partielle : maximum 120 000 paires de vidéos.")
        for (vid1, vid2), poids in sorted(relations.items()):
            if poids < seuil:
                continue
            a, b = "video:" + vid1, "video:" + vid2
            noeuds[a] = {"id": a, "label": "Vidéo " + vid1, "type": "video"}
            noeuds[b] = {"id": b, "label": "Vidéo " + vid2, "type": "video"}
            liens.append({"source": a, "cible": b,
                          "poids": poids, "relation": "auteurs_communs"})
    else:
        parents_absents = set()
        for vid, cid, parent in reponses:
            a, b = f"commentaire:{vid}:{cid}", f"commentaire:{vid}:{parent}"
            noeuds[a] = {"id": a, "label": "Com. " + cid[-10:], "type": "commentaire"}
            parent_existe = (vid, parent) in commentaires_uniques
            noeuds[b] = {"id": b, "label": "Com. " + parent[-10:],
                         "type": "commentaire" if parent_existe else "parent_non_collecte"}
            if not parent_existe:
                parents_absents.add(b)
            liens.append({"source": a, "cible": b, "poids": 1, "relation": "reponse_a"})
        if parents_absents:
            diagnostics.append(
                f"{len(parents_absents)} commentaire(s) parent(s) non collectés.")
    n = len(commentaires_uniques)
    return {
        "mode": mode, "oriente": mode == "reponses",
        "noeuds": list(noeuds.values()), "liens": liens,
        "statistiques": {
            "commentaires_exploitables": n,
            "commentaires_auteur_identifie": n - inconnus,
            "commentaires_sans_auteur_fiable": inconnus,
            "pourcentage_auteur_identifie": round(100 * (n - inconnus) / n, 2) if n else 0,
            "auteurs_distincts": len(participation_videos),
            "videos_avec_auteur": len(participations),
            "reponses_observees": len(reponses),
            "noeuds": len(noeuds), "liens": len(liens),
        },
        "diagnostics": diagnostics,
    }


def apercu(reseau, max_noeuds=75, max_liens=150):
    """Limiter seulement le dessin ; conserver les exports complets."""
    ids, liens = set(), []
    for lien in sorted(reseau["liens"], key=lambda x: -x["poids"]):
        supplement = {lien["source"], lien["cible"]} - ids
        if len(ids) + len(supplement) > max_noeuds or len(liens) >= max_liens:
            continue
        liens.append(lien)
        ids.update((lien["source"], lien["cible"]))
    return {
        "noeuds": [n for n in reseau["noeuds"] if n["id"] in ids],
        "liens": liens, "oriente": reseau["oriente"],
        "partiel": len(liens) != len(reseau["liens"]),
    }


def construire_dot(reseau):
    """Sérialiser un graphe DOT sans nom brut ni texte de commentaire."""
    dirige = reseau["oriente"]
    lignes = ["digraph R {" if dirige else "graph R {",
              'graph [overlap="false", bgcolor="transparent"];']
    for noeud in reseau["noeuds"]:
        couleur = {"auteur": "lightblue", "video": "khaki",
                   "commentaire": "lightgreen", "parent_non_collecte": "lightgray"}[noeud["type"]]
        forme = "box" if noeud["type"] == "video" else "ellipse"
        lignes.append(f'{json.dumps(noeud["id"])} '
                      f'[label={json.dumps(noeud["label"])}, fillcolor="{couleur}", '
                      f'style="filled", shape="{forme}"];')
    fleche = "->" if dirige else "--"
    for lien in reseau["liens"]:
        lignes.append(f'{json.dumps(lien["source"])} {fleche} '
                      f'{json.dumps(lien["cible"])} [label="{lien["poids"]}"];')
    return "\n".join(lignes + ["}"])


def csv_reseau(lignes, colonnes):
    """Émettre un CSV compatible avec les outils statistiques français."""
    texte = StringIO()
    writer = csv.DictWriter(texte, fieldnames=colonnes, delimiter=";",
                            lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    writer.writerows(lignes)
    return texte.getvalue().encode("utf-8-sig")


def matrice(reseau):
    """Construire la matrice pondérée sur 250 nœuds au maximum."""
    ids = [noeud["id"] for noeud in reseau["noeuds"]]
    if len(ids) > 250:
        raise ValueError("Matrice limitée à 250 nœuds. Exportez les liens CSV.")
    poids = {i: {j: 0 for j in ids} for i in ids}
    for lien in reseau["liens"]:
        a, b = lien["source"], lien["cible"]
        poids[a][b] += lien["poids"]
        if not reseau["oriente"] and a != b:
            poids[b][a] += lien["poids"]
    return csv_reseau([{"noeud": i, **poids[i]} for i in ids], ["noeud"] + ids)


def graphml(reseau):
    """Exporter un GraphML à attributs typés."""
    ns = "http://graphml.graphdrawing.org/xmlns"
    ET.register_namespace("", ns)
    balise = lambda x: f"{{{ns}}}{x}"
    root = ET.Element(balise("graphml"))
    for cle, niveau, nom, genre in [
        ("type", "node", "type", "string"),
        ("label", "node", "label", "string"),
        ("weight", "edge", "weight", "double"),
        ("relation", "edge", "relation", "string"),
    ]:
        ET.SubElement(root, balise("key"),
                      {"id": cle, "for": niveau, "attr.name": nom, "attr.type": genre})
    graph = ET.SubElement(root, balise("graph"),
                          {"id": "ScrapTikTok", "edgedefault":
                           "directed" if reseau["oriente"] else "undirected"})
    for n in reseau["noeuds"]:
        node = ET.SubElement(graph, balise("node"), {"id": n["id"]})
        for cle, val in (("type", n["type"]), ("label", n["label"])):
            ET.SubElement(node, balise("data"), {"key": cle}).text = val
    for i, l in enumerate(reseau["liens"]):
        edge = ET.SubElement(graph, balise("edge"), {
            "id": "e" + str(i), "source": l["source"], "target": l["cible"]})
        for cle, val in (("weight", l["poids"]), ("relation", l["relation"])):
            ET.SubElement(edge, balise("data"), {"key": cle}).text = str(val)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def gexf(reseau):
    """Exporter un GEXF avec poids et types de nœuds."""
    ns = "http://www.gexf.net/1.2draft"
    ET.register_namespace("", ns)
    balise = lambda x: f"{{{ns}}}{x}"
    root = ET.Element(balise("gexf"), {"version": "1.2"})
    graph = ET.SubElement(root, balise("graph"), {
        "mode": "static", "defaultedgetype":
        "directed" if reseau["oriente"] else "undirected"})
    attributs = ET.SubElement(graph, balise("attributes"), {"class": "node"})
    ET.SubElement(attributs, balise("attribute"), {
        "id": "type", "title": "type", "type": "string"})
    nodes = ET.SubElement(graph, balise("nodes"))
    for n in reseau["noeuds"]:
        node = ET.SubElement(nodes, balise("node"), {
            "id": n["id"], "label": n["label"]})
        vals = ET.SubElement(node, balise("attvalues"))
        ET.SubElement(vals, balise("attvalue"), {"for": "type", "value": n["type"]})
    edges = ET.SubElement(graph, balise("edges"))
    for i, l in enumerate(reseau["liens"]):
        ET.SubElement(edges, balise("edge"), {
            "id": str(i), "source": l["source"], "target": l["cible"],
            "weight": str(l["poids"]), "label": l["relation"]})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def exporter(reseau, format_):
    """Produire un export correspondant au réseau choisi."""
    if format_ == "noeuds.csv":
        # Exporter les métriques facultatives des vidéos importées sans
        # modifier les trois colonnes du format historique.
        supplementaires = ("url", "vues", "likes", "commentaires",
                           "partages", "favoris", "taux_engagement")
        colonnes = ["id", "label", "type"] + [
            nom for nom in supplementaires
            if any(nom in noeud for noeud in reseau["noeuds"])]
        return csv_reseau(reseau["noeuds"], colonnes)
    if format_ == "liens.csv":
        return csv_reseau(reseau["liens"], ["source", "cible", "poids", "relation"])
    if format_ == "matrice.csv":
        return matrice(reseau)
    if format_ == "graphml":
        return graphml(reseau)
    if format_ == "gexf":
        return gexf(reseau)
    raise ValueError("Format d'export inconnu.")
