from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import altair as alt
except ImportError:  # pragma: no cover - dépendance externe
    alt = None


def altair_available() -> bool:
    return alt is not None


def save_chart(chart: Any, output_path: str | Path) -> str:
    if alt is None:
        raise RuntimeError("Altair est requis pour exporter les graphiques multimodaux.")

    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        if destination.suffix.lower() == ".png":
            chart.save(str(destination), scale_factor=3)
        else:
            chart.save(str(destination))
    except Exception as exc:  # pragma: no cover - dépendance externe
        if destination.suffix.lower() == ".png":
            raise RuntimeError(
                "Export Altair PNG impossible. Installez `vl-convert-python` pour générer les PNG multimodaux."
            ) from exc
        raise
    return str(destination)


def configure_chart(chart: Any, title: str) -> Any:
    if alt is None:
        return chart

    return (
        chart.properties(title=title)
        .configure_view(stroke=None)
        .configure_axis(
            labelFontSize=12,
            titleFontSize=13,
            gridColor="#e8ddd4",
            domainColor="#8a6e5a",
            tickColor="#8a6e5a",
        )
        .configure_title(
            fontSize=16,
            color="#512b1f",
            anchor="start",
        )
        .configure_legend(
            labelFontSize=12,
            titleFontSize=12,
        )
    )
