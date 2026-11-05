"""Construire un réseau de proximité statistique entre vidéos TikTok.

Les quatre métriques sont des agrégats par vidéo : elles ne révèlent aucune
identité de spectateur, de commentateur ou de personne ayant partagé le contenu.
"""

import math
import heapq
from statistics import mean, pstdev

from .import_csv import lire_csv, premier

METRIQUES = {
    "vues": ("vues", "view_count"),
    "likes": ("likes", "like_count"),
    "commentaires": ("commentaires", "comment_count"),
    "partages": ("partages", "share_count"),
}
MAX_VIDEOS_CSV = 100_000


def convertir_nombre(valeur):
    """Lire un compteur réel non négatif, sans confondre absence et zéro."""
    if valeur is None:
        return None
    texte = str(valeur).strip().replace("\u00a0", "").replace("\u202f", "")
    texte = texte.replace(" ", "")
    if not texte:
        return None
    # Les exports bruts utilisent un point ; accepter aussi la virgule
    # décimale lorsqu'elle apparaît dans un CSV français.
    if texte.count(",") == 1 and "." not in texte:
        texte = texte.replace(",", ".")
    try:
        nombre = float(texte)
    except (ValueError, OverflowError):
        return None
    if not math.isfinite(nombre) or nombre < 0:
        return None
    return nombre


def importer_engagement(fichiers):
    """Importer des tableaux engagement.csv avec identifiants vidéo distincts."""
    if not fichiers:
        raise ValueError("Importez au moins un fichier engagement.csv.")
    videos = {}
    doublons = 0
    sans_id = 0
    diagnostics = []
    for nom, donnees in fichiers:
        colonnes, lignes = lire_csv(donnees, nom)
        identifiant = next(
            (champ for champ in ("publication_id", "id", "id_", "video_id")
             if champ in colonnes), None)
        if not identifiant:
            raise ValueError(
                f"{nom} : colonne publication_id, id ou video_id absente.")
        disponibles = {
            variable for variable, alias in METRIQUES.items()
            if any(champ in colonnes for champ in alias)
        }
        if not disponibles:
            raise ValueError(
                f"{nom} : aucune colonne vues, likes, commentaires ou partages.")
        for ligne in lignes:
            video_id = premier(ligne, identifiant)
            if not video_id:
                sans_id += 1
                continue
            if video_id in videos:
                doublons += 1
                continue
            if len(videos) >= MAX_VIDEOS_CSV:
                raise ValueError("Maximum de 100 000 vidéos distinctes.")
            mesures = {
                variable: convertir_nombre(premier(ligne, *alias))
                for variable, alias in METRIQUES.items()
            }
            videos[video_id] = {
                "id": video_id,
                "url": premier(ligne, "url", "video_url"),
                **mesures,
            }
    if doublons:
        diagnostics.append(
            f"{doublons} vidéo(s) en doublon ignorée(s), première ligne conservée.")
    if sans_id:
        diagnostics.append(f"{sans_id} ligne(s) sans ID vidéo ignorée(s).")
    if not videos:
        raise ValueError("Aucune vidéo identifiable dans les CSV importés.")
    return {"videos": list(videos.values()), "diagnostics": diagnostics,
            "doublons": doublons, "sans_id": sans_id}


def construire_reseau_engagement(donnees, metriques=None, *,
                                 seuil=0.75, voisins=5, limite=500):
    """Relier les vidéos proches selon la distance des log-compteurs centrés.

    Les arêtes sont non orientées et pondérées par 1/(1+distance). Les
    compteurs sont comparés après log(1+x), centrage et réduction, sans
    jamais traiter une valeur manquante comme zéro. Chaque vidéo conserve
    au plus ses `voisins` plus proches, puis les liens sont symétrisés.
    """
    choisies = list(METRIQUES) if metriques is None else list(metriques)
    if not choisies or len(set(choisies)) != len(choisies):
        raise ValueError("Choisissez au moins une métrique sans doublon.")
    if any(nom not in METRIQUES for nom in choisies):
        raise ValueError("Métrique d'engagement inconnue.")
    if not isinstance(limite, int) or not 2 <= limite <= 1000:
        raise ValueError("Nombre de vidéos à analyser : entre 2 et 1 000.")
    if not isinstance(voisins, int) or not 1 <= voisins <= 20:
        raise ValueError("Nombre de voisins : entre 1 et 20.")
    if not 0 < float(seuil) <= 1:
        raise ValueError("Seuil de similarité : supérieur à 0 et au plus égal à 1.")

    disponibles = [
        item for item in donnees["videos"]
        if all(item.get(nom) is not None for nom in choisies)
    ]
    total = len(disponibles)
    # L'ordre du CSV est conservé et toute troncature est explicitement
    # signalée : on ne prétend pas avoir analysé tout le corpus.
    videos = disponibles[:limite]
    if len(videos) < 2:
        raise ValueError(
            "Au moins deux vidéos doivent posséder toutes les métriques choisies.")
    colonnes = [
        [math.log1p(item[nom]) for item in videos] for nom in choisies
    ]
    moyennes = [mean(colonne) for colonne in colonnes]
    ecarts = [pstdev(colonne) for colonne in colonnes]
    actives = [i for i, ecart in enumerate(ecarts) if ecart > 0]
    if not actives:
        raise ValueError(
            "Toutes les vidéos ont les mêmes valeurs : aucune distance exploitable.")
    vecteurs = [
        [(colonnes[j][i] - moyennes[j]) / ecarts[j] for j in actives]
        for i in range(len(videos))
    ]
    # Ne conserver qu'un petit tas de voisins par vidéo. L'ancienne
    # implémentation conservait jusqu'à n*(n-1) correspondances en mémoire,
    # puis triait des listes potentiellement très importantes à chaque
    # déplacement d'un curseur Streamlit.
    voisins_possibles = [[] for _ in videos]
    nombre_dimensions = len(actives)
    paires_proches = 0
    nombre_comparaisons = len(videos) * (len(videos) - 1) // 2

    def ajouter_voisin(indice, voisin, similarite):
        """Conserver les k meilleurs voisins, avec un ordre déterministe."""
        candidats = voisins_possibles[indice]
        # En cas d'égalité de similarité, privilégier le plus petit indice.
        candidat = (similarite, -voisin)
        if len(candidats) < voisins:
            heapq.heappush(candidats, candidat)
        elif candidat > candidats[0]:
            heapq.heapreplace(candidats, candidat)

    # Calculer chaque paire une seule fois, sans créer de liste quadratique.
    for i, vecteur_i in enumerate(vecteurs):
        for j in range(i + 1, len(vecteurs)):
            vecteur_j = vecteurs[j]
            somme_carres = 0.0
            for dimension in range(nombre_dimensions):
                ecart = vecteur_i[dimension] - vecteur_j[dimension]
                somme_carres += ecart * ecart
            distance = math.sqrt(somme_carres / nombre_dimensions)
            similarite = 1.0 / (1.0 + distance)
            if similarite >= seuil:
                paires_proches += 1
                ajouter_voisin(i, j, similarite)
                ajouter_voisin(j, i, similarite)
    liens_uniques = set()
    for i, candidats in enumerate(voisins_possibles):
        for _, negatif_j in candidats:
            j = -negatif_j
            liens_uniques.add((min(i, j), max(i, j)))

    noeuds = []
    for video in videos:
        noeud = {"id": "video:" + video["id"],
                 "label": "Vidéo " + video["id"], "type": "video"}
        for champ in (*METRIQUES, "url"):
            if video.get(champ) is not None:
                noeud[champ] = video[champ]
        noeuds.append(noeud)
    liens = []
    for i, j in sorted(liens_uniques):
        distance = math.sqrt(
            sum((a - b) ** 2 for a, b in zip(vecteurs[i], vecteurs[j]))
            / nombre_dimensions)
        poids = round(1.0 / (1.0 + distance), 6)
        liens.append({"source": noeuds[i]["id"], "cible": noeuds[j]["id"],
                      "poids": poids, "relation": "similarite_engagement"})

    diagnostics = list(donnees.get("diagnostics", []))
    if total > limite:
        diagnostics.append(
            f"Corpus partiel : {limite} premières vidéos complètes analysées "
            f"sur {total} exploitables. Augmentez la limite pour élargir le réseau.")
    if len(actives) < len(choisies):
        diagnostics.append(
            "Métrique(s) constante(s) ignorée(s) dans la distance : "
            + ", ".join(choisies[i] for i in range(len(choisies))
                        if i not in actives) + ".")
    diagnostics.append(
        "Les arêtes représentent une similarité statistique entre compteurs, "
        "et non une interaction entre utilisateurs ou une audience commune.")
    return {
        "mode": "similarite_engagement", "oriente": False,
        "noeuds": noeuds, "liens": liens,
        "diagnostics": diagnostics,
        "statistiques": {
            "videos_importees": len(donnees["videos"]),
            "videos_completes": total, "videos_analysees": len(videos),
            "metriques_actives": [choisies[i] for i in actives],
            "liens": len(liens), "noeuds": len(noeuds),
            "seuil": float(seuil), "voisins": voisins,
            "comparaisons": nombre_comparaisons,
            "paires_au_seuil": paires_proches,
        },
    }
