"""Import des commentaires CSV avec préservation de l'auteur et du texte."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata

from lecture_iramuteq import Document, decoder_fichier


def identifiant_auteur(nom_affiche: str) -> str:
    """Former un identifiant IRaMuTeQ stable sans perdre le nom CSV d'origine."""
    ascii_normalise = unicodedata.normalize("NFKD", nom_affiche)
    ascii_normalise = ascii_normalise.encode("ascii", errors="ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "_", ascii_normalise.lower()).strip("_")[:35]
    base = base or "anonyme"
    empreinte = hashlib.sha256(nom_affiche.encode("utf-8")).hexdigest()[:10]
    return f"{base}_{empreinte}"


def analyser_commentaires_csv(
    contenu: bytes | str, numero_depart: int = 0
) -> tuple[list[Document], dict[int, dict[str, str]]]:
    """Lire un CSV français ou international et produire des unités documentaires.

    Le CSV exige les deux colonnes nom_affiche et texte, séparées par un
    point-virgule, une virgule ou une tabulation. Les retours à la ligne
    inclus dans les cellules entre guillemets sont pris en charge.
    """
    contenu_decode = decoder_fichier(contenu) if isinstance(contenu, bytes) else contenu
    if not contenu_decode.strip():
        raise ValueError("Le fichier de commentaires CSV est vide.")

    lecteur = None
    colonnes = None
    for separateur in (";", ",", "\t"):
        candidat = csv.DictReader(
            io.StringIO(contenu_decode, newline=""),
            delimiter=separateur, strict=True,
        )
        noms = candidat.fieldnames or []
        normalises = [nom.strip().lstrip("\ufeff").lower() for nom in noms]
        if "nom_affiche" in normalises and "texte" in normalises:
            if len(set(normalises)) != len(normalises):
                raise ValueError("Le CSV contient des colonnes dupliquées.")
            lecteur = candidat
            colonnes = {
                "nom_affiche": noms[normalises.index("nom_affiche")],
                "texte": noms[normalises.index("texte")],
            }
            break

    if lecteur is None or colonnes is None:
        raise ValueError(
            "Colonnes CSV non reconnues : nom_affiche et texte sont obligatoires. "
            "Séparateurs acceptés : virgule, point-virgule, tabulation."
        )

    documents: list[Document] = []
    metadonnees: dict[int, dict[str, str]] = {}
    try:
        for position, ligne in enumerate(lecteur, start=1):
            if None in ligne:
                raise ValueError(
                    f"Ligne CSV {position + 1} : trop de champs ou séparateur incorrect."
                )
            nom = str(ligne.get(colonnes["nom_affiche"]) or "")
            texte = str(ligne.get(colonnes["texte"]) or "")
            numero = numero_depart + position
            jetons = (
                "source_commentaires_csv",
                f"ligne_{numero}",
                f"auteur_{identifiant_auteur(nom)}",
            )
            entete = "**** " + " ".join("*" + jeton for jeton in jetons)
            documents.append(Document(
                numero=numero, entete=entete, variables=jetons, texte=texte,
            ))
            metadonnees[numero] = {
                "nom_affiche": nom,
                "ligne_csv": str(position + 1),
            }
    except csv.Error as erreur:
        raise ValueError(f"Le CSV contient une citation ou une ligne invalide : {erreur}") from erreur

    if not documents:
        raise ValueError("Le CSV ne contient aucun commentaire.")
    return documents, metadonnees
