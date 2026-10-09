"""Segments transcrits reliés à leur publication, sans réécriture."""
def construire_transcriptions(resultats, variables=None):
    return [{"id": identifiant, "texte": " ".join(s["texte"] for s in r.get("segments", [])),
        "variables": {**(variables or {}).get(identifiant,{}), "type": "transcription", "langue": r.get("langue")}} for identifiant, r in resultats.items()]
