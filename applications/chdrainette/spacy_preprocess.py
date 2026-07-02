# spacy_preprocess.py
# -*- coding: utf-8 -*-

"""
Prétraitement spaCy FR pour Rainette (Shiny / Hugging Face)
Entrée : TSV (doc_id, text)
Sortie : TSV (doc_id, text) reconstruit avec tokens filtrés
Optionnel : TSV tokens détaillés (doc_id, token, lemma, pos)
"""

import argparse
import csv
import sys
from typing import List, Tuple, Optional

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


def ecrire_tsv(chemin: str, doc_ids: List[str], textes: List[str]) -> None:
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        champs = ["doc_id", "text"]
        ecrivain = csv.DictWriter(f, fieldnames=champs, delimiter="\t")
        ecrivain.writeheader()
        for did, txt in zip(doc_ids, textes):
            ecrivain.writerow({"doc_id": did, "text": txt})


def ecrire_tokens(chemin: str, lignes: List[dict]) -> None:
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        champs = ["doc_id", "token", "lemma", "pos"]
        ecrivain = csv.DictWriter(f, fieldnames=champs, delimiter="\t")
        ecrivain.writeheader()
        for row in lignes:
            ecrivain.writerow(row)


def nettoyer_et_filtrer_doc(doc, pos_keep_set, utiliser_lemmes: bool) -> Tuple[str, List[dict]]:
    tokens_sortie: List[str] = []
    lignes_tokens: List[dict] = []

    for tok in doc:
        if tok.is_space or tok.is_punct or tok.like_num:
            continue
        pos = (tok.pos_ or "").upper().strip()
        if pos_keep_set and pos not in pos_keep_set:
            continue

        token_surface = (tok.text or "").strip()
        if not token_surface:
            continue

        if utiliser_lemmes:
            lemma = (tok.lemma_ or "").strip()
            if not lemma:
                lemma = token_surface
            forme = lemma.lower()
        else:
            forme = token_surface.lower()

        if not forme:
            continue

        tokens_sortie.append(forme)
        lignes_tokens.append(
            {
                "doc_id": "",  # rempli plus tard
                "token": token_surface.lower(),
                "lemma": (tok.lemma_ or token_surface).strip().lower(),
                "pos": pos,
            }
        )

    return " ".join(tokens_sortie), lignes_tokens


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Chemin TSV d'entrée (doc_id, text).")
    parser.add_argument("--output", required=True, help="Chemin TSV de sortie (doc_id, text).")
    parser.add_argument("--modele", default="fr_core_news_md", help="Nom du modèle spaCy FR.")
    parser.add_argument("--pos_keep", default="", help="Liste POS à conserver (virgules), ex: NOUN,ADJ,VERB.")
    parser.add_argument("--lemmes", default="0", help="1 pour utiliser token.lemma_, 0 sinon.")
    parser.add_argument("--lower_input", default="0", help="1 pour forcer le texte d'entrée en minuscules avant spaCy.")
    parser.add_argument("--output_tokens", default="", help="Chemin TSV optionnel pour exporter tokens (doc_id, token, lemma, pos).")

    args = parser.parse_args()

    utiliser_lemmes = str(args.lemmes).strip() == "1"
    lower_input = str(args.lower_input).strip() == "1"

    pos_keep = [p.strip().upper() for p in (args.pos_keep or "").split(",") if p.strip()]
    pos_keep_set = set(pos_keep)

    try:
        nlp = spacy.load(args.modele, disable=["ner", "parser"])
    except Exception as e:
        sys.stderr.write(f"Erreur chargement modèle spaCy '{args.modele}' : {e}\n")
        return 2

    try:
        doc_ids, textes = lire_tsv(args.input)
    except Exception as e:
        sys.stderr.write(f"Erreur lecture TSV : {e}\n")
        return 3

    if lower_input:
        textes = [t.lower() for t in textes]

    textes_sortie: List[str] = []
    tokens_export: List[dict] = []

    try:
        for did, doc in zip(doc_ids, nlp.pipe(textes)):
            reconstruit, lignes_tok = nettoyer_et_filtrer_doc(
                doc=doc,
                pos_keep_set=pos_keep_set,
                utiliser_lemmes=utiliser_lemmes,
            )
            textes_sortie.append(reconstruit)

            if args.output_tokens:
                for row in lignes_tok:
                    row["doc_id"] = did
                tokens_export.extend(lignes_tok)

    except Exception as e:
        sys.stderr.write(f"Erreur traitement spaCy : {e}\n")
        return 4

    try:
        ecrire_tsv(args.output, doc_ids, textes_sortie)
    except Exception as e:
        sys.stderr.write(f"Erreur écriture TSV : {e}\n")
        return 5

    if args.output_tokens:
        try:
            ecrire_tokens(args.output_tokens, tokens_export)
        except Exception as e:
            sys.stderr.write(f"Erreur écriture tokens TSV : {e}\n")
            return 6

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
