#!/usr/bin/env python3
"""Indexer les expressions candidates par document avec l'automate Aho-Corasick.

L'index est volontairement conservateur : les correspondances approximatives
sont confirmées ensuite par les expressions régulières historiques dans R.
Aucune substitution lexicale n'est effectuée ici.
"""

import json
import sys
import unicodedata
from collections import deque


def normaliser_pour_recherche(texte):
    """Normaliser largement pour éviter d'écarter une correspondance possible."""
    if not isinstance(texte, str):
        return ""
    texte = texte.casefold()
    texte = texte.translate(str.maketrans({
        "œ": "oe", "æ": "ae", "ø": "o",
        "’": "'", "ˈ": "'", "´": "'", "ʼ": "'", "ʹ": "'",
        chr(96): "'",
    }))
    return "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texte)
        if not unicodedata.category(caractere).startswith("M")
    )


def construire_automate(expressions):
    """Construire les transitions, échecs et listes d'expressions terminales."""
    transitions = [{}]
    echecs = [0]
    sorties = [[]]

    for indice, expression in enumerate(expressions):
        expression = normaliser_pour_recherche(expression)
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
                sorties.append([])
            etat = suivant
        sorties[etat].append(indice)

    file = deque(transitions[0].values())
    while file:
        etat = file.popleft()
        for caractere, suivant in transitions[etat].items():
            file.append(suivant)
            repli = echecs[etat]
            while repli and caractere not in transitions[repli]:
                repli = echecs[repli]
            echecs[suivant] = transitions[repli].get(caractere, 0)
            if sorties[echecs[suivant]]:
                sorties[suivant].extend(sorties[echecs[suivant]])
    return transitions, echecs, sorties


def indexer_expressions_par_document(textes, expressions):
    """Retourner les documents candidats pour chaque expression, en index zéro."""
    transitions, echecs, sorties = construire_automate(expressions)
    candidats = {}
    for numero_document, texte in enumerate(textes):
        etat = 0
        indices_trouves = set()
        for caractere in normaliser_pour_recherche(texte):
            while etat and caractere not in transitions[etat]:
                etat = echecs[etat]
            etat = transitions[etat].get(caractere, 0)
            if sorties[etat]:
                indices_trouves.update(sorties[etat])
        for indice in indices_trouves:
            candidats.setdefault(str(indice), []).append(numero_document)
    return candidats


def executer():
    """Lire les textes et les expressions et écrire l'index documentaire."""
    if len(sys.argv) != 3:
        raise ValueError("Utilisation : methodeAho.py entree.json sortie.json")
    with open(sys.argv[1], "r", encoding="utf-8") as entree:
        donnees = json.load(entree)
    candidats = indexer_expressions_par_document(donnees["textes"], donnees["motifs"])
    with open(sys.argv[2], "w", encoding="utf-8") as sortie:
        json.dump({"candidats": candidats}, sortie, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    executer()
