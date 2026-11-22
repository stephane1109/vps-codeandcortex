"""Visualisation interactive des réseaux sociométriques avec PyVis.

La visualisation ne reconstruit pas les relations : elle affiche exclusivement
les nœuds et les liens déjà calculés et pseudonymisés par le moteur sociométrique.
Les ressources JavaScript sont incorporées au HTML pour éviter les CDN externes.
"""
from html import escape
from math import isfinite

from pyvis.network import Network


COULEURS = {
    "auteur": "#6CA9D3",
    "video": "#E4BB67",
    "commentaire": "#79C6A1",
    "parent_non_collecte": "#BBBBBB",
}

FORMES = {
    "auteur": "dot",
    "video": "box",
    "commentaire": "dot",
    "parent_non_collecte": "diamond",
}


def html_reseau_pyvis(reseau, hauteur=620):
    """Générer un HTML autonome à partir d'un graphe calculé en amont."""
    if not isinstance(reseau, dict):
        raise ValueError("Le réseau à visualiser est invalide.")
    if not 350 <= hauteur <= 1000:
        raise ValueError("La hauteur PyVis doit être comprise entre 350 et 1 000 px.")
    noeuds = reseau.get("noeuds") or []
    liens = reseau.get("liens") or []
    if len(noeuds) > 500 or len(liens) > 1000:
        raise ValueError("Aperçu PyVis limité à 500 nœuds et 1 000 liens.")
    reseau_visuel = Network(
        height=f"{hauteur}px",
        width="100%",
        directed=bool(reseau.get("oriente")),
        notebook=False,
        cdn_resources="in_line",
        bgcolor="#FFFFFF",
        font_color="#252525",
        select_menu=True,
    )
    for noeud in noeuds:
        identifiant = escape(str(noeud["id"]))
        type_noeud = str(noeud.get("type", "commentaire"))
        etiquette = escape(str(noeud.get("label") or noeud["id"]))
        lignes = [
            f"<strong>{etiquette}</strong>",
            f"Type : {escape(type_noeud)}",
        ]
        for champ, titre in (
            ("vues", "Vues"),
            ("likes", "Likes"),
            ("commentaires", "Commentaires"),
            ("partages", "Partages"),
            ("favoris", "Favoris"),
            ("taux_engagement", "Taux d'engagement"),
        ):
            valeur = noeud.get(champ)
            if valeur not in (None, ""):
                lignes.append(f"{titre} : {escape(str(valeur))}")
        reseau_visuel.add_node(
            identifiant,
            label=etiquette,
            title="<br>".join(lignes),
            shape=FORMES.get(type_noeud, "dot"),
            color=COULEURS.get(type_noeud, "#AAAAAA"),
            size=19 if type_noeud == "video" else 13,
        )
    presents = {str(noeud["id"]) for noeud in noeuds}
    for lien in liens:
        source = escape(str(lien["source"]))
        cible = escape(str(lien["cible"]))
        if source not in presents or cible not in presents:
            continue
        try:
            poids = float(lien.get("poids", 1))
        except (TypeError, ValueError):
            poids = 1.0
        if not isfinite(poids) or poids <= 0:
            poids = 1.0
        relation = escape(str(lien.get("relation") or "relation"))
        reseau_visuel.add_edge(
            source, cible,
            value=min(poids, 1000),
            title=f"{relation} — poids : {poids:g}",
        )
    reseau_visuel.barnes_hut(
        gravity=-3500,
        central_gravity=0.3,
        spring_length=130,
        spring_strength=0.02,
        damping=0.15,
    )
    reseau_visuel.set_options(
        """{
            "interaction": {
                "hover": true,
                "navigationButtons": true,
                "keyboard": true,
                "tooltipDelay": 150
            },
            "physics": {
                "enabled": true,
                "stabilization": {"iterations": 150, "fit": true},
                "barnesHut": {
                    "gravitationalConstant": -3500,
                    "centralGravity": 0.3,
                    "springLength": 130,
                    "springConstant": 0.02,
                    "damping": 0.15
                }
            },
            "edges": {"smooth": {"type": "dynamic"}},
            "nodes": {"font": {"size": 13}}
        }"""
    )
    return reseau_visuel.generate_html(notebook=False)
