# dictionnaire.py
# Listes extensibles d'expressions (insensibles à la casse, appariement exact)
# Toutes les variables sont en minuscules, alignées avec main.py.

deictiques_proches = {
    "maintenant", "aujourd'hui", "tout de suite", "immédiatement", "à l'instant",
    "ici", "ce soir", "ce matin", "tout à l'heure", "bientôt",
    "actuellement", "à présent", "dès maintenant"
}

deictiques_eloignes = {
    "demain", "après-demain", "la semaine prochaine", "le mois prochain",
    "dans l'avenir", "ultérieurement", "à long terme", "à moyen terme",
    "plus tard", "prochainement"
}

deictiques_passes = {
    "hier", "avant-hier", "la semaine dernière", "le mois dernier",
    "autrefois", "jadis", "auparavant", "précédemment", "il y a"
}

# Catégorie supplémentaire demandée et utilisée par main.py
deictiques_plannificateur = {
    "à court terme", "dans l'immédiat", "pour l'instant", "dès que possible",
    "dans les prochains jours", "dans l'instant", "immédiatement après",
    "tout de suite après", "sans délai"
}

marqueurs_planification = {
    "plan", "programme", "feuille de route", "calendrier", "échéance",
    "stratégie", "projection", "objectif", "objectifs", "priorités", "agenda",
    "réforme", "réformes", "projet", "projets", "roadmap", "appel"
}

connecteurs_causaux = {
    "parce que", "car", "donc", "ainsi", "de sorte que", "afin de", "de manière à",
    "si", "alors", "par conséquent", "en conséquence"
}

