"""Défilement de la grille de recherche, y compris les conteneurs imbriqués."""
import time
from selenium.common.exceptions import WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.actions.wheel_input import ScrollOrigin


ETAT_RECHERCHE_JS = """
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
// Partir des résultats, quels que soient leurs auteurs, jamais du menu latéral.
const racine = document.querySelector('[data-e2e="search-video-container"]') || document.querySelector('main');
const lister = zone => Array.from(zone.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]')).filter(visible);
const locaux = racine ? lister(racine) : [];
const liens = locaux.length ? locaux : lister(document);
// Le premier résultat demeure souvent visible quand la suite de la recherche
// est affichée plus bas. S'ancrer sur le DERNIER résultat visible pour faire
// défiler le conteneur de la liste, et non son bandeau supérieur.
const ancre = liens.filter(e => {
    const r = e.getBoundingClientRect();
    return r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
}).at(-1) || liens.at(-1) || racine;
let conteneur = null;
for (let e = ancre; e; e = e.parentElement) {
    if (/auto|scroll|overlay/.test(getComputedStyle(e).overflowY) && e.scrollHeight > e.clientHeight + 2) {
        conteneur = e; break;
    }
}
conteneur = conteneur || document.scrollingElement || document.documentElement;
const page = conteneur === document.scrollingElement || conteneur === document.documentElement;
const cadre = page ? {left:0, top:0, right:innerWidth, bottom:innerHeight} : conteneur.getBoundingClientRect();
const zone = ancre ? ancre.getBoundingClientRect() : cadre;
const gauche = Math.max(0, cadre.left, zone.left), droite = Math.min(innerWidth, cadre.right, zone.right);
const haut = Math.max(0, cadre.top, zone.top), bas = Math.min(innerHeight, cadre.bottom, zone.bottom);
return {element:conteneur,
    x:Math.max(1, Math.min(innerWidth-2, Math.floor((gauche+droite)/2))),
    y:Math.max(1, Math.min(innerHeight-2, Math.floor((haut+bas)/2))),
    position:Math.round(conteneur.scrollTop), hauteur:conteneur.scrollHeight, fenetre:conteneur.clientHeight,
    fin:conteneur.scrollTop+conteneur.clientHeight >= conteneur.scrollHeight-4};
"""

SECOURS_DEFILEMENT_JS = """
// Dernière carte présente dans les résultats vidéo : déclenche son rendu
// progressif lorsque la molette du navigateur n'a rien déplacé.
const racine = document.querySelector('[data-e2e="search-video-container"]') || document.querySelector('main') || document;
const liens = Array.from(racine.querySelectorAll('a[href*="/video/"], a[href*="/photo/"]'));
const dernier = liens.at(-1);
if (dernier) dernier.scrollIntoView({block:'end',inline:'nearest',behavior:'auto'});
const zone = arguments[0], pas = arguments[1];
if (zone && zone.scrollHeight > zone.clientHeight + 2
    && zone !== document.documentElement && zone !== document.body
    && zone !== document.scrollingElement) {
    zone.scrollBy(0,pas);
} else {
    window.scrollBy(0,pas);
}
return !!dernier;
"""


PAGE_SUIVANTE_JS = r"""
const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
const q = new URL(location.href).searchParams.get('q');
const candidats = document.querySelectorAll('a[rel="next"], nav button, [role="navigation"] button, [data-e2e*="pagination"] button');
return Array.from(candidats).find(e => {
    if (!visible(e) || e.disabled || e.getAttribute('aria-disabled') === 'true') return false;
    if (e.tagName === 'A') {
        const u = new URL(e.href);
        return u.origin === location.origin && u.pathname.replace(/\/$/, '') === '/search/video' && u.searchParams.get('q') === q;
    }
    return /^(next|next page|suivant|suivante|page suivante)$/i.test((e.getAttribute('aria-label') || e.innerText).trim());
}) || null;
"""


def etat_resultats(navigateur):
    """Relire le conteneur à chaque étape, après une éventuelle reconstruction DOM."""
    return navigateur.execute_script(ETAT_RECHERCHE_JS)


def defiler_resultats(navigateur, *, reprendre=False, check=None):
    """Avancer par portion d'écran et réexposer le bas après une attente vide."""
    from scraptiktok import DEFILER_PUBLICATIONS_JS
    check = check or (lambda: None)
    check()
    avant = etat_resultats(navigateur)
    methode = "molette"
    bouton = navigateur.execute_script(PAGE_SUIVANTE_JS) if reprendre and avant["fin"] else None
    if bouton:
        try:
            bouton.click()
            methode = "page_suivante"
        except WebDriverException:
            bouton = None
    if not bouton:
        pas = max(120, min(700, int(avant["fenetre"] * .7)))
        origine = ScrollOrigin.from_viewport(avant["x"], avant["y"])
        try:
            gestes = ActionChains(navigateur)
            if reprendre:
                gestes.scroll_from_origin(origine, 0, -pas).pause(.3)
            gestes.scroll_from_origin(origine, 0, pas * (2 if reprendre else 1)).pause(.2).perform()
        except WebDriverException:
            methode = "conteneur"
            if reprendre:
                navigateur.execute_script(DEFILER_PUBLICATIONS_JS, "progressif", avant["element"], -pas)
                time.sleep(.3)
                check()
            navigateur.execute_script(DEFILER_PUBLICATIONS_JS, "progressif", avant["element"], pas * (2 if reprendre else 1))
    check()
    apres = etat_resultats(navigateur)
    secours = False
    if (methode != "page_suivante"
            and apres["position"] <= avant["position"] + 2
            and apres["hauteur"] <= avant["hauteur"] + 2):
        # Une recherche qui affiche 12 résultats sans jamais déplacer sa grille
        # ne doit pas être considérée comme totalement parcourue.
        check()
        navigateur.execute_script(SECOURS_DEFILEMENT_JS, avant["element"],
                                  max(120, min(700, int(avant["fenetre"] * .7))))
        secours = True
        methode += "+dernier_resultat"
        check()
        apres = etat_resultats(navigateur)
    champs = ("position", "hauteur", "fenetre", "fin")
    return {"avant": {c: avant[c] for c in champs}, "apres": {c: apres[c] for c in champs},
            "methode": methode, "relance": reprendre, "secours": secours}
