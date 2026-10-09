"""Archive des exports ; profils navigateur et base globale exclus."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

def exporter_zip(dossier, destination, inclure_medias=False):
    dossier = Path(dossier).resolve(); destination = Path(destination).resolve()
    temporaire = destination.with_suffix(".zip.tmp")
    with ZipFile(temporaire, "w", ZIP_DEFLATED) as archive:
        for chemin in sorted(dossier.rglob("*")):
            if not chemin.is_file() or chemin.is_symlink() or chemin.resolve() in {destination, temporaire}: continue
            relatif = chemin.relative_to(dossier)
            if not inclure_medias and relatif.parts[0] in {"videos", "images", "audio"}: continue
            if chemin.suffix not in {".txt", ".csv", ".json", ".mp4", ".jpg", ".wav"}: continue
            archive.write(chemin, relatif.as_posix())
    temporaire.replace(destination)
    return destination
