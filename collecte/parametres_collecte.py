"""Traçabilité des paramètres effectivement retenus pour une collecte ScrapTikTok.

Ce fichier ne doit jamais exposer les identifiants des API ni les cookies.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


# Les champs sensibles sont systématiquement exclus, y compris des archives
# créées depuis une ancienne configuration ou une base PostgreSQL.
_CHAMPS_INTERDITS = {
    "research_client_key", "research_client_secret", "tikhub_api_key",
    "apify_api_token", "cookies_tiktok", "authorization", "password",
    "access_token", "refresh_token", "api_key", "api_secret",
}

_LIBELLES = {
    "source_collecte": "Mode de collecte",
    "nom_sauvegarde": "Nom de la collecte",
    "hashtag_moteur": "Moteur Hashtags",
    "profil_moteur": "Moteur Profils",
    "presse_moteur": "Moteur Presse",
    "date_debut": "Date de début des publications",
    "date_fin": "Date de fin des publications",
    "hashtags_saisis": "Hashtags recherchés",
    "hashtags_presse": "Hashtags croisés avec la presse",
    "hashtags_exclus": "Hashtags exclus",
    "groupes_hashtags": "Groupes de hashtags",
    "operator": "Opérateur de recherche",
    "operator_presse": "Opérateur du croisement Presse",
    "comptes": "Profils sélectionnés",
    "medias": "Médias sélectionnés",
    "variables_txt": "Variables sélectionnées dans le TXT",
    "variables_csv": "Variables sélectionnées dans le CSV",
    "variables_classes_txt": "Variables de classes du TXT",
    "profils_medias_variables": "Métriques des profils à récupérer",
    "profils_medias_classes": "Métriques des profils à catégoriser",
    "profils_medias_txt_bruts": "Métriques brutes des profils dans le TXT",
    "profils_medias_txt_classes": "Classes des profils dans le TXT",
    "profils_medias_csv_bruts": "Métriques brutes des profils dans le CSV",
    "profils_medias_csv_classes": "Classes des profils dans le CSV",
    "region_fr_research": "Filtre Research région FR",
    "french_only": "Filtre linguistique français",
    "rechercher_dans_texte": "Recherche aussi dans le texte",
    "variantes_accents": "Variantes orthographiques et accents",
    "ville_etude": "Ville associée au corpus",
    "limit": "Plafond local de publications",
    "collecte_research_complete": "Pagination Research complète demandée",
    "test_research_10_publications": "Test Research sur dix publications",
    "collecter_commentaires": "Collecter les commentaires",
    "collecter_reponses": "Collecter les réponses",
    "limite_commentaires": "Limite de commentaires",
    "inclure_commentaires_txt": "Exporter les commentaires dans le TXT",
    "inclure_texte_genere_ia": "Collecter le résumé IA TikTok",
    "filtrer_texte_ia_tiktok": "Ne garder que les publications avec texte IA",
    "collecter_follower_count": "Récupérer le nombre d'abonnés",
    "collecter_is_verified": "Récupérer la vérification des comptes",
    "taux_engagement_txt": "Export du taux d'engagement TXT",
    "telecharger_mp4": "Télécharger les vidéos MP4",
    "croiser_hashtag_presse": "Activer le croisement Presse / hashtags",
    "collecter_republications_research": "Collecter les republications Research",
    "maximum_republications_par_compte": "Maximum de republications par compte",
    "inclure_hashtags_csv": "Inclure les hashtags dans le CSV",
    "supprimer_arobase_profil": "Supprimer @ devant le profil",
    "enrichir": "Produire les exports enrichis",
}


def _autorise(cle):
    """Écarter les données d'authentification, même dans les anciens dictionnaires."""
    nom = str(cle).lower()
    return (nom not in _CHAMPS_INTERDITS
            and not any(fragment in nom for fragment in (
                "secret", "password", "token", "cookie", "credential",
                "autorisation", "authorization", "api_key")))


def _formater(valeur):
    """Fournir une représentation lisible, explicite et sur une seule ligne."""
    if valeur is None:
        return "non renseigné"
    if isinstance(valeur, bool):
        return "oui" if valeur else "non"
    if isinstance(valeur, (list, dict)):
        if not valeur:
            return "aucun"
        return json.dumps(valeur, ensure_ascii=False, separators=(", ", ": "))
    texte = str(valeur).replace("\r", " ").replace("\n", " ").strip()
    return texte if texte else "non renseigné"


def _liste_hashtags(parametres):
    valeurs = parametres.get("hashtags_saisis") or []
    if not valeurs:
        valeurs = [parametres.get("hashtag"), parametres.get("second_hashtag")]
    return list(dict.fromkeys(
        str(valeur).lstrip("#") for valeur in valeurs if valeur))


def generer_parametres_collecte(parametres, *, identifiant="", statut="",
                                 date_lancement=None, journal=None):
    """Documenter les critères et les champs, sans aucune donnée d'accès.

    Tous les paramètres non sensibles sont reproduits, y compris les options
    désactivées. Les diagnostics par source proviennent du journal enregistré.
    """
    if hasattr(parametres, "model_dump"):
        parametres = parametres.model_dump()
    valeurs = {str(cle): valeur for cle, valeur in dict(parametres or {}).items()
               if _autorise(cle)}
    mode = valeurs.get("source_collecte", "non renseigné")
    moteur = valeurs.get({
        "hashtags": "hashtag_moteur",
        "comptes": "profil_moteur",
        "presse": "presse_moteur",
    }.get(mode, ""), "non renseigné")
    hashtags = (
        list(valeurs.get("hashtags_presse") or [])
        if mode == "presse" and valeurs.get("croiser_hashtag_presse")
        else _liste_hashtags(valeurs) if mode != "presse" else [])
    operateur = (
        valeurs.get("operator_presse", "OR") if mode == "presse"
        else valeurs.get("operator", "OR"))
    aujourd_hui = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lignes = [
        "SCRAPTIKTOK — PARAMÈTRES DE COLLECTE",
        "=================================",
        "Nom : " + _formater(valeurs.get("nom_sauvegarde")),
        "Identifiant : " + _formater(identifiant),
        "Mode : " + _formater(mode),
        "Méthode : " + _formater(moteur),
        "Date de lancement UTC : " + _formater(date_lancement),
        "Date de génération du fichier : " + aujourd_hui,
        "Statut au moment de l'export : " + _formater(statut),
        "",
        "CRITÈRES DE RECHERCHE",
        "---------------------",
        "Début de période demandé : " + _formater(valeurs.get("date_debut")),
        "Fin de période demandée : " + _formater(valeurs.get("date_fin")),
        "Nombre de hashtags recherchés : " + str(len(hashtags)),
        "Hashtags : " + (", ".join("#" + str(tag).lstrip("#")
                                  for tag in hashtags) if hashtags else "aucun"),
        "Opérateur : " + _formater(operateur if hashtags else None),
        "Hashtags exclus : " + _formater(valeurs.get("hashtags_exclus") or []),
        "Profils : " + _formater(valeurs.get("comptes") or []),
        "Médias : " + _formater(valeurs.get("medias") or []),
        "Groupes de hashtags : " + _formater(valeurs.get("groupes_hashtags") or []),
        "Filtre français : " + _formater(valeurs.get("french_only")),
        "Filtre région FR : " + _formater(valeurs.get("region_fr_research")),
        "",
    ]
    if mode == "comptes" and moteur == "research":
        lignes.extend([
            "Requête logique Research : username EQ ET hashtag_name "
            + ("IN" if operateur == "OR" and len(hashtags) > 1 else "EQ"),
            "Nombre de valeurs transmises au filtre hashtag : "
            + str(len(hashtags)),
            "L'opérateur IN correspond à une alternative entre les hashtags.",
            "Une réponse Research peut être partielle : consulter le bilan "
            "et les diagnostics de pagination avant toute comparaison.",
            "",
        ])
    lignes.extend([
        "VARIABLES SÉLECTIONNÉES",
        "-----------------------",
    ])
    for cle in (
            "variables_txt", "variables_csv", "variables_classes_txt",
            "profils_medias_variables", "profils_medias_classes",
            "profils_medias_txt_bruts", "profils_medias_txt_classes",
            "profils_medias_csv_bruts", "profils_medias_csv_classes"):
        lignes.append(_LIBELLES[cle] + " : " + _formater(valeurs.get(cle)))
    lignes.extend(["", "ENSEMBLE DES PARAMÈTRES EFFECTIFS", "---------------------------------"])
    for cle in sorted(valeurs):
        lignes.append(_LIBELLES.get(cle, cle) + " [" + cle + "] : "
                      + _formater(valeurs[cle]))
    if journal:
        lignes.extend(["", "DIAGNOSTIC DE DÉCOUVERTE PAR SOURCE",
                       "-----------------------------------"])
        for entree in journal:
            if not isinstance(entree, dict):
                continue
            rapport = entree.get("rapport") or {}
            if not isinstance(rapport, dict):
                continue
            lignes.append("Source : " + _formater(entree.get("source")))
            recherches = rapport.get("recherches_compte")
            if not isinstance(recherches, list):
                recherches = [rapport]
            for recherche in recherches:
                if not isinstance(recherche, dict):
                    continue
                for cle in ("hashtags_recherches", "operateur_hashtags",
                            "plage_research", "pages_research",
                            "candidats_examines", "discovery_stop",
                            "collecte_partielle", "requete_recherche"):
                    if cle in recherche:
                        lignes.append("  " + cle + " : " + _formater(recherche[cle]))
    return "\n".join(lignes) + "\n"
