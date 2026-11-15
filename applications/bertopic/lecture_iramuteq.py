"""Lecture et export de corpus IRaMuTeQ sans modification des métadonnées."""
from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pandas as pd

MOTIF_ENTETE = re.compile(r"^\s*\*{4}(?:\s+\*[^\s*]+)*\s*$")
MOTIF_VARIABLE = re.compile(r"\*([^\s*]+)")


@dataclass(frozen=True)
class Document:
    numero: int
    entete: str
    variables: tuple[str, ...]
    texte: str


def decoder_fichier(contenu: bytes) -> str:
    """Décoder les exports IRaMuTeQ UTF-8 ou Windows-1252."""
    for encodage in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return contenu.decode(encodage)
        except UnicodeDecodeError:
            continue
    raise ValueError("Encodage non reconnu : fournir un fichier UTF-8.")


def analyser_corpus(contenu: bytes | str) -> list[Document]:
    """Conserver chaque unité initiale, même si elle contient plusieurs lignes."""
    texte = decoder_fichier(contenu) if isinstance(contenu, bytes) else contenu
    documents: list[Document] = []
    entete: str | None = None
    lignes: list[str] = []
    avant_premier: list[str] = []

    def ajouter_document() -> None:
        if entete is None:
            return
        contenu_document = "\n".join(lignes).strip("\n")
        variables = tuple(MOTIF_VARIABLE.findall(entete[4:]))
        documents.append(Document(len(documents) + 1, entete.strip(), variables, contenu_document))

    for ligne in texte.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if MOTIF_ENTETE.fullmatch(ligne):
            ajouter_document()
            entete = ligne.strip()
            lignes = []
        elif entete is not None:
            lignes.append(ligne)
        elif ligne.strip():
            avant_premier.append(ligne)
    ajouter_document()
    if avant_premier:
        raise ValueError("Contenu détecté avant le premier en-tête IRaMuTeQ (****).")
    if not documents:
        raise ValueError("Aucun en-tête IRaMuTeQ valide détecté : attendu **** *variable_valeur.")
    return documents


def tableau_documents(documents: list[Document]) -> pd.DataFrame:
    """Fournir les variables étoilées en colonnes, sans perdre leurs valeurs brutes."""
    lignes: list[dict[str, object]] = []
    for document in documents:
        enregistrement: dict[str, object] = {
            "numero_document": document.numero,
            "entete_iramuteq": document.entete,
            "variables_iramuteq": " ".join("*" + v for v in document.variables),
            "texte": document.texte,
            "nombre_caracteres": len(document.texte.strip()),
        }
        for variable in document.variables:
            if "_" in variable:
                cle, valeur = variable.split("_", 1)
            else:
                cle, valeur = variable, "oui"
            nom_colonne = "variable_" + cle
            precedent = enregistrement.get(nom_colonne)
            enregistrement[nom_colonne] = (
                str(precedent) + " | " + valeur if precedent is not None else valeur
            )
        lignes.append(enregistrement)
    return pd.DataFrame(lignes)


def exporter_iramuteq(documents: list[Document], categories: dict[int, str], nom_variable: str) -> bytes:
    """Ajouter une variable étoilée sans altérer le texte ou l'en-tête d'origine."""
    parties: list[str] = []
    for document in documents:
        categorie = re.sub(r"[^A-Za-z0-9_-]+", "_", categories.get(document.numero, "indetermine"))
        entete = document.entete + f" *{nom_variable}_{categorie}"
        parties.append(entete + "\n" + document.texte)
    return ("\n\n".join(parties) + "\n").encode("utf-8")


def exporter_csv(tableau: pd.DataFrame) -> bytes:
    tampon = io.StringIO()
    tableau.to_csv(tampon, index=False, sep=";", encoding="utf-8", lineterminator="\n")
    return ("\ufeff" + tampon.getvalue()).encode("utf-8")
