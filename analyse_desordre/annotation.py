"""Codage humain de la violence physique visible, indépendant des mesures vidéo.

0 = absence de violence physique visible ; 1 = violence physique visible ;
None = non évaluée (jamais assimilée à 0).
Annotations sauvegardées par session et identifiant TikTok, pas par numéro de ligne.
"""
from functools import lru_cache
from pathlib import Path
import csv
import io
import json
import os
import re
import tempfile

NOM_FICHIER = "annotations_violence.json"
VARIABLE = "violence_visible"
MODALITES = {"Non évaluée": None, "Non": 0, "Oui": 1}


def lire_annotations(session):
    fichier = Path(session) / NOM_FICHIER
    if fichier.is_symlink():
        raise ValueError("Fichier d’annotations invalide.")
    if not fichier.is_file():
        return {}
    donnees = json.loads(fichier.read_text(encoding="utf-8"))
    if not isinstance(donnees, dict):
        raise ValueError("Format des annotations invalide.")
    return {str(identifiant): valeur for identifiant, valeur in donnees.items()
            if re.fullmatch(r"[0-9]+", str(identifiant)) and type(valeur) is int
            and valeur in (0, 1)}


def enregistrer_annotations(session, modifications, identifiants_valides):
    """Fusion atomique ; None retire le codage plutôt que d'enregistrer un faux 0.

    L'appelant doit protéger la lecture/modification/écriture avec le verrou du job.
    """
    session = Path(session)
    autorises = {str(x) for x in identifiants_valides}
    contenu = lire_annotations(session)
    for element in modifications:
        identifiant = str(element["publication_id"])
        code = element["violence_visible"]
        if identifiant not in autorises or not re.fullmatch(r"[0-9]+", identifiant):
            raise ValueError("Identifiant de publication absent du corpus.")
        if code is not None and (type(code) is not int or code not in (0, 1)):
            raise ValueError("Le codage doit être 0, 1 ou non évalué.")
        if code is None:
            contenu.pop(identifiant, None)
        else:
            contenu[identifiant] = code
    # Création dans le même dossier pour garantir os.replace atomique.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", prefix=".annotations_", suffix=".tmp",
        dir=session, delete=False
    ) as flux:
        temporaire = Path(flux.name)
        try:
            json.dump(contenu, flux, ensure_ascii=False, sort_keys=True, indent=2)
        except BaseException:
            temporaire.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporaire, session / NOM_FICHIER)
    finally:
        temporaire.unlink(missing_ok=True)
    return contenu


def fusionner(lignes, annotations):
    return [{**ligne, VARIABLE: annotations.get(str(ligne.get("publication_id")))}
            for ligne in lignes]


def statistiques_codage(annotations, total):
    oui = sum(valeur == 1 for valeur in annotations.values())
    non = sum(valeur == 0 for valeur in annotations.values())
    return {"oui": oui, "non": non, "non_evaluees": max(0, total - oui - non)}


def exporter_annotations_csv(publications, annotations):
    texte = io.StringIO(newline="")
    export = csv.writer(texte, delimiter=";")
    export.writerow(("publication_id", "url", "violence_visible"))
    for publication in publications:
        identifiant = str(publication.get("id") or publication.get("publication_id") or "")
        code = annotations.get(identifiant)
        export.writerow((identifiant, publication.get("url") or "",
                         "" if code is None else code))
    return "\ufeff" + texte.getvalue()


@lru_cache(maxsize=64)
def _calculs_violence(chemin, signature, valeurs):
    """Calculs mémorisés par version du CSV et par codages ; aucun réexamen vidéo."""
    from .service import lire_tableau
    from .statistiques import correlation_spearman
    from .engagement import VARIABLES_ENGAGEMENT
    from .indice import INDICATEURS
    import numpy as np

    lignes = lire_tableau(Path(chemin))
    codages = dict(valeurs)
    resultat = []
    for engagement in (*VARIABLES_ENGAGEMENT, *INDICATEURS):
        x, y = [], []
        for ligne in lignes:
            code = codages.get(str(ligne.get("publication_id")))
            valeur = ligne.get(engagement)
            if code is None or valeur is None:
                continue
            try:
                mesure = float(valeur)
            except (TypeError, ValueError):
                continue
            if not np.isfinite(mesure):
                continue
            x.append(code)
            y.append(mesure)
        calcul = correlation_spearman(x, y)
        resultat.append({"indicateur": VARIABLE, "engagement": engagement,
                         **calcul})
    valides = sorted((i for i, r in enumerate(resultat) if r["p"] is not None),
                     key=lambda i: resultat[i]["p"])
    minimum = 1.
    for rang in range(len(valides), 0, -1):
        i = valides[rang - 1]
        minimum = min(minimum, resultat[i]["p"] * len(valides) / rang)
        resultat[i]["p_ajustee_bh"] = minimum
    return resultat


def correlations_violence(chemin_csv, annotations):
    chemin = Path(chemin_csv)
    if not chemin.is_file() or not annotations:
        return []
    stat = chemin.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    return _calculs_violence(str(chemin.resolve()), signature,
                             tuple(sorted(annotations.items())))


def exporter_correlations_csv(correlations):
    texte = io.StringIO(newline="")
    champs = ("indicateur", "engagement", "n", "rho", "p", "p_ajustee_bh",
              "methode", "permutations", "raison")
    csv_out = csv.DictWriter(texte, fieldnames=champs, delimiter=";")
    csv_out.writeheader()
    for ligne in correlations:
        csv_out.writerow({k: v for k, v in ligne.items() if k in champs})
    return "\ufeff" + texte.getvalue()
