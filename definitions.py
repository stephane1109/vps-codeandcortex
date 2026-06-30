# definitions.py
# Fichier de légendes et glossaire pour l’application Streamlit
# Toutes les définitions sont centralisées ici.

import streamlit as st

def obtenir_definitions() -> str:
    return (
        "Déictiques : la détection repose sur un dictionnaire d’expressions, insensible à la casse, "
        "que vous pouvez enrichir. Elle n’est pas universelle : elle dépend donc du dictionnaire fourni.\n\n"
        "deictiques_proches_brut : nombre d’occurrences de déictiques temporels proches "
        "(ex. « maintenant », « aujourd’hui », « tout de suite », « à l’instant », « ce soir », « à présent », « actuellement »).\n"
        "deictiques_eloignes_brut : nombre d’occurrences de déictiques éloignés/futurs "
        "(ex. « demain », « la semaine prochaine », « plus tard », « à long terme », « à moyen terme », « prochainement »).\n"
        "deictiques_passes_brut : nombre d’occurrences de déictiques passés "
        "(ex. « hier », « la semaine dernière », « auparavant », « il y a », « jadis », « autrefois »).\n"
        "planification_brut : marqueurs lexicaux de planification/projection "
        "(ex. « plan », « programme », « feuille de route », « calendrier », « échéance », « stratégie », « objectif(s) », « agenda », « réforme(s) », « projet(s) », « roadmap »).\n\n"
        "Texte : les temps verbaux sont détectés par spaCy Transformer (CamemBERT) uniquement, via les traits morphologiques : "
        "présent (Tense=Pres), passé (Tense=Imp ou Tense=Past), futur (Tense=Fut). Les tableaux donnent les comptes, les ratios par rapport au nombre de verbes, et les listes de formes.\n\n"
        "Audio : l’analyse porte sur les silences, les pauses longues (≥ 300 ms) et le débit de parole. "
        "Graphique « Pauses » : énergie RMS, zones de silence et bandes continues pour chaque pause longue avec sa durée. "
        "Graphique « Débit » : activité vocale instantanée (0–1) et barres « débit par seconde ». "
        "Graphique « Parole vs Pause » : barres empilées par seconde indiquant la part de parole et de pause.\n\n"
        "Timeline : les segments issus de l’audio transcrit (Whisper) comportent t_debut et t_fin en secondes ; "
        "les fichiers .txt conservent ces colonnes en NaN."
    )

def obtenir_glossaire() -> dict:
    return {
        "present_brut": "Nombre de formes verbales au présent (spaCy Tense=Pres).",
        "passe_brut": "Nombre de formes verbales au passé (Imparfait/Past).",
        "futur_brut": "Nombre de formes verbales au futur (Tense=Fut).",
        "ratio_present_par_verbe": "Proportion de verbes au présent parmi tous les verbes.",
        "ratio_passe_par_verbe": "Proportion de verbes au passé parmi tous les verbes.",
        "ratio_futur_par_verbe": "Proportion de verbes au futur parmi tous les verbes.",
        "deictiques_proches_brut": "Occurrences de déictiques temporels proches (dictionnaire).",
        "deictiques_eloignes_brut": "Occurrences de déictiques temporels éloignés/futurs (dictionnaire).",
        "deictiques_passes_brut": "Occurrences de déictiques temporels passés (dictionnaire).",
        "planification_brut": "Occurrences de marqueurs de planification/projection (dictionnaire).",
        "causaux_brut": "Occurrences de connecteurs causaux/conditionnels (dictionnaire).",
        "termes_*": "Listes des formes effectivement détectées pour contrôle analytique.",
        "nb_pauses": "Nombre de pauses longues (≥ 300 ms).",
        "duree_pauses_totale_s": "Somme des durées des pauses longues, en secondes.",
        "duree_pause_moy_s": "Durée moyenne des pauses longues, en secondes.",
        "duree_pause_med_s": "Durée médiane des pauses longues, en secondes.",
        "silence_ratio": "Part du temps classée comme silence (0–1).",
        "parole_active_ratio": "1 − silence_ratio.",
        "debit_proxy_sps": "Approximation du débit global (pics d’énergie par seconde).",
        "activite_vocale_t": "Activité vocale instantanée (0–1) lissée sur ~1 s.",
        "timeline": "Toutes les séries temporelles commencent à t=0 s pour éviter tout décalage négatif."
    }

def afficher_legendes():
    st.header("Légendes et glossaire")
    st.write(obtenir_definitions())
    st.subheader("Glossaire des variables")
    for k, v in obtenir_glossaire().items():
        st.markdown(f"**{k}** — {v}")
