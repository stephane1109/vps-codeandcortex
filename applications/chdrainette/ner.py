# ner.py
# -*- coding: utf-8 -*-

"""
Extraction NER spaCy FR pour Rainette
Entrée : TSV (doc_id, text)
Sortie : TSV (doc_id, ent_text, ent_label, start_char, end_char)
"""

import argparse
import csv
import sys
from typing import List, Tuple

import spacy


def lire_tsv(chemin: str) -> Tuple[List[str], List[str]]:
    doc_ids: List[str] = []
    textes: List[str] = []
    with open(chemin, "r", encoding="utf-8", newline="") as f:
        lecteur = csv.DictReader(f, delimiter="\t")
        if lecteur.fieldnames is None:
            raise ValueError("TSV invalide : en-tête manquant.")
        if "doc_id" not in lecteur.fieldnames or "text" not in lecteur.fieldnames:
            raise ValueError("Le TSV doit contenir les colonnes 'doc_id' et 'text'.")
        for row in lecteur:
            doc_ids.append((row.get("doc_id", "") or "").strip())
            textes.append(row.get("text", "") or "")
    return doc_ids, textes


def ecrire_tsv(chemin: str, lignes: List[dict]) -> None:
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        champs = ["doc_id", "ent_text", "ent_label", "start_char", "end_char"]
        ecrivain = csv.DictWriter(f, fieldnames=champs, delimiter="\t")
        ecrivain.writeheader()
        for row in lignes:
            ecrivain.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Chemin TSV d'entrée (doc_id, text).")
    parser.add_argument("--output", required=True, help="Chemin TSV de sortie.")
    parser.add_argument("--modele", default="fr_core_news_md", help="Nom du modèle spaCy FR.")
    args = parser.parse_args()

    try:
        nlp = spacy.load(args.modele)
    except Exception as e:
        sys.stderr.write(f"Erreur chargement modèle spaCy '{args.modele}' : {e}\n")
        return 2

    # On ne garde que tok2vec + ner pour accélérer et stabiliser
    keep = {"tok2vec", "ner"}
    disable = [p for p in nlp.pipe_names if p not in keep]
    if disable:
        nlp.disable_pipes(*disable)

    try:
        doc_ids, textes = lire_tsv(args.input)
    except Exception as e:
        sys.stderr.write(f"Erreur lecture TSV : {e}\n")
        return 3

    lignes: List[dict] = []
    try:
        for did, doc in zip(doc_ids, nlp.pipe(textes)):
            for ent in doc.ents:
                txt = (ent.text or "").strip()
                if not txt:
                    continue

                lignes.append(
                    {
                        "doc_id": did,
                        "ent_text": " ".join(txt.split()),
                        "ent_label": ent.label_,
                        "start_char": ent.start_char,
                        "end_char": ent.end_char,
                    }
                )
    except Exception as e:
        sys.stderr.write(f"Erreur traitement NER : {e}\n")
        return 4

    try:
        ecrire_tsv(args.output, lignes)
    except Exception as e:
        sys.stderr.write(f"Erreur écriture TSV : {e}\n")
        return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
