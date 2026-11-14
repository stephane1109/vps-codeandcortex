#!/usr/bin/env python3
"""Présélection Aho-Corasick des documents pour le dictionnaire d'expressions.

Ce module ne remplace aucune expression : les substitutions restent confiées
à la fonction R classique, afin de conserver exactement ses règles.
"""

import json
import sys
import unicodedata
from collections import deque


def normaliser_pour_recherche(texte):
    """Construire une clé de recherche tolérante aux variantes typographiques."""
    if not isinstance(texte, str):
        return ""
    texte = texte.casefold().replace("œ", "oe").replace("æ", "ae")
    apostrophes = {"’": "'", chr(96): "'", "´": "'", "ʼ": "'", "ʹ": "'"}
    texte = texte.translate(str.maketrans(apostrophes))
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texte)
        if not unicodedata.category(caractere).startswith("M")
    )


def construire_automate(expressions):
    """Construire le trie, les liens d'échec et les états terminaux."""
    transitions = [{}]
    echecs = [0]
    terminaux = [False]
    for expression in set(expressions):
        if not expression:
            continue
        etat = 0
        for caractere in expression:
            suivant = transitions[etat].get(caractere)
            if suivant is None:
                suivant = len(transitions)
                transitions[etat][caractere] = suivant
                transitions.append({})
                echecs.append(0)
                terminaux.append(False)
            etat = suivant
        terminaux[etat] = True

    file = deque(transitions[0].values())
    while file:
        etat = file.popleft()
        for caractere, suivant in transitions[etat].items():
            file.append(suivant)
            repli = echecs[etat]
            while repli and caractere not in transitions[repli]:
                repli = echecs[repli]
            echecs[suivant] = transitions[repli].get(caractere, 0)
            terminaux[suivant] = terminaux[suivant] or terminaux[echecs[suivant]]
    return transitions, echecs, terminaux


def contient_expression(texte, automate):
    """Détecter au moins une expression, sans effectuer de substitution."""
    transitions, echecs, terminaux = automate
    etat = 0
    for caractere in normaliser_pour_recherche(texte):
        while etat and caractere not in transitions[etat]:
            etat = echecs[etat]
        etat = transitions[etat].get(caractere, 0)
        if terminaux[etat]:
            return True
    return False


def selectionner_documents(textes, expressions):
    """Retourner les indices zéro-indexés des documents candidats."""
    automate = construire_automate(
        [normaliser_pour_recherche(expression) for expression in expressions]
    )
    return [
        indice
        for indice, texte in enumerate(textes)
        if contient_expression(texte, automate)
    ]


def executer():
    """Lire le JSON fourni par R et écrire les seuls indices candidats."""
    if len(sys.argv) != 3:
        raise ValueError("Utilisation : methodeAho.py entree.json sortie.json")
    with open(sys.argv[1], "r", encoding="utf-8") as entree:
        donnees = json.load(entree)
    indices = selectionner_documents(donnees["textes"], donnees["motifs"])
    with open(sys.argv[2], "w", encoding="utf-8") as sortie:
        json.dump({"indices": indices}, sortie, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    executer()
