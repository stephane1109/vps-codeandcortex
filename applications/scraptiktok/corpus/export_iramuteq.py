"""Corpus UTF-8 ; variables normalisées, valeurs manquantes explicites."""
import re
import unicodedata
from pathlib import Path

def normaliser_modalite(valeur):
    if valeur is None or valeur == "": return "indetermine"
    texte = unicodedata.normalize("NFKD", str(valeur)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "_", texte).strip("_") or "indetermine"

def construire_corpus(documents):
    blocs = []
    for document in documents:
        texte = str(document.get("texte") or "").strip()
        if not texte: continue
        variables = {"id": document["id"], **document.get("variables", {})}
        entete = "**** " + " ".join("*" + normaliser_modalite(k) + "_" + normaliser_modalite(v) for k, v in variables.items())
        # Les astérisques du contenu ne doivent pas introduire de fausses variables.
        texte = texte.replace("*", " ").replace("\x00", "")
        blocs.append(entete + "\n" + texte)
    return "\n\n".join(blocs) + ("\n" if blocs else "")

def exporter_iramuteq(chemin, documents):
    Path(chemin).write_text(construire_corpus(documents), encoding="utf-8")
