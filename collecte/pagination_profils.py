"""Défilement progressif de la grille publique d'un profil TikTok."""
from selenium.common.exceptions import WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin


ETAT_GRILLE_JS = """
const compte = arguments[0].toLowerCase();
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
const liens = Array.from(document.querySelectorAll('a[href*="/video/"],a[href*="/photo/"]'))
    .filter(e => {
        const chemin = new URL(e.href).pathname.split('/');
        return decodeURIComponent(chemin[1] || '').toLowerCase() === '@' + compte && visible(e);
    });
const grille = Array.from(document.querySelectorAll('[data-e2e="user-post-item-list"]'))
    .find(visible);
let conteneur = null;
for (let e = grille || liens[0]; e; e = e.parentElement) {
    const style = getComputedStyle(e);
    if (/auto|scroll|overlay/.test(style.overflowY) && e.scrollHeight > e.clientHeight + 2) {
        conteneur = e;
        break;
    }
}
conteneur = conteneur || document.scrollingElement || document.documentElement;
const page = conteneur === document.scrollingElement || conteneur === document.documentElement;
const cadre = page ? {left:0, top:0, right:innerWidth, bottom:innerHeight}
    : conteneur.getBoundingClientRect();
// Placer la molette sur la grille, pas sur le menu latéral de TikTok.
// La première vignette peut rester visible alors que la suite de la grille
// se trouve plus bas. Utiliser la DERNIÈRE vignette à l'écran pour déclencher
// réellement le défilement du profil plutôt que de la bannière supérieure.
const ancre = liens.filter(e => {
    const r = e.getBoundingClientRect();
    return r.bottom > Math.max(0, cadre.top) && r.top < Math.min(innerHeight, cadre.bottom)
        && r.right > 0 && r.left < innerWidth;
}).at(-1) || liens.at(-1);
const zone = ancre ? ancre.getBoundingClientRect() : cadre;
const gauche = Math.max(0, cadre.left, zone.left);
const droite = Math.min(innerWidth, cadre.right, zone.right);
const haut = Math.max(0, cadre.top, zone.top);
const bas = Math.min(innerHeight, cadre.bottom, zone.bottom);
return {element:conteneur, x:Math.max(1, Math.min(innerWidth-2, Math.floor((gauche+droite)/2))),
    y:Math.max(1, Math.min(innerHeight-2, Math.floor((haut+bas)/2))),
    position:Math.round(conteneur.scrollTop), hauteur:conteneur.scrollHeight,
    fenetre:conteneur.clientHeight, liens_visibles:liens.length,
    fin:conteneur.scrollTop+conteneur.clientHeight >= conteneur.scrollHeight-4};
"""


RECUPERATION_DEFILEMENT_JS = """
// Utiliser la vraie grille publique et non l'en-tête figé du profil.
// Un scrollIntoView du dernier élément visible peut déclencher le chargement
// progressif que la molette seule ne provoque pas dans certains conteneurs.
const compte = arguments[0].toLowerCase();
const conteneur = arguments[1];
const pas = arguments[2];
const liens = Array.from(document.querySelectorAll('a[href*="/video/"],a[href*="/photo/"]'))
    .filter(e => {
        try { return decodeURIComponent(new URL(e.href).pathname.split('/')[1]).toLowerCase() === '@'+compte; }
        catch (_) { return false; }
    });
const dernier = liens.at(-1);
if (dernier) dernier.scrollIntoView({block:'end',inline:'nearest',behavior:'instant'});
if (conteneur && conteneur !== document.documentElement && conteneur !== document.body
        && conteneur !== document.scrollingElement
        && conteneur.scrollHeight > conteneur.clientHeight + 2) {
    conteneur.scrollBy(0,pas);
} else {
    window.scrollBy(0,pas);
}
return {liens:liens.length, ancre_presente:!!dernier};
"""


def etat_grille_profil(navigateur, compte):
    """Relever la position réelle du conteneur des publications."""
    return navigateur.execute_script(ETAT_GRILLE_JS, compte)


def defiler_grille_profil(navigateur, compte, *, reprendre=False, check=None):
    """Faire défiler par écran ; réexposer la fin de grille après une attente vide."""
    check = check or (lambda: None)
    check()
    avant = etat_grille_profil(navigateur, compte)
    pas = max(120, min(700, int(avant["fenetre"] * 0.7)))
    methode = "molette"
    try:
        origine = ScrollOrigin.from_viewport(avant["x"], avant["y"])
        gestes = ActionChains(navigateur)
        if reprendre:
            # Sortir le bas de grille du viewport, puis le réexposer : un simple
            # scrollTo sur une position déjà atteinte ne produit aucun défilement.
            gestes.scroll_from_origin(origine, 0, -pas).pause(0.3)
        gestes.scroll_from_origin(origine, 0, pas * (2 if reprendre else 1)).pause(0.2).perform()
    except WebDriverException:
        check()
        methode = "defilement_conteneur"
        navigateur.execute_script("arguments[0].scrollBy(0, arguments[1]);", avant["element"], pas)
    check()
    apres = etat_grille_profil(navigateur, compte)
    # TikTok peut immobiliser la première grille de 6 vignettes. En l'absence
    # de déplacement effectif, tenter le scroll DOM ordinaire de la dernière
    # carte rendue ; aucune requête TikTok artificielle n'est rejouée.
    recours = False
    if (apres["position"] <= avant["position"] + 2
            and apres["hauteur"] <= avant["hauteur"] + 2
            and apres["liens_visibles"] <= avant["liens_visibles"]):
        check()
        navigateur.execute_script(RECUPERATION_DEFILEMENT_JS, compte, avant["element"], pas)
        recours = True
        methode += "+fin_grille"
        check()
        apres = etat_grille_profil(navigateur, compte)
    champs = ("position", "hauteur", "fenetre", "liens_visibles", "fin")
    return {"avant": {c: avant[c] for c in champs},
            "apres": {c: apres[c] for c in champs},
            "methode": methode, "relance": reprendre, "recours": recours}
