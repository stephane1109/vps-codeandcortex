"""Import des commentaires CSV avec sélection libre des colonnes."""
from __future__ import annotations

import csv
import hashlib
import io
import re
import unicodedata
from collections.abc import Iterator

from lecture_iramuteq import Document, decoder_fichier


def identifiant_auteur(nom_affiche: str) -> str:
    """Former un identifiant IRaMuTeQ stable sans perdre le nom CSV d'origine."""
    ascii_normalise = unicodedata.normalize("NFKD", nom_affiche)
    ascii_normalise = ascii_normalise.encode("ascii", errors="ignore").decode("ascii")
    base = re.sub(r"[^a-z0-9]+", "_", ascii_normalise.lower()).strip("_")[:35]
    base = base or "anonyme"
    empreinte = hashlib.sha256(nom_affiche.encode("utf-8")).hexdigest()[:10]
    return f"{base}_{empreinte}"


def ouvrir_lecteur_csv(
    contenu: bytes | str,
) -> tuple[csv.DictReader, list[str]]:
    """Détecter le séparateur et restituer tous les en-têtes d'un CSV."""
    texte = decoder_fichier(contenu) if isinstance(contenu, bytes) else contenu
    if not texte.strip():
        raise ValueError("Le fichier de commentaires CSV est vide.")

    try:
        separateur = csv.Sniffer().sniff(
            texte[:8192], delimiters=";,\t"
        ).delimiter
    except csv.Error:
        # Lorsque l'échantillon est trop court, comparer les en-têtes.
        nombres = []
        for candidat in (";", ",", "\t"):
            try:
                premiere_ligne = next(csv.reader(
                    io.StringIO(texte, newline=""),
                    delimiter=candidat, strict=True,
                ))
                nombres.append((len(premiere_ligne), candidat))
            except (csv.Error, StopIteration):
                continue
        separateur = max(nombres, default=(1, ";"), key=lambda x: x[0])[1]

    lecteur = csv.DictReader(
        io.StringIO(texte, newline=""),
        delimiter=separateur,
        strict=True,
    )
    colonnes = lecteur.fieldnames or []
    if not colonnes:
        raise ValueError("Le fichier CSV ne contient aucun en-tête.")
    if any(nom is None or not nom.strip() for nom in colonnes):
        raise ValueError("Le CSV contient une colonne sans nom.")

    # Les libellés et leur casse sont préservés pour l'affichage et les exports.
    normalises = [nom.strip().lstrip("\ufeff").casefold() for nom in colonnes]
    if len(set(normalises)) != len(normalises):
        raise ValueError("Le CSV contient des noms de colonnes dupliqués.")
    return lecteur, colonnes


def lister_colonnes_csv(contenu: bytes | str) -> list[str]:
    """Lister les colonnes réellement présentes pour les sélecteurs Streamlit."""
    _, colonnes = ouvrir_lecteur_csv(contenu)
    return colonnes


def analyser_commentaires_csv(
    contenu: bytes | str,
    numero_depart: int = 0,
    colonne_texte: str = "texte",
    colonne_auteur: str | None = "nom_affiche",
) -> tuple[list[Document], dict[int, dict[str, str]]]:
    """Transformer chaque ligne CSV en document, selon les colonnes sélectionnées.

    Sans choix explicite, les colonnes historiques « texte » et
    « nom_affiche » restent obligatoires pour préserver la compatibilité.
    L'interface peut sélectionner n'importe quelle colonne de commentaire
    et rendre facultative la colonne auteur.
    """
    lecteur, colonnes = ouvrir_lecteur_csv(contenu)
    if colonne_texte not in colonnes:
        raise ValueError(
            "Colonnes CSV obligatoires : la colonne de commentaire "
            f"« {colonne_texte} » est absente."
        )
    if colonne_auteur is not None and colonne_auteur not in colonnes:
        raise ValueError(
            "Colonnes CSV obligatoires : la colonne auteur "
            f"« {colonne_auteur} » est absente."
        )
    if colonne_auteur == colonne_texte:
        raise ValueError("La colonne auteur doit être distincte du commentaire.")

    documents: list[Document] = []
    metadonnees: dict[int, dict[str, str]] = {}
    try:
        for position, ligne in enumerate(lecteur, start=1):
            if None in ligne:
                raise ValueError(
                    f"Ligne CSV {position + 1} : nombre de champs incorrect."
                )
            texte = str(ligne.get(colonne_texte) or "")
            nom = str(ligne.get(colonne_auteur) or "") if colonne_auteur else ""
            numero = numero_depart + position
            jetons = (
                "source_commentaires_csv",
                f"ligne_{numero}",
                f"auteur_{identifiant_auteur(nom)}",
            )
            entete = "**** " + " ".join("*" + jeton for jeton in jetons)
            documents.append(Document(
                numero=numero,
                entete=entete,
                variables=jetons,
                texte=texte,
            ))
            informations = {
                "nom_affiche": nom,
                "ligne_csv": str(position + 1),
                "colonne_texte_source": colonne_texte,
                "colonne_auteur_source": colonne_auteur or "",
            }
            # Les autres colonnes originales restent accessibles dans
            # codage_commentaires.csv et ne sont pas transmises au modèle.
            for nom_colonne in colonnes:
                if nom_colonne not in (colonne_texte, colonne_auteur):
                    informations["csv_" + nom_colonne] = str(
                        ligne.get(nom_colonne) or ""
                    )
            metadonnees[numero] = informations
    except csv.Error as erreur:
        raise ValueError(
            f"Le CSV contient une ligne ou une citation invalide : {erreur}"
        ) from erreur

    if not documents:
        raise ValueError("Le CSV ne contient aucun commentaire.")
    return documents, metadonnees
