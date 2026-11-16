"""Codage multithématique et non exclusif de textes avec Qwen/Ollama."""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from codage_qwen import CONTEXTE_MAXIMUM, MODELE, SYSTEME_COMMUN, URL_OLLAMA

CHAMPS_THEMES = (
    "theme_denonciation",
    "theme_indignation",
    "theme_persecuteur",
)

SCHEMA_MATRICE: dict[str, Any] = {
    "type": "object",
    "properties": {
        **{champ: {"type": "boolean"} for champ in CHAMPS_THEMES},
        "indice_denonciation": {"type": "string"},
        "indice_indignation": {"type": "string"},
        "indice_persecuteur": {"type": "string"},
        "acteur_designe": {"type": "string"},
        "incertitude_interpretation": {"type": "boolean"},
        "justification": {"type": "string"},
    },
    "required": [
        *CHAMPS_THEMES,
        "indice_denonciation", "indice_indignation", "indice_persecuteur",
        "acteur_designe", "incertitude_interpretation", "justification",
    ],
    "additionalProperties": False,
}

PROMPT_MATRICE_DEFAUT = """Annote le texte selon trois opérations discursives distinctes et
non exclusives, dans une perspective de sciences humaines et sociales.
DÉNONCIATION : le locuteur condamne ou critique explicitement une violence.
INDIGNATION : le locuteur exprime explicitement une colère, une révolte,
une consternation ou un sentiment d'injustice devant une violence.
PERSÉCUTEUR DÉSIGNÉ : le locuteur attribue explicitement une violence,
une persécution ou une oppression à un acteur identifié ou désigné.
Il s'agit d'une attribution discursive, jamais d'une culpabilité démontrée.
Chaque dimension est codée indépendamment (vrai ou faux).
Une même unité peut relever des trois dimensions.
Ne conclus pas à une indignation simplement parce qu'une violence est citée.
Ne déduis pas une dénonciation de la seule description d'un événement.
Ne déduis pas un persécuteur de la seule mention d'une institution.
Les textes courts, familiers, SMS, fautifs, ironiques ou incomplets sont
des données : n'invente aucun sens ni acteur pour combler les lacunes.
En cas d'ambiguïté, signale incertitude_interpretation=true.
Les indices sont des citations textuelles courtes et littérales du passage ;
si un thème est absent, son indice est vide. Réponds en JSON uniquement."""


def segmenter_texte(
    texte: str, longueur_max: int = 1000, recouvrement: int = 90
) -> list[str]:
    """Segmenter sans supprimer les passages des textes descriptifs longs."""
    if longueur_max < 200 or recouvrement < 0 or recouvrement >= longueur_max:
        raise ValueError("Les paramètres de segmentation sont invalides.")
    if not texte.strip():
        return []
    segments: list[str] = []
    debut = 0
    while debut < len(texte):
        fin = min(debut + longueur_max, len(texte))
        if fin < len(texte):
            minimum = debut + int(longueur_max * 0.65)
            separation = max(
                texte.rfind("\n", minimum, fin),
                texte.rfind(". ", minimum, fin),
                texte.rfind("! ", minimum, fin),
                texte.rfind("? ", minimum, fin),
                texte.rfind(" ", minimum, fin),
            )
            if separation >= minimum:
                fin = separation + 1
        segments.append(texte[debut:fin])
        if fin == len(texte):
            break
        debut = max(debut + 1, fin - recouvrement)
    return segments


def valider_annotation(objet: object, passage: str) -> dict[str, object]:
    """Contrôler le JSON, les indices littéraux et la cohérence du codage."""
    if not isinstance(objet, dict):
        raise ValueError("La sortie multithématique n'est pas un objet JSON.")
    for champ in (*CHAMPS_THEMES, "incertitude_interpretation"):
        if type(objet.get(champ)) is not bool:
            raise ValueError(f"Réponse booléenne invalide : {champ}.")
    for champ in (
        "indice_denonciation", "indice_indignation", "indice_persecuteur",
        "acteur_designe", "justification",
    ):
        if not isinstance(objet.get(champ), str):
            raise ValueError(f"Champ textuel invalide : {champ}.")
    resultat = {
        champ: objet[champ] for champ in (
            *CHAMPS_THEMES,
            "indice_denonciation", "indice_indignation", "indice_persecuteur",
            "acteur_designe", "incertitude_interpretation", "justification",
        )
    }
    paires = (
        ("theme_denonciation", "indice_denonciation"),
        ("theme_indignation", "indice_indignation"),
        ("theme_persecuteur", "indice_persecuteur"),
    )
    for code, indice in paires:
        citation = str(resultat[indice]).strip()
        if not resultat[code]:
            resultat[indice] = ""
        elif not citation or citation not in passage:
            # Une citation inventée ne doit jamais être enregistrée comme indice.
            resultat[indice] = ""
            resultat["incertitude_interpretation"] = True
        else:
            resultat[indice] = citation
    if not resultat["theme_persecuteur"]:
        resultat["acteur_designe"] = ""
    return resultat


def regrouper_annotations(
    annotations: list[dict[str, object]]
) -> dict[str, object]:
    """Réunir les annotations de segments sans imposer une classe unique."""
    if not annotations:
        raise ValueError("Aucune annotation à regrouper.")
    resultat: dict[str, object] = {
        code: any(bool(annotation[code]) for annotation in annotations)
        for code in CHAMPS_THEMES
    }
    for code in ("denonciation", "indignation", "persecuteur"):
        champ = "indice_" + code
        extraits = [
            str(ann[champ]).strip() for ann in annotations
            if ann["theme_" + code] and str(ann[champ]).strip()
        ]
        # Ne pas répéter plusieurs fois les mêmes citations.
        resultat[champ] = " | ".join(dict.fromkeys(extraits))[:1000]
    acteurs = [
        str(ann["acteur_designe"]).strip()
        for ann in annotations if ann["theme_persecuteur"]
        and str(ann["acteur_designe"]).strip()
    ]
    resultat["acteur_designe"] = " | ".join(dict.fromkeys(acteurs))[:500]
    resultat["incertitude_interpretation"] = any(
        bool(ann["incertitude_interpretation"]) for ann in annotations
    )
    justifications = [
        str(ann["justification"]).strip() for ann in annotations
        if str(ann["justification"]).strip()
    ]
    resultat["justification"] = " | ".join(dict.fromkeys(justifications))[:1000]
    return resultat


def coder_multithemes(
    texte: str,
    consigne: str = PROMPT_MATRICE_DEFAUT,
    contexte: str = "",
    temperature: float = 0.1,
    session: requests.Session | None = None,
    longueur_segment: int = 850,
) -> dict[str, object]:
    """Annoter tout le texte, éventuellement segmenté, sans troncature muette."""
    if not consigne.strip():
        raise ValueError("Le prompt multithématique est vide.")
    if len(consigne.strip()) > 1700:
        raise ValueError(
            "Le prompt dépasse 1700 caractères pour le contexte local "
            "de Qwen. Raccourcissez la consigne avant de relancer."
        )
    if not texte.strip():
        raise ValueError("Impossible d'annoter un texte vide.")
    if longueur_segment > 1600:
        raise ValueError("Segments trop longs pour le contexte local Qwen.")
    segments = segmenter_texte(texte, longueur_max=longueur_segment)
    requetes = session or requests
    annotations: list[dict[str, object]] = []
    systeme = (
        SYSTEME_COMMUN + "\n\nConsigne du chercheur :\n"
        + consigne.strip()
        + "\nRespecte strictement le schéma JSON. "
        "Les trois dimensions sont indépendantes. "
        "Ne transforme jamais une attribution de responsabilité en fait établi."
    )
    for numero, passage in enumerate(segments, start=1):
        message = (
            f"Segment {numero}/{len(segments)} du même document.\n"
            f"Contexte du chercheur : {contexte[:350]}\n"
            "Annote uniquement le passage délimité, sans inventer d'indices.\n"
            f"<texte>\n{passage}\n</texte>\n/no_think"
        )
        reponse = requetes.post(
            URL_OLLAMA + "/api/chat",
            json={
                "model": MODELE,
                "stream": False,
                "think": False,
                "messages": [
                    {"role": "system", "content": systeme},
                    {"role": "user", "content": message},
                ],
                "format": SCHEMA_MATRICE,
                "options": {
                    "temperature": float(temperature),
                    "num_ctx": CONTEXTE_MAXIMUM,
                    "num_predict": 260,
                },
                "keep_alive": "5m",
            },
            timeout=(10, 240),
        )
        try:
            reponse.raise_for_status()
        except requests.HTTPError as erreur:
            raise requests.HTTPError(
                f"Modèle sollicité : {MODELE} ; segment {numero}/{len(segments)} ; "
                f"HTTP {reponse.status_code} : {reponse.text[:700]}",
                response=reponse,
            ) from erreur
        corps = reponse.json().get("message", {}).get("content", "")
        if not isinstance(corps, str) or not corps.strip():
            raise ValueError(
                f"Aucune annotation retournée pour le segment {numero}/{len(segments)}."
            )
        try:
            objet = json.loads(corps)
        except json.JSONDecodeError as erreur:
            raise ValueError(
                f"JSON invalide sur le segment {numero}/{len(segments)}."
            ) from erreur
        annotations.append(valider_annotation(objet, passage))
    resultat = regrouper_annotations(annotations)
    resultat["nombre_segments"] = len(segments)
    resultat["segments_traites"] = len(annotations)
    resultat["texte_tronque"] = False
    resultat["contexte_tronque"] = len(contexte) > 350
    resultat["mode_analyse"] = "matrice"
    resultat["reponse_qwen"] = json.dumps(resultat, ensure_ascii=False)
    return resultat
