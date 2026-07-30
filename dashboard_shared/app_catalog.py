from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS_ROOT = REPO_ROOT / "applications"

FILE_PRIORITY = (
    "Dockerfile",
    "DEPLOIEMENT_OVH_COOLIFY.md",
    "README.md",
    "main.py",
    "app.py",
    "app_runtime.py",
    "app.R",
    "webapp/ticket_gate.py",
)
RUNTIME_FILES = ("main.py", "app.py", "app_runtime.py", "app.R")
FAMILIES = (
    {"id": "extraire", "label": "Extraire", "order": 10},
    {"id": "calculer", "label": "Calculer", "order": 20},
    {"id": "multimodale", "label": "Multimodale", "order": 30},
)
FAMILY_LABELS = {item["id"]: item["label"] for item in FAMILIES}
FAMILY_ORDER = {item["id"]: item["order"] for item in FAMILIES}

# Les champs de presentation restent ici. Les donnees tickets
# (label/max_active/cost) viennent des applications et/ou des overrides
# d'environnement lus par le dashboard.
UI_OVERRIDES: dict[str, dict[str, Any]] = {
    "europresse-to-iramuteq": {
        "href": "https://europresse.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-file-export",
        "description": "Conversion d’exports Europresse vers un corpus compatible avec IRaMuTeQ.",
        "order": 10,
        "visible": True,
    },
    "extraction-multimedia": {
        "href": "https://multimedia.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-photo-film",
        "description": "Pour extraire des fichiers images, mp4, mp3 depuis une vidéo YouTube.",
        "order": 20,
        "visible": True,
    },
    "stopmotion_opticalflow": {
        "href": "https://stopmotion.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-photo-film",
        "description": "Extraction et génération stopmotion.",
        "order": 30,
        "visible": True,
    },
    "extract_comments_youtube": {
        "href": "https://extractcommentyoutube.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-file-export",
        "description": "Extraire les commentaires YouTube avec clé API Google obligatoire.",
        "order": 40,
        "visible": True,
    },
    "scraping_reddit": {
        "href": "https://scrapingreddit.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-diagram-project",
        "description": "Scraper les posts Reddit.",
        "order": 50,
        "visible": True,
    },
    "Extraction_infos_YouTube": {
        "href": "https://infosyoutube.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-diagram-project",
        "description": "Scraper les informations d’une chaîne YouTube.",
        "order": 60,
        "visible": True,
    },
    "mp3_to_text": {
        "href": "https://speechtotext.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-file-export",
        "description": "Conversion de fichier mp3 en texte avec Whisper.",
        "order": 70,
        "visible": True,
    },
    "pdf-to-text-to-iramuteq": {
        "href": "https://pdftotext.codeandcortex.fr",
        "familyId": "extraire",
        "iconClass": "fas fa-file-pdf",
        "description": "Convertir un ou plusieurs PDF en texte nettoyé compatible avec IRaMuTeQ.",
        "order": 80,
        "visible": True,
    },
    "cooccurrencesmotpivot": {
        "href": "https://cooccurrences.codeandcortex.fr",
        "familyId": "calculer",
        "iconClass": "fas fa-chart-pie",
        "description": "Analyse de cooccurrences centrée sur un mot pivot.",
        "order": 100,
        "visible": True,
    },
    "chdrainette": {
        "href": "http://chdrainette.codeandcortex.fr",
        "familyId": "calculer",
        "iconClass": "fas fa-chart-pie",
        "description": "Classification descendante hiérarchique Rainette.",
        "order": 110,
        "visible": True,
    },
    "divergence-jensen-shannon": {
        "href": "https://djs.codeandcortex.fr",
        "familyId": "calculer",
        "iconClass": "fas fa-chart-pie",
        "description": "Comparer deux distributions textuelles avec la divergence de Jensen-Shannon.",
        "order": 120,
        "visible": True,
    },
    "symbolic_connectors": {
        "href": "https://connectors.codeandcortex.fr",
        "familyId": "calculer",
        "iconClass": "fas fa-diagram-project",
        "description": "Détection et analyse de connecteurs symboliques.",
        "order": 130,
        "visible": True,
    },
    "iramuteq-lite": {
        "href": "https://iramuteqlite.codeandcortex.fr",
        "familyId": "calculer",
        "iconClass": "fas fa-chart-pie",
        "description": "Analyse textuelle IRaMuTeQ Lite dans le navigateur.",
        "order": 140,
        "visible": True,
    },
    "vecteur-emotionnel": {
        "href": "https://vecteuremotionnel.codeandcortex.fr",
        "familyId": "multimodale",
        "iconClass": "fas fa-chart-pie",
        "description": "Mesure et visualisation du vecteur émotionnel.",
        "order": 150,
        "visible": True,
    },
    "rendreaudible": {
        "href": "http://rendreaudible.codeandcortex.fr",
        "familyId": "multimodale",
        "iconClass": "fas fa-wave-square",
        "description": "Analyse de l’amplitude sonore dans un discours.",
        "order": 160,
        "visible": True,
    },
    "analyse_debit_parole": {
        "href": "https://debitparole.codeandcortex.fr",
        "familyId": "multimodale",
        "iconClass": "fas fa-gauge-high",
        "description": "Mesurer le débit de parole d’un discours.",
        "order": 170,
        "visible": True,
    },
    "Analyses_multi_modales": {
        "href": "https://multimodales.codeandcortex.fr",
        "familyId": "multimodale",
        "iconClass": "fas fa-chart-pie",
        "description": "Analyse multimodale de la temporalité à partir de texte, audio et images.",
        "order": 180,
        "visible": True,
    },
    "lda": {
        "familyId": "calculer",
        "iconClass": "fas fa-chart-pie",
        "description": "Analyse discriminante linéaire (LDA).",
        "order": 220,
        "visible": False,
    },
    "kmeans": {
        "familyId": "calculer",
        "iconClass": "fas fa-chart-pie",
        "description": "Classification KMeans.",
        "order": 230,
        "visible": False,
    },
    "Analyse_MM": {
        "familyId": "multimodale",
        "iconClass": "fas fa-photo-film",
        "description": "Préparation vidéo, extraction, transcription, anomalies et analyses multimodales.",
        "order": 240,
        "visible": False,
    },
}

STATIC_ENTRIES: tuple[dict[str, Any], ...] = (
    {
        "entryId": "detectia-placeholder",
        "label": "Détection IA",
        "description": "Repérer des indices de vidéo générée par IA à partir de mesures temporelles.",
        "familyId": "extraire",
        "iconClass": "fas fa-eye",
        "order": 35,
        "disabled": True,
        "ticketed": False,
        "statusLabel": "En construction",
        "metaText": "Application en préparation",
    },
    {
        "entryId": "scraper-wikipedia-static",
        "label": "Scraper Wikipedia",
        "description": "Scraper Wikipedia",
        "familyId": "extraire",
        "iconClass": "fas fa-file-export",
        "order": 90,
        "disabled": False,
        "ticketed": False,
        "href": "https://wikipedia.codeandcortex.fr",
        "statusLabel": "Libre",
        "metaText": "Scraper Wikipedia",
    },
    {
        "entryId": "analyse-mm-placeholder",
        "label": "Analyse MM",
        "description": "Préparation vidéo, extraction, transcription, anomalies et analyses multimodales.",
        "familyId": "multimodale",
        "iconClass": "fas fa-photo-film",
        "order": 190,
        "disabled": True,
        "ticketed": False,
        "statusLabel": "En construction",
        "metaText": "Application en préparation",
    },
)

CALL_PATTERNS = (
    re.compile(r'enforce_streamlit_access\(\s*(["\'])(?P<app>.*?)\1\s*,\s*(["\'])(?P<label>.*?)\3'),
    re.compile(r'ticket_config\(\s*(["\'])(?P<app>.*?)\1\s*,\s*(["\'])(?P<label>.*?)\3'),
)
DEFAULT_APP_LABEL_PATTERN = re.compile(r'app_label:\s*str\s*=\s*(["\'])(?P<label>.*?)\1')
VARIABLE_CALL_PATTERNS = (
    re.compile(r'enforce_streamlit_access\(\s*(?:"(?P<app_dq>[^"]+)"|\'(?P<app_sq>[^\']+)\'|[A-Z0-9_]+)\s*,\s*(?P<var>[A-Z][A-Z0-9_]*)\s*\)'),
    re.compile(r'ticket_config\(\s*(?:"(?P<app_dq>[^"]+)"|\'(?P<app_sq>[^\']+)\'|[A-Z0-9_]+)\s*,\s*(?P<var>[A-Z][A-Z0-9_]*)\s*\)'),
)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _candidate_texts(app_dir: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for filename in FILE_PRIORITY:
        path = app_dir / filename
        if path.exists():
            texts[filename] = _read_text(path)
    return texts


def _extract_simple_assignments(text: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    patterns = (
        re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s*=\s*(["\'])(.*?)\2', re.MULTILINE),
        re.compile(r'^\s*([A-Z][A-Z0-9_]*)\s*<-\s*(["\'])(.*?)\2', re.MULTILINE),
    )
    for pattern in patterns:
        for name, _quote, value in pattern.findall(text):
            assignments[name] = value.strip()
    return assignments


def _extract_setting(texts: dict[str, str], name: str) -> str | None:
    pattern = re.compile(rf"{re.escape(name)}\s*=\s*([A-Za-z0-9_\-]+)")
    for filename in FILE_PRIORITY:
        text = texts.get(filename)
        if not text:
            continue
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
    return None


def _extract_int_setting(texts: dict[str, str], name: str, default: int) -> int:
    raw = _extract_setting(texts, name)
    if raw is None:
        return default
    try:
        return max(0, int(raw))
    except ValueError:
        return default


def _humanize_identifier(value: str) -> str:
    cleaned = re.sub(r"[_\-]+", " ", value).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return value
    return cleaned[:1].upper() + cleaned[1:]


def _extract_markdown_heading(texts: dict[str, str]) -> str | None:
    readme = texts.get("README.md", "")
    for line in readme.splitlines():
        cleaned = line.strip()
        if not cleaned.startswith("#"):
            continue
        heading = cleaned.lstrip("#").strip()
        if heading:
            return heading
    return None


def _extract_label(texts: dict[str, str], app_id: str, folder_name: str) -> str:
    runtime_assignments: dict[str, str] = {}

    for filename in RUNTIME_FILES:
        text = texts.get(filename)
        if not text:
            continue
        runtime_assignments.update(_extract_simple_assignments(text))

        for pattern in CALL_PATTERNS:
            for match in pattern.finditer(text):
                if match.group("app").strip() == app_id:
                    return match.group("label").strip()

        for pattern in VARIABLE_CALL_PATTERNS:
            for match in pattern.finditer(text):
                app_arg = (match.group("app_dq") or match.group("app_sq") or "").strip()
                if app_arg and app_arg != app_id:
                    continue
                variable_name = match.group("var").strip()
                if variable_name in runtime_assignments:
                    return runtime_assignments[variable_name]

    for variable_name in ("APP_DISPLAY_NAME", "APP_LABEL", "APP_NAME"):
        if variable_name in runtime_assignments:
            return runtime_assignments[variable_name]

    for filename in FILE_PRIORITY:
        text = texts.get(filename)
        if not text:
            continue
        match = DEFAULT_APP_LABEL_PATTERN.search(text)
        if match:
            return match.group("label").strip()

    markdown_heading = _extract_markdown_heading(texts)
    if markdown_heading:
        return markdown_heading

    return _humanize_identifier(app_id or folder_name)


def _looks_ticketed(texts: dict[str, str]) -> bool:
    markers = ("APP_TICKET_ID", "enforce_streamlit_access(", "ticket_config(", "ticket_gate.py", "ticket_gate_cli.py")
    return any(any(marker in text for marker in markers) for text in texts.values())


def _discover_ticket_app(app_dir: Path) -> dict[str, Any] | None:
    texts = _candidate_texts(app_dir)
    if not texts:
        return None

    app_id = _extract_setting(texts, "APP_TICKET_ID")
    if not app_id and not _looks_ticketed(texts):
        return None

    if not app_id:
        app_id = app_dir.name

    return {
        "application_id": app_id,
        "label": _extract_label(texts, app_id, app_dir.name),
        "max_active": max(1, _extract_int_setting(texts, "APP_TICKET_MAX_ACTIVE", 1)),
        "cout": _extract_int_setting(texts, "APP_TICKET_COST", 1),
        "folder": app_dir.name,
        "source": str((app_dir / "Dockerfile") if (app_dir / "Dockerfile").exists() else app_dir),
    }


@lru_cache(maxsize=1)
def load_ticket_app_defaults() -> dict[str, dict[str, Any]]:
    applications: dict[str, dict[str, Any]] = {}
    if not APPLICATIONS_ROOT.exists():
        return applications

    for app_dir in sorted(path for path in APPLICATIONS_ROOT.iterdir() if path.is_dir()):
        metadata = _discover_ticket_app(app_dir)
        if metadata is None:
            continue
        applications[metadata["application_id"]] = metadata
    return applications


def build_dashboard_entries(include_hidden: bool = False) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []

    for app_id, meta in load_ticket_app_defaults().items():
        ui = UI_OVERRIDES.get(app_id, {})
        visible = bool(ui.get("visible", False))
        if not include_hidden and not visible:
            continue

        family_id = str(ui.get("familyId", "calculer"))
        entry = {
            "entryId": app_id,
            "appId": app_id,
            "label": meta["label"],
            "description": str(ui.get("description", "")),
            "href": ui.get("href"),
            "iconClass": str(ui.get("iconClass", "fas fa-cube")),
            "familyId": family_id,
            "familyLabel": FAMILY_LABELS.get(family_id, family_id.title()),
            "familyOrder": FAMILY_ORDER.get(family_id, 999),
            "order": int(ui.get("order", 999)),
            "visible": visible,
            "ticketed": True,
            "disabled": bool(ui.get("disabled", False)),
            "defaultMaxActive": int(meta["max_active"]),
            "defaultCost": int(meta["cout"]),
            "defaultMetaText": f"0 / {int(meta['max_active'])} actif · 0 attente",
        }
        entries.append(entry)

    if include_hidden:
        return sorted(entries, key=lambda item: (item["familyOrder"], item["order"], item["label"]))

    for item in STATIC_ENTRIES:
        family_id = str(item.get("familyId", "calculer"))
        entries.append(
            {
                "entryId": item["entryId"],
                "appId": item.get("appId"),
                "label": item["label"],
                "description": item["description"],
                "href": item.get("href"),
                "iconClass": item["iconClass"],
                "familyId": family_id,
                "familyLabel": FAMILY_LABELS.get(family_id, family_id.title()),
                "familyOrder": FAMILY_ORDER.get(family_id, 999),
                "order": int(item["order"]),
                "visible": True,
                "ticketed": bool(item.get("ticketed", False)),
                "disabled": bool(item.get("disabled", False)),
                "statusLabel": item.get("statusLabel", "Libre"),
                "metaText": item.get("metaText", ""),
            }
        )

    return sorted(entries, key=lambda item: (item["familyOrder"], item["order"], item["label"]))
