from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STAGE_PLANS: dict[str, list[dict[str, Any]]] = {
    "mouvements": [
        {"key": "prepare_source", "label": "Préparation de la source"},
        {"key": "normalise_source", "label": "Normalisation de la source"},
        {"key": "open_video", "label": "Ouverture et échantillonnage"},
        {"key": "analyse_flux", "label": "Calcul de l'optical flow"},
        {"key": "aggregate_windows", "label": "Agrégation des fenêtres"},
        {"key": "write_exports", "label": "Écriture des exports"},
        {"key": "completed", "label": "Analyse terminée"},
    ]
}


def write_progress_snapshot(
    output_dir: str | Path,
    analysis_key: str,
    stage_key: str,
    progress: int,
    message: str,
    extra: dict[str, Any] | None = None,
) -> str:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    payload = {
        "analysis": analysis_key,
        "stage": stage_key,
        "progress": max(0, min(100, int(progress))),
        "message": message,
        "stages": STAGE_PLANS.get(analysis_key, []),
        "extra": extra or {},
    }
    progress_path = destination / f"progression_{analysis_key}.json"
    progress_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(progress_path)
