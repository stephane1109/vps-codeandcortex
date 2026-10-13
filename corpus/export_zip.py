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


def archive_avec_texte(chemin, contenu_txt):
    """Adapter uniquement les deux TXT principaux pour ce téléchargement."""
    from shutil import copyfileobj
    from tempfile import SpooledTemporaryFile
    # Au-delà de 8 Mio, utiliser un fichier temporaire pour ménager la mémoire du VPS.
    flux = SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")
    try:
        with ZipFile(chemin, "r") as source, ZipFile(flux, "w", ZIP_DEFLATED) as cible:
            for entree in source.infolist():
                if entree.filename in {"textes.txt", "corpus_iramuteq.txt"}:
                    continue
                with source.open(entree) as lecture, cible.open(entree, "w") as ecriture:
                    copyfileobj(lecture, ecriture, length=1024 * 1024)
            for nom in ("textes.txt", "corpus_iramuteq.txt"):
                cible.writestr(nom, contenu_txt)
        flux.seek(0)
        return flux
    except Exception:
        flux.close()
        raise
