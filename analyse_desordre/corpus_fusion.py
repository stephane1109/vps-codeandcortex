"""Exports complets et fusion hors ligne des résultats de Désordre visuel.

Chaque ligne représente un identifiant de publication TikTok. Les mesures
originales ne sont jamais recalculées et les annotations absentes restent
manquantes (jamais codées zéro). Aucun téléchargement TikTok n'est requis.
"""
import csv
import io
import json
from pathlib import Path
import re


FICHIER = "tableau_complet.csv"
MAX_FICHIERS = 20
MAX_OCTETS = 10 * 1024 * 1024
MAX_LIGNES = 100_000
CHAMPS_PROVENANCE = ("analyse_source", "parametres_frequence", "parametres_dimension",
                     "parametres_duree_max")
CHAMPS_CODAGE = "codage:"


def _identifiant(ligne):
    return str(ligne.get("publication_id") or ligne.get("id") or "").strip()


def _texte_csv(value):
    valeur = "" if value is None else str(value)
    # Les mesures scientifiques négatives restent numériques dans le CSV.
    # Neutraliser les formules uniquement lorsqu'il s'agit d'un texte.
    if valeur.lstrip().startswith(("=", "+", "-", "@")):
        try:
            float(valeur)
        except ValueError:
            return "'" + valeur
    return valeur


def _csv_texte(colonnes, lignes):
    sortie = io.StringIO(newline="")
    writer = csv.DictWriter(sortie, fieldnames=colonnes, delimiter=";",
                            extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for ligne in lignes:
        writer.writerow({champ: _texte_csv(ligne.get(champ)) for champ in colonnes})
    return "\ufeff" + sortie.getvalue()


def construire_tableau_complet(session, dossier):
    """Joindre toutes les mesures, URL, échecs et codages sur le même ID TikTok.

    Compléter les vidéos découvertes sans MP4/mesure : elles doivent rester
    représentées comme données manquantes dans le corpus.
    """
    from .annotation import lire_annotations
    from .codages_personnalises import lire as lire_codages
    from .sources import lire_publications

    session, dossier = Path(session), Path(dossier)
    source = dossier / "indicateurs_engagement.csv"
    if not source.is_file():
        raise ValueError("Aucune mesure de Désordre visuel n'a été enregistrée.")
    with source.open(encoding="utf-8-sig", newline="") as flux:
        apercu=flux.read(4096)
        flux.seek(0)
        try:
            dialecte=csv.Sniffer().sniff(apercu, delimiters=",;")
        except csv.Error:
            dialecte=csv.excel
        lecteur = csv.DictReader(flux, dialect=dialecte)
        colonnes_source = list(lecteur.fieldnames or [])
        mesures = list(lecteur)
    if "publication_id" not in colonnes_source:
        raise ValueError("Le tableau de mesures ne possède aucun ID TikTok.")

    violence = lire_annotations(session)
    personnalises = lire_codages(session)
    variables = personnalises["variables"]
    noms = [CHAMPS_CODAGE + variable["nom"] for variable in variables]
    if len(noms) != len(set(n.casefold() for n in noms)):
        raise ValueError("Deux noms de variables de codage sont identiques.")
    reserve = set(colonnes_source) | {"violence_visible", *CHAMPS_PROVENANCE}
    if any(nom in reserve for nom in noms):
        raise ValueError("Une variable personnalisée entre en conflit avec une mesure.")

    params = {}
    chemin_params = dossier / "parametres.json"
    if chemin_params.is_file():
        params = json.loads(chemin_params.read_text(encoding="utf-8-sig"))
    provenance = {
        "analyse_source": session.name,
        "parametres_frequence": params.get("frequence", ""),
        "parametres_dimension": params.get("dimension", ""),
        "parametres_duree_max": params.get("duree_max", ""),
    }
    lignes = {}
    for ligne in mesures:
        identifiant = _identifiant(ligne)
        if not re.fullmatch(r"[0-9]+", identifiant):
            raise ValueError("Identifiant TikTok incorrect dans le tableau de mesures.")
        if identifiant in lignes:
            raise ValueError("Publication répétée dans les mesures : " + identifiant)
        lignes[identifiant] = {**ligne, "publication_id": identifiant}
    for publication in lire_publications(session):
        identifiant = _identifiant(publication)
        if not re.fullmatch(r"[0-9]+", identifiant):
            continue
        if identifiant not in lignes:
            lignes[identifiant] = {
                "publication_id": identifiant,
                "url": publication.get("url") or "",
                "statut": "sans_mesure",
            }
        elif not lignes[identifiant].get("url"):
            lignes[identifiant]["url"] = publication.get("url") or ""
        lignes[identifiant]["contenu_genere_ia"] = publication.get("contenu_genere_ia") or "non_renseigne"

    colonnes = list(dict.fromkeys([
        "publication_id", "url", "statut", "contenu_genere_ia", *colonnes_source, "violence_visible",
        *noms, *CHAMPS_PROVENANCE,
    ]))
    for identifiant, ligne in lignes.items():
        ligne.update(provenance)
        valeur = violence.get(identifiant)
        ligne["violence_visible"] = "" if valeur is None else valeur
        for variable, nom in zip(variables, noms):
            code = personnalises["valeurs"].get(variable["id"], {}).get(identifiant)
            ligne[nom] = "" if code is None else code
    return _csv_texte(colonnes, lignes.values())


def sauvegarder_tableau_complet(session):
    """Générer l'export à côté des métriques, afin de l'inclure dans l'historique."""
    from .service import lire_etat
    session = Path(session)
    etat = lire_etat(session)
    nom = etat.get("dossier", "")
    if not re.fullmatch(r"desordre_[a-f0-9]{16}", nom):
        return None
    dossier = session / nom
    if not dossier.is_dir() or dossier.is_symlink():
        return None
    if not (dossier / "indicateurs_engagement.csv").is_file():
        return None
    texte = construire_tableau_complet(session, dossier)
    cible = dossier / FICHIER
    temporaire = dossier / (FICHIER + ".tmp")
    temporaire.write_text(texte, encoding="utf-8")
    temporaire.replace(cible)
    return cible


def fusionner_tableaux(fichiers, priorite="premier"):
    """Union des colonnes, dédoublonnage TikTok et provenance des lots.

    fichiers: séquence (nom, bytes), uniquement CSV complets ScrapTikTok.
    Une publication déjà présente est soit conservée (premier), soit remplacée
    (dernier). Ne jamais multiplier artificiellement l'effectif statistique.
    """
    if priorite not in {"premier", "dernier"}:
        raise ValueError("Politique de doublons inconnue.")
    if not 1 <= len(fichiers) <= MAX_FICHIERS:
        raise ValueError(f"Chargez entre 1 et {MAX_FICHIERS} tableaux.")
    lignes = {}
    colonnes = ["publication_id", "url", "analyse_source"]
    doublons = 0
    divergences = 0
    total = 0
    for nom, contenu in fichiers:
        if not nom.lower().endswith(".csv"):
            raise ValueError("L'import accepte uniquement les exports CSV.")
        if not isinstance(contenu, bytes) or len(contenu) > MAX_OCTETS:
            raise ValueError("Un fichier dépasse la limite de 10 Mo.")
        try:
            texte = contenu.decode("utf-8-sig")
        except UnicodeError as erreur:
            raise ValueError("Les tableaux doivent être encodés en UTF-8.") from erreur
        lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
        champs = lecteur.fieldnames or []
        if not {"publication_id", "url", "indice_desordre"}.issubset(champs):
            raise ValueError(
                f"{nom} n'est pas un tableau complet de Désordre visuel "
                "(colonnes publication_id, url, indice_desordre attendues)."
            )
        if len(champs) != len(set(champs)) or None in champs:
            raise ValueError("Colonnes dupliquées ou invalides dans " + nom)
        colonnes = list(dict.fromkeys([*colonnes, *champs]))
        for ligne in lecteur:
            total += 1
            if total > MAX_LIGNES:
                raise ValueError("Limite de 100 000 lignes atteinte.")
            if None in ligne:
                raise ValueError(f"Ligne CSV incorrecte dans {nom}.")
            identifiant = _identifiant(ligne)
            if not re.fullmatch(r"[0-9]+", identifiant):
                raise ValueError(f"Identifiant TikTok manquant ou incorrect dans {nom}.")
            ligne["publication_id"] = identifiant
            ligne["analyse_source"] = ligne.get("analyse_source") or nom
            existante = lignes.get(identifiant)
            if existante is not None:
                doublons += 1
                communs = set(existante) & set(ligne) - {"analyse_source"}
                if any(existante.get(k) not in (None, "") and ligne.get(k) not in (None, "")
                       and str(existante[k]) != str(ligne[k]) for k in communs):
                    divergences += 1
                if priorite == "premier":
                    continue
            lignes[identifiant] = ligne
    return {
        "lignes": list(lignes.values()),
        "colonnes": colonnes,
        "total_initial": total,
        "nombre_unique": len(lignes),
        "doublons": doublons,
        "doublons_divergents": divergences,
        "csv": _csv_texte(colonnes, lignes.values()),
    }
