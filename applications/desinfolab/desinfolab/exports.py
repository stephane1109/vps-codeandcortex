"""Exports de corpus, complets et protégés contre les formules de tableur."""

import csv
import io
import json

MIMES = {"txt": "text/plain", "csv": "text/csv", "json": "application/json"}
COLONNES = [
    "id",
    "entite",
    "nom",
    "titre",
    "pseudonyme",
    "identifiant",
    "url",
    "date",
    "description",
    "type_media",
    "plateforme",
    "plateforme_id",
    "source_id",
    "source",
    "compte_id",
    "pays",
    "langue",
    "tags",
    "qualifications",
    "references",
    "version",
    "cree_le",
    "modifie_le",
]


def cellule_csv(valeur):
    if isinstance(valeur, (list, dict)):
        valeur = json.dumps(valeur, ensure_ascii=False)
    if valeur is None:
        return ""
    texte = str(valeur)
    if texte.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "\n")) or texte.startswith(
        ("\t", "\r", "\n")
    ):
        texte = "'" + texte
    return texte


def exporter_lignes(resultats, format_export):
    """Générer des fragments UTF-8, utilisables directement par une réponse HTTP."""
    if format_export == "txt":
        for r in resultats:
            if r.get("url"):
                yield r["url"] + "\n"
    elif format_export == "json":
        yield "[\n"
        premier = True
        for r in resultats:
            if not premier:
                yield ",\n"
            yield json.dumps(r, ensure_ascii=False)
            premier = False
        yield "\n]\n"
    elif format_export == "csv":
        tampon = io.StringIO(newline="")
        writer = csv.DictWriter(tampon, fieldnames=COLONNES, extrasaction="ignore")
        writer.writeheader()
        yield "\ufeff" + tampon.getvalue()
        for r in resultats:
            tampon.seek(0)
            tampon.truncate(0)
            writer.writerow({k: cellule_csv(v) for k, v in r.items()})
            yield tampon.getvalue()
    else:
        raise ValueError("Format inconnu : choisir txt, csv ou json.")


def exporter(resultats, format_export):
    return "".join(exporter_lignes(resultats, format_export)).encode("utf-8")
