#!/usr/bin/env python3
"""Prétraitement multilingue spaCy pour IRaMuTeQ-Lab."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


POS_IRAMUTEQ = {
    "NOUN": "nom",
    "PROPN": "nom",
    "VERB": "ver",
    "AUX": "aux",
    "ADJ": "adj",
    "ADV": "adv",
    "ADP": "pre",
    "PRON": "pro",
    "CCONJ": "con",
    "SCONJ": "con",
}

MODEL_PATTERN = re.compile(r"^[a-z]{2,3}_[a-z0-9_]+_(?:sm|md|lg|trf)$")


def convertir_pos(pos_spacy: str) -> str:
    return POS_IRAMUTEQ.get((pos_spacy or "").upper(), "AUTRE_FORME")


def charger_modele(nom_modele: str):
    if not MODEL_PATTERN.fullmatch(nom_modele):
        raise ValueError(
            "Nom de modèle spaCy invalide. Exemple attendu : de_core_news_md."
        )

    try:
        import spacy
    except ImportError as exc:
        raise RuntimeError("spaCy n'est pas installé sur le serveur.") from exc

    try:
        nlp = spacy.load(nom_modele, exclude=["ner", "parser", "textcat"])
    except OSError as exc:
        raise RuntimeError(
            f"Le modèle spaCy '{nom_modele}' n'est pas installé sur le serveur."
        ) from exc

    composants = set(nlp.pipe_names)
    possede_pos = bool(composants.intersection({"tagger", "morphologizer"}))
    possede_lemme = "lemmatizer" in composants or "trainable_lemmatizer" in composants
    if not possede_pos or not possede_lemme:
        raise RuntimeError(
            f"Le modèle '{nom_modele}' doit fournir le POS et la lemmatisation. "
            f"Composants détectés : {', '.join(nlp.pipe_names) or 'aucun'}."
        )
    return nlp


def lire_documents(path: Path) -> list[tuple[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        if not reader.fieldnames or not {"doc_id", "text"}.issubset(reader.fieldnames):
            raise ValueError("Le fichier d'entrée doit contenir les colonnes doc_id et text.")
        return [(row["doc_id"], row["text"]) for row in reader]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-docs", required=True, type=Path)
    parser.add_argument("--output-lexicon", required=True, type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--lemmatize", action="store_true")
    parser.add_argument("--remove-stopwords", action="store_true")
    parser.add_argument("--remove-punct", action="store_true")
    parser.add_argument("--remove-numbers", action="store_true")
    parser.add_argument("--filter-morpho", action="store_true")
    parser.add_argument("--keep-pos", default="")
    parser.add_argument("--keep-unknown", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    nlp = charger_modele(args.model)
    documents = lire_documents(args.input)
    pos_conserves = {
        value.strip().lower() for value in args.keep_pos.split(",") if value.strip()
    }
    lexique: dict[str, tuple[str, str]] = {}

    args.output_docs.parent.mkdir(parents=True, exist_ok=True)
    args.output_lexicon.parent.mkdir(parents=True, exist_ok=True)

    textes = (text for _, text in documents)
    docs_spacy = nlp.pipe(textes, batch_size=max(1, args.batch_size))

    with args.output_docs.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["doc_id", "text"], delimiter="\t")
        writer.writeheader()
        for (doc_id, _), doc in zip(documents, docs_spacy):
            formes = []
            for token in doc:
                if token.is_space:
                    continue
                pos_iramuteq = convertir_pos(token.pos_)
                if args.remove_punct and token.is_punct:
                    continue
                if args.remove_numbers and token.like_num:
                    continue
                if args.remove_stopwords and token.is_stop:
                    continue
                if args.filter_morpho:
                    connu = pos_iramuteq != "AUTRE_FORME"
                    if connu and pos_iramuteq not in pos_conserves:
                        continue
                    if not connu and not args.keep_unknown:
                        continue

                forme = token.text.strip().lower()
                lemme = (token.lemma_ or token.text).strip().lower()
                if not forme or not lemme:
                    continue
                valeur = lemme if args.lemmatize else forme
                formes.append(valeur)
                lexique.setdefault(forme, (lemme, pos_iramuteq))
            writer.writerow({"doc_id": doc_id, "text": " ".join(formes)})

    with args.output_lexicon.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["c_mot", "c_lemme", "c_morpho"],
            delimiter="\t",
        )
        writer.writeheader()
        for forme, (lemme, morpho) in sorted(lexique.items()):
            writer.writerow({"c_mot": forme, "c_lemme": lemme, "c_morpho": morpho})


if __name__ == "__main__":
    main()
