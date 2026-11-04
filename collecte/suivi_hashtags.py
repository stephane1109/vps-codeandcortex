"""Bilan et reprise des sources hashtags de la Research API officielle."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timezone

from collecte.hashtags import variantes_hashtag

ETATS_REPRISE = frozenset({"non_commencee", "interrompue", "partielle", "echec"})
ETATS_VALIDES = ETATS_REPRISE | {"traitee", "en_attente", "en_cours"}
COLONNES_HISTORIQUES = ("collecte_id", "hashtag", "etat", "liens", "motif")
COLONNES_PAGINATION = (
    "date_debut", "date_fin", "source_pagination",
    "indice_periode", "debut_periode", "fin_periode",
    "cursor", "search_id", "pagination_invalide",
    "positions_research_json", "exporte_le",
)
COLONNES = COLONNES_HISTORIQUES + COLONNES_PAGINATION


def variantes_par_hashtag(hashtags, avec_accents=False):
    """Associer les graphies explorées à chaque hashtag sans doublon."""
    resultats = {}
    deja_vus = set()
    for hashtag in hashtags:
        variantes = []
        for variante in variantes_hashtag(hashtag, avec_accents=avec_accents):
            cle = variante.casefold()
            if cle not in deja_vus:
                variantes.append(variante)
                deja_vus.add(cle)
        if not variantes:
            # Deux hashtags distincts peuvent partager toutes leurs graphies
            # accentuées. Réutiliser la source déjà demandée dans le bilan au
            # lieu de considérer abusivement le second comme terminé.
            variantes = [variantes_hashtag(
                hashtag, avec_accents=avec_accents)[0]]
        resultats[hashtag] = variantes
    return resultats


def etats_variantes(hashtags, avec_accents, journal, *, source_en_cours=None,
                   termine=False):
    """Reconstituer le dernier statut de chaque graphie depuis le journal."""
    dernier = {}
    for entree in journal:
        if (isinstance(entree, dict) and isinstance(entree.get("source"), str)
                and entree["source"].startswith("#")):
            dernier[entree["source"][1:].casefold()] = entree
    etats = {}
    for variantes in variantes_par_hashtag(hashtags, avec_accents).values():
        for variante in variantes:
            entree = dernier.get(variante.casefold())
            if entree is None:
                etat = (
                    ("interrompue" if termine else "en_cours")
                    if source_en_cours == "#" + variante
                    else ("non_commencee" if termine else "en_attente")
                )
                motif, liens, position = "", 0, None
            else:
                rapport = entree.get("rapport") or {}
                etat = entree.get("statut_source")
                if etat not in ETATS_VALIDES:
                    etat = ("echec" if entree.get("statut") == "inaccessible"
                            else "partielle" if rapport.get("collecte_partielle")
                            else "traitee")
                if etat == "en_cours" and termine:
                    etat = "interrompue"
                motif = str(entree.get("message") or "")
                liens = len(rapport.get("discovered_urls") or [])
                position = rapport.get("reprise_pagination_research")
                if etat == "traitee" or not isinstance(position, dict):
                    position = None
            etats[variante.casefold()] = {
                "etat": etat, "motif": motif, "liens": liens,
                "position": position,
            }
    return etats


def etablir_bilan_hashtags(hashtags, avec_accents, journal, *,
                           source_en_cours=None, termine=False,
                           collecte_id="", date_debut="", date_fin=""):
    """Bilan réimportable incluant les curseurs pour chaque variante inachevée."""
    variantes = variantes_par_hashtag(hashtags, avec_accents)
    etats = etats_variantes(hashtags, avec_accents, journal,
                           source_en_cours=source_en_cours, termine=termine)
    bilan = []
    for hashtag, graphies in variantes.items():
        observations = [etats[v.casefold()] for v in graphies]
        valeurs = [o["etat"] for o in observations]
        if all(v == "traitee" for v in valeurs):
            etat = "traitee"
        elif any(v == "echec" for v in valeurs):
            etat = "echec"
        elif any(v == "interrompue" for v in valeurs):
            etat = "interrompue"
        elif any(v == "partielle" for v in valeurs):
            etat = "partielle"
        elif any(v == "en_cours" for v in valeurs):
            etat = "en_cours"
        elif any(v == "traitee" for v in valeurs):
            etat = "partielle"
        elif all(v == "non_commencee" for v in valeurs):
            etat = "non_commencee"
        else:
            etat = "en_attente"
        positions = {
            "#" + graphie: observation["position"]
            for graphie, observation in zip(graphies, observations)
            if (observation["etat"] in ETATS_REPRISE | {"en_cours"}
                and isinstance(observation["position"], dict)
                and isinstance(observation["position"].get("indice_periode"), int)
                and isinstance(observation["position"].get("debut_periode"), str)
                and isinstance(observation["position"].get("fin_periode"), str))
        }
        source, position = next(
            iter(positions.items()), ("", {}))
        bilan.append({
            "collecte_id": collecte_id,
            "hashtag": hashtag,
            "etat": etat,
            "liens": sum(o["liens"] for o in observations),
            "motif": " | ".join(dict.fromkeys(
                o["motif"] for o in observations if o["motif"])),
            "date_debut": date_debut or "",
            "date_fin": date_fin or "",
            "source_pagination": source,
            "indice_periode": position.get("indice_periode", ""),
            "debut_periode": position.get("debut_periode", ""),
            "fin_periode": position.get("fin_periode", ""),
            "cursor": (
                position.get("cursor") if position.get("cursor") is not None
                else ""),
            "search_id": position.get("search_id") or "",
            "pagination_invalide": (
                "1" if position.get("pagination_invalide") else "0"
                if position else ""),
            "positions_research_json": (
                json.dumps(positions, ensure_ascii=False,
                           sort_keys=True, separators=(",", ":"))
                if positions else ""),
        })
    return bilan


def hashtags_a_reprendre(bilan):
    """Extraire les hashtags présentant des variantes encore inachevées."""
    return [e["hashtag"] for e in bilan if e["etat"] in ETATS_REPRISE]


def preparer_reprise_hashtags(hashtags, avec_accents, journal, selection=None,
                              *, source_en_cours=None):
    """Limiter la nouvelle interrogation aux graphies réellement inachevées."""
    bilan = etablir_bilan_hashtags(
        hashtags, avec_accents, journal,
        source_en_cours=source_en_cours, termine=True)
    disponibles = hashtags_a_reprendre(bilan)
    if not disponibles:
        raise ValueError("Tous les hashtags ont été parcourus : aucune reprise nécessaire.")
    if selection is None:
        selection = disponibles
    if not selection or len(selection) != len(set(selection)):
        raise ValueError("Choisissez des hashtags distincts à reprendre.")
    if any(tag not in disponibles for tag in selection):
        raise ValueError("La reprise accepte uniquement les hashtags inachevés de cette collecte.")
    etats = etats_variantes(
        hashtags, avec_accents, journal,
        source_en_cours=source_en_cours, termine=True)
    graphies = variantes_par_hashtag(hashtags, avec_accents)
    a_interroger = [
        variante for tag in selection for variante in graphies[tag]
        if etats[variante.casefold()]["etat"] in ETATS_REPRISE
    ]
    if not a_interroger:
        raise ValueError("Aucune variante de hashtag inachevée.")
    return list(selection), a_interroger, bilan


def positions_pagination_research(journal, variantes):
    """Retrouver la première page non explorée de chaque source inachevée.

    Une position provient du journal de l'archive d'origine, jamais d'une
    entrée fournie par l'utilisateur. La dernière exécution d'une source
    détermine son état ; une source terminée ne garde pas d'ancien curseur.
    """
    autorisees = {"#" + variante for variante in variantes}
    positions = {}
    for entree in journal:
        if not isinstance(entree, dict):
            continue
        source = entree.get("source")
        if source not in autorisees:
            continue
        rapport = entree.get("rapport")
        if not isinstance(rapport, dict):
            continue
        position = rapport.get("reprise_pagination_research")
        if isinstance(position, dict) and (
                isinstance(position.get("indice_periode"), int)
                and isinstance(position.get("debut_periode"), str)
                and isinstance(position.get("fin_periode"), str)):
            positions[source] = {
                "indice_periode": position["indice_periode"],
                "debut_periode": position["debut_periode"],
                "fin_periode": position["fin_periode"],
                "cursor": position.get("cursor"),
                "search_id": position.get("search_id"),
                "pagination_invalide": bool(position.get("pagination_invalide")),
            }
        elif entree.get("statut_source") == "traitee":
            positions.pop(source, None)
    return positions


def exporter_bilan_hashtags_csv(bilan):
    """Produire un CSV UTF-8 réimportable, associé au corpus initial."""
    tampon = io.StringIO()
    writer = csv.DictWriter(tampon, fieldnames=COLONNES, delimiter=";",
                            extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    horodatage = datetime.now(timezone.utc).isoformat()
    for ligne in bilan:
        writer.writerow({**ligne, "exporte_le": (
            ligne.get("exporte_le") or horodatage)})
    return ("\ufeff" + tampon.getvalue()).encode("utf-8")


def identifier_collecte_bilan_hashtags_csv(contenu):
    """Identifier un corpus à rouvrir sans autoriser sa consultation par le CSV."""
    import re
    if not isinstance(contenu, bytes) or len(contenu) > 2_000_000:
        raise ValueError("Bilan hashtags invalide ou supérieur à 2 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        raise ValueError("Le CSV doit être encodé en UTF-8.") from erreur
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
    if not lecteur.fieldnames or not set(COLONNES_HISTORIQUES).issubset(lecteur.fieldnames):
        raise ValueError("Le fichier n'est pas un bilan hashtags ScrapTikTok.")
    identifiants = {
        str(ligne.get("collecte_id") or "").strip()
        for ligne in lecteur
    }
    if len(identifiants) != 1:
        raise ValueError("Le bilan doit appartenir à une seule collecte.")
    identifiant = next(iter(identifiants))
    if not re.fullmatch(r"[a-f0-9]{32}", identifiant):
        raise ValueError("Identifiant du corpus invalide.")
    return identifiant


def importer_bilan_hashtags_csv(contenu, *, collecte_id, hashtags_autorises):
    """Valider identité et statuts sans faire confiance à un CSV externe."""
    if not isinstance(contenu, bytes) or len(contenu) > 2_000_000:
        raise ValueError("Bilan hashtags invalide ou supérieur à 2 Mo.")
    try:
        texte = contenu.decode("utf-8-sig")
    except UnicodeDecodeError as erreur:
        raise ValueError("Le CSV doit être encodé en UTF-8.") from erreur
    lecteur = csv.DictReader(io.StringIO(texte), delimiter=";")
    if not lecteur.fieldnames or not set(COLONNES_HISTORIQUES).issubset(lecteur.fieldnames):
        raise ValueError("Le fichier n'est pas un bilan hashtags ScrapTikTok.")
    autorises = set(hashtags_autorises)
    vus, repris = set(), []
    for ligne in lecteur:
        if None in ligne:
            raise ValueError("Le bilan hashtags contient des colonnes supplémentaires.")
        tag = str(ligne.get("hashtag") or "").strip()
        etat = str(ligne.get("etat") or "").strip()
        identifiant = str(ligne.get("collecte_id") or "").strip()
        if identifiant != collecte_id:
            raise ValueError("Ce bilan appartient à une autre collecte PostgreSQL.")
        if tag not in autorises or tag in vus or etat not in ETATS_VALIDES:
            raise ValueError("Le bilan contient un hashtag ou un état invalide.")
        vus.add(tag)
        if etat in ETATS_REPRISE:
            repris.append(tag)
    if not vus:
        raise ValueError("Le bilan hashtags est vide.")
    return repris


def regrouper_bilans_hashtags_csv(contenus):
    """Classer les bilans par corpus sans mélanger les données ou curseurs."""
    fichiers = list(contenus)
    if not fichiers:
        raise ValueError("Sélectionnez au moins un bilan de hashtags CSV.")
    if len(fichiers) > 20:
        raise ValueError("Importez au maximum 20 bilans de hashtags à la fois.")
    if sum(len(fichier) for fichier in fichiers if isinstance(fichier, bytes)) > 10_000_000:
        raise ValueError("Le volume total des bilans ne doit pas dépasser 10 Mo.")
    groupes = {}
    for fichier in fichiers:
        identifiant = identifier_collecte_bilan_hashtags_csv(fichier)
        groupes.setdefault(identifiant, []).append(fichier)
    return groupes


def identifier_collecte_bilans_hashtags_csv(contenus):
    """Exiger un seul identifiant lorsque la reprise est sans sélection."""
    groupes = regrouper_bilans_hashtags_csv(contenus)
    if len(groupes) != 1:
        raise ValueError(
            "Les bilans importés appartiennent à des collectes différentes. "
            "Choisissez un corpus d'origine avant la reprise.")
    return next(iter(groupes))


def importer_bilans_hashtags_csv(contenus, *, collecte_id, hashtags_autorises):
    """Unir les hashtags inachevés de plusieurs bilans d'un même corpus.

    Le bilan historique sélectionne les hashtags ; seul le journal actuel
    détermine ensuite ceux qui restent effectivement à reprendre.
    """
    fichiers = list(contenus)
    identifiant = identifier_collecte_bilans_hashtags_csv(fichiers)
    if identifiant != collecte_id:
        raise ValueError(
            "Ces bilans appartiennent à une autre collecte PostgreSQL. "
            "Rouvrez d'abord cette collecte dans l'historique.")
    candidats = set()
    for fichier in fichiers:
        candidats.update(importer_bilan_hashtags_csv(
            fichier, collecte_id=collecte_id,
            hashtags_autorises=hashtags_autorises))
    return [tag for tag in dict.fromkeys(hashtags_autorises)
            if tag in candidats]


def positions_pagination_bilans_csv(
        contenus, *, collecte_id, hashtags_autorises,
        avec_accents=False, date_debut=None, date_fin=None):
    """Lire les curseurs sauvegardés dans les nouveaux bilans CSV.

    Chaque position est validée contre les variantes et la période originelles
    de la collecte PostgreSQL. Les anciens CSV à cinq colonnes restent valides,
    mais ne possèdent aucune position exacte.
    """
    from collecte.researchapi import _dates

    fichiers = list(contenus)
    if identifier_collecte_bilans_hashtags_csv(fichiers) != collecte_id:
        raise ValueError("Ces bilans ne correspondent pas au corpus d'origine.")
    if not date_debut or not date_fin:
        raise ValueError(
            "La période initiale doit être retrouvée avant de restaurer un curseur.")
    try:
        fin = date.fromisoformat(str(date_fin))
        periodes = list(_dates(date_debut, date_fin, aujourd_hui=fin))
    except (ValueError, TypeError) as erreur:
        raise ValueError("Période originale Research invalide.") from erreur
    graphies = variantes_par_hashtag(hashtags_autorises, avec_accents)
    positions = {}
    dates = {}

    for fichier in fichiers:
        lecteur = csv.DictReader(
            io.StringIO(fichier.decode("utf-8-sig")), delimiter=";")
        if not set(COLONNES_HISTORIQUES).issubset(lecteur.fieldnames or []):
            raise ValueError("Le CSV n'est pas un bilan hashtags ScrapTikTok.")
        for ligne in lecteur:
            hashtag = str(ligne.get("hashtag") or "").strip()
            etat = str(ligne.get("etat") or "").strip()
            if (hashtag not in graphies
                    or etat not in ETATS_REPRISE | {"en_cours"}):
                continue
            fenetre_debut = str(ligne.get("date_debut") or "").strip()
            fenetre_fin = str(ligne.get("date_fin") or "").strip()
            if ((fenetre_debut and fenetre_debut != date_debut)
                    or (fenetre_fin and fenetre_fin != date_fin)):
                raise ValueError(
                    "La période du bilan CSV diffère de la collecte PostgreSQL.")
            texte_json = str(ligne.get("positions_research_json") or "").strip()
            if texte_json:
                try:
                    candidates = json.loads(texte_json)
                except (TypeError, ValueError) as erreur:
                    raise ValueError(
                        "Positions Research JSON illisibles dans le bilan.") from erreur
                if not isinstance(candidates, dict):
                    raise ValueError("Positions Research du bilan invalides.")
            elif str(ligne.get("indice_periode") or "").strip():
                source = str(ligne.get("source_pagination") or "")
                candidates = {source: {
                    "indice_periode": ligne.get("indice_periode"),
                    "debut_periode": ligne.get("debut_periode"),
                    "fin_periode": ligne.get("fin_periode"),
                    "cursor": ligne.get("cursor"),
                    "search_id": ligne.get("search_id"),
                    "pagination_invalide": ligne.get("pagination_invalide"),
                }}
            else:
                continue
            # Export de référence : trier les versions chronologiquement,
            # plutôt que selon l'ordre des fichiers envoyés dans Streamlit.
            date_export = str(ligne.get("exporte_le") or "")
            if date_export:
                try:
                    horodatage = datetime.fromisoformat(
                        date_export.replace("Z", "+00:00"))
                    if horodatage.tzinfo is None:
                        horodatage = horodatage.replace(tzinfo=timezone.utc)
                    horodatage = horodatage.astimezone(timezone.utc)
                except ValueError as erreur:
                    raise ValueError(
                        "Horodatage d'export CSV invalide.") from erreur
            else:
                horodatage = datetime.min.replace(tzinfo=timezone.utc)
            autorisees = {"#" + graphie for graphie in graphies[hashtag]}
            for source, element in candidates.items():
                if source not in autorisees or not isinstance(element, dict):
                    raise ValueError(
                        "Le curseur CSV ne correspond pas à un hashtag autorisé.")
                try:
                    indice = int(element["indice_periode"])
                    curseur_brut = element.get("cursor")
                    curseur = (None if curseur_brut in ("", None)
                               else int(curseur_brut))
                except (ValueError, TypeError, KeyError) as erreur:
                    raise ValueError(
                        "Indice ou curseur Research invalide dans le CSV.") from erreur
                if (indice < 0 or indice >= len(periodes)
                        or curseur is not None and curseur < 0):
                    raise ValueError("Curseur Research hors de la pagination initiale.")
                debut_attendu, fin_attendue = periodes[indice]
                if (element.get("debut_periode") != debut_attendu
                        or element.get("fin_periode") != fin_attendue):
                    raise ValueError(
                        "La période du curseur ne correspond pas aux dates "
                        "initiales de la collecte.")
                recherche = element.get("search_id") or None
                if (curseur is not None
                        and (not isinstance(recherche, str) or not recherche)):
                    raise ValueError(
                        "Le curseur TikTok nécessite son search_id d'origine.")
                if recherche is not None and (
                        not isinstance(recherche, str) or len(recherche) > 1024):
                    raise ValueError("Identifiant de recherche Research invalide.")
                invalide = str(element.get("pagination_invalide") or "").lower()
                if invalide in ("1", "true"):
                    raise ValueError(
                        "Le bilan contient une pagination TikTok signalée invalide.")
                position = {
                    "indice_periode": indice,
                    "debut_periode": debut_attendu,
                    "fin_periode": fin_attendue,
                    "cursor": curseur,
                    "search_id": recherche,
                    "pagination_invalide": False,
                }
                if (source in dates and horodatage == dates[source]
                        and positions[source] != position):
                    raise ValueError(
                        "Deux bilans portent des curseurs divergents sans "
                        "horodatage permettant de les départager.")
                if source not in dates or horodatage >= dates[source]:
                    positions[source] = position
                    dates[source] = horodatage
    return positions
