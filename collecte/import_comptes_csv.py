"""Lire des listes de comptes TikTok issues de collectes antérieures."""

import csv
import io
import unicodedata

from collecte.verification_comptes import normaliser_compte


COLONNES_COMPTES = (
    "username", "compte", "comptes", "compte_tiktok",
    "comptes_tiktok", "profil", "profils", "profil_tiktok",
    "utilisateur", "nom_utilisateur", "nom_d_utilisateur",
    "unique_id", "uniqueid", "author", "author_username",
    "auteur", "url_compte", "url_profil", "lien_profil",
)
TAILLE_MAX_FICHIER = 10 * 1024 * 1024
NOMBRE_MAX_FICHIERS = 20


def normaliser_entete(entete):
    """Uniformiser le nom d'une colonne sans modifier les identifiants."""
    texte = unicodedata.normalize("NFKD", str(entete).strip().lower())
    texte = "".join(caractere for caractere in texte
                    if not unicodedata.combining(caractere))
    return "_".join("".join(
        caractere if caractere.isalnum() else " " for caractere in texte
    ).split())


def choisir_separateur(texte):
    """Reconnaître les formats CSV francophones et anglophones."""
    echantillon = texte[:8192]
    try:
        return csv.Sniffer().sniff(echantillon, delimiters=";,\t").delimiter
    except csv.Error:
        premiere_ligne = next(
            (ligne for ligne in texte.splitlines() if ligne.strip()), "")
        return max((";", ",", "\t"), key=premiere_ligne.count)


def lire_comptes_csv(contenu):
    """Extraire les profils, en ignorant les doublons et lignes incorrectes."""
    if not isinstance(contenu, bytes):
        raise ValueError("Le contenu du fichier CSV doit être binaire.")
    if len(contenu) > TAILLE_MAX_FICHIER:
        raise ValueError("Le fichier dépasse la taille maximale de 10 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError:
        texte = contenu.decode("cp1252")
    if not texte.strip():
        raise ValueError("Le fichier CSV est vide.")

    lecteur = csv.reader(
        io.StringIO(texte, newline=""),
        delimiter=choisir_separateur(texte))
    premiere_ligne = next((ligne for ligne in lecteur if any(
        valeur.strip() for valeur in ligne)), None)
    if premiere_ligne is None:
        raise ValueError("Le fichier CSV ne contient aucun compte.")

    entetes = [normaliser_entete(valeur) for valeur in premiere_ligne]
    indice = next((
        entetes.index(colonne) for colonne in COLONNES_COMPTES
        if colonne in entetes), None)
    premiere_valeur = None
    if indice is None:
        if len(premiere_ligne) != 1:
            raise ValueError(
                "Colonne de comptes introuvable. Utilisez username, compte, "
                "profil, author ou url_compte.")
        # Un CSV à une seule colonne peut ne pas avoir d'en-tête.
        try:
            normaliser_compte(premiere_ligne[0])
        except (ValueError, AttributeError, TypeError) as erreur:
            raise ValueError(
                "En-tête de comptes non reconnu. Utilisez username ou compte."
            ) from erreur
        indice = 0
        premiere_valeur = premiere_ligne[indice]

    lignes = ([premiere_valeur] if premiere_valeur is not None else [])
    lignes.extend(
        ligne[indice] if indice < len(ligne) else ""
        for ligne in lecteur
        if any(valeur.strip() for valeur in ligne)
    )

    comptes = []
    deja_vus = set()
    invalides = []
    doublons = 0
    for position, valeur in enumerate(lignes, start=1):
        try:
            compte = normaliser_compte(valeur)
        except (ValueError, AttributeError, TypeError):
            invalides.append({
                "ligne": position, "valeur": str(valeur)[:80]})
            continue
        if compte in deja_vus:
            doublons += 1
            continue
        deja_vus.add(compte)
        comptes.append(compte)

    if not comptes:
        raise ValueError("Aucun compte TikTok valide n'a été trouvé dans le CSV.")
    return {
        "comptes": comptes,
        "doublons": doublons,
        "invalides": invalides,
        "lignes_lues": len(lignes),
    }


def lire_plusieurs_csv(fichiers):
    """Fusionner plusieurs listes CSV en conservant l'ordre des profils."""
    if not fichiers:
        raise ValueError("Sélectionnez au moins un fichier CSV.")
    if len(fichiers) > NOMBRE_MAX_FICHIERS:
        raise ValueError("Importez 20 fichiers CSV au maximum.")

    selection = []
    deja_vus = set()
    doublons = 0
    invalides = []
    lignes_lues = 0
    for nom, contenu in fichiers:
        try:
            resultat = lire_comptes_csv(contenu)
        except (ValueError, csv.Error) as erreur:
            raise ValueError(f"{nom} : {erreur}") from erreur
        lignes_lues += resultat["lignes_lues"]
        doublons += resultat["doublons"]
        invalides.extend([
            {"fichier": nom, **ligne} for ligne in resultat["invalides"]
        ])
        for compte in resultat["comptes"]:
            if compte in deja_vus:
                doublons += 1
            else:
                deja_vus.add(compte)
                selection.append(compte)
    return {
        "comptes": selection, "doublons": doublons,
        "invalides": invalides, "lignes_lues": lignes_lues,
        "fichiers": len(fichiers),
    }
