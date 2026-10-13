"""Validation des formulaires et canonicalisation sans requête réseau."""

import ipaddress
import re
import unicodedata
from datetime import date as DatePublication
from typing import Annotated, Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator

NATURES = {
    "thematique": "Thématique",
    "discours": "Type de discours",
    "qualification": "Qualification factuelle",
    "categorie": "Catégorie",
    "mot_cle": "Mot-clé",
}
MEDIAS = {
    "video": "Vidéo",
    "article": "Article",
    "publication": "Publication",
    "podcast": "Podcast",
    "audio": "Audio / radio",
    "pdf": "Document PDF",
    "autre": "Autre",
}
ENTITES = {"source": "Source", "compte": "Compte", "contenu": "Contenu", "tag": "Tag"}
PLATEFORMES = [
    "YouTube",
    "TikTok",
    "Facebook",
    "Instagram",
    "X",
    "Telegram",
    "Rumble",
    "Odysee",
    "Site Internet",
    "Blog",
    "Forum",
    "Podcast",
    "Radio",
    "Document PDF",
]


def cle_texte(valeur: str) -> str:
    return unicodedata.normalize("NFKC", valeur).strip().casefold()


def valider_url(valeur: str) -> str:
    valeur = valeur.strip()
    if len(valeur) > 2048 or re.search(r"[\x00-\x20\x7f\\]", valeur):
        raise ValueError("URL trop longue ou contenant des caractères interdits.")
    try:
        url = urlsplit(valeur)
        hote = (url.hostname or "").encode("idna").decode().lower()
        port = url.port
    except (ValueError, UnicodeError):
        raise ValueError("URL invalide.") from None
    if (
        url.scheme not in {"https", "http"}
        or not hote
        or url.username is not None
        or url.password is not None
    ):
        raise ValueError("Indiquer une URL publique HTTP(S), sans identifiant ni mot de passe.")
    if port is not None and port not in {80, 443}:
        raise ValueError("Seuls les ports web 80 et 443 sont acceptés.")
    try:
        adresse = ipaddress.ip_address(hote)
    except ValueError:
        if (
            "." not in hote
            or hote.endswith((".local", ".localhost", ".internal", ".test"))
            or not re.fullmatch(r"[a-z0-9-]+(?:\.[a-z0-9-]+)+", hote)
            or hote.replace(".", "").isdigit()
        ):
            raise ValueError("Utiliser un domaine public valide.")
    else:
        if not adresse.is_global:
            raise ValueError("Les adresses locales ou privées ne sont pas acceptées.")
    return valeur


def canonicaliser_url(valeur: str) -> str:
    url = urlsplit(valider_url(valeur))
    hote = url.hostname.encode("idna").decode().lower()
    params = [
        (k, v)
        for k, v in parse_qsl(url.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    ]
    # L'URL originale reste intacte ; seules les clés de dédoublonnage sont normalisées.
    if hote in {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtu.be"}:
        video = None
        if hote.endswith("youtu.be"):
            video = url.path.strip("/")
        elif url.path == "/watch":
            video = dict(params).get("v")
        elif url.path.startswith(("/shorts/", "/embed/", "/live/")):
            video = url.path.split("/")[2]
        if video and re.fullmatch(r"[A-Za-z0-9_-]{11}", video):
            return f"https://www.youtube.com/watch?v={video}"
    if ":" in hote:
        hote = f"[{hote}]"
    if url.port and url.port != {"http": 80, "https": 443}[url.scheme]:
        hote += f":{url.port}"
    return urlunsplit((url.scheme, hote, url.path or "/", urlencode(params), ""))


TexteCourt = Annotated[str, Field(min_length=1, max_length=300)]
Identifiant = Annotated[int, Field(gt=0)]


class Saisie(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ReferenceSaisie(Saisie):
    titre: Annotated[str, Field(min_length=1, max_length=500)]
    url: str
    type_reference: Literal["article", "scientifique", "fact_checking", "autre"] = "article"
    citation: Annotated[str, Field(max_length=5000)] = ""
    qualification_tag_id: Identifiant | None = None
    _url = field_validator("url")(valider_url)


class DocumentSaisie(Saisie):
    references: list[ReferenceSaisie] = Field(default_factory=list, max_length=30)


class SourceSaisie(DocumentSaisie):
    nom: TexteCourt
    description: Annotated[str, Field(max_length=10000)] = ""
    url: str
    pays: Annotated[str, Field(max_length=100)] = ""
    langue: Annotated[str, Field(max_length=100)] = ""
    plateforme_id: Identifiant
    tags: list[Identifiant] = Field(default_factory=list, max_length=50)
    _url = field_validator("url")(valider_url)


class CompteSaisie(DocumentSaisie):
    pseudonyme: TexteCourt
    identifiant: Annotated[str, Field(max_length=300)] = ""
    url: str
    plateforme_id: Identifiant
    source_id: Identifiant
    _url = field_validator("url")(valider_url)


class ContenuSaisie(DocumentSaisie):
    titre: TexteCourt
    url: str
    date: DatePublication | None = None
    description: Annotated[str, Field(max_length=10000)] = ""
    type_media: Literal["video", "article", "publication", "podcast", "audio", "pdf", "autre"]
    source_id: Identifiant
    compte_id: Identifiant | None = None
    plateforme_id: Identifiant
    tags: list[Identifiant] = Field(default_factory=list, max_length=50)
    _url = field_validator("url")(valider_url)


class TagSaisie(DocumentSaisie):
    nom: Annotated[str, Field(min_length=1, max_length=150)]
    nature: Literal["thematique", "discours", "qualification", "categorie", "mot_cle"]
    description: Annotated[str, Field(max_length=10000)] = ""
    parent_id: Identifiant | None = None


SAISIES = {"source": SourceSaisie, "compte": CompteSaisie, "contenu": ContenuSaisie, "tag": TagSaisie}


class Filtres(Saisie):
    texte: Annotated[str, Field(max_length=300)] = ""
    url: Annotated[str, Field(max_length=2048)] = ""
    plateforme_id: Identifiant | None = None
    type_media: Literal["video", "article", "publication", "podcast", "audio", "pdf", "autre"] | None = None
    tags: list[Identifiant] = Field(default_factory=list, max_length=50)
    thematique_id: Identifiant | None = None
    operateur: Literal["ET", "OU"] = "ET"
    descendants: bool = True
    pays: Annotated[str, Field(max_length=100)] = ""
    langue: Annotated[str, Field(max_length=100)] = ""
    date_debut: DatePublication | None = None
    date_fin: DatePublication | None = None
    source_id: Identifiant | None = None
    compte_id: Identifiant | None = None
