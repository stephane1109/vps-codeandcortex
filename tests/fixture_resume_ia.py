"""Page locale pour vérifier les sélecteurs dans un vrai navigateur, sans TikTok.

Exécution : PYTHONPATH=. python tests/fixture_resume_ia.py /tmp/fixture-ia.html
Ouvrir ensuite la page via un serveur HTTP local ; le bilan doit indiquer SUCCÈS.
"""
import json
import sys
from pathlib import Path

from scraptiktok import PAGE_JS, DEPLIER_LEGENDE_JS


def construire_page():
    """Insérer les scripts de production dans un DOM à chargement différé."""
    page = '''<!doctype html><html lang="fr"><meta charset="utf-8"><title>TikTok</title>
<body><h1>Validation des résumés IA — page locale</h1><pre id="bilan">Tests en cours…</pre>
<article><a href="/@autre/video/9999999999">Recommandation</a>
<p data-e2e="video-desc">Légende étrangère</p><div>Résumé qui ne doit jamais être récupéré.
<p>Ceci est un résumé généré par l’IA</p></div></article>
<article id="cible"><a href="/@test/video/1234567890">Publication cible</a>
<div data-media-card-description-container="true"><p data-e2e="video-desc">Légende originale</p></div>
<div><button id="plus"><span>Plus</span></button></div><section id="resume"></section></article>
<script>
const lire = new Function(LECTURE);
const deplier = new Function(DEPLIAGE);
const resultats = [];
function verifier(condition, message) {
    if (!condition) throw new Error(message);
    resultats.push('OK : ' + message);
}
const attendre = ms => new Promise(r => setTimeout(r, ms));
(async () => {
    try {
        verifier(lire('1234567890').description === 'Légende originale', 'bonne publication sélectionnée');
        verifier(!lire('1111111111').description, 'aucune lecture de recommandation pour un ID absent');
        deplier('1234567890');
        verifier(!lire('1234567890').blocs_resume_ia.length, 'aucun résumé avant hydratation');
        await attendre(300);
        document.getElementById('plus').onclick = () => {
            document.getElementById('plus').textContent = 'Moins';
            setTimeout(() => {
                document.getElementById('resume').innerHTML = '<div><h2>Une manifestation en ville</h2>' +
                    '<p>Des participants se rassemblent dans les rues de la ville.</p>' +
                    '<p>Ceci est un résumé généré par l’IA. Feedback et aide – TikTok</p></div>';
            }, 700);
        };
        verifier(deplier('1234567890'), 'clic sur Plus après hydratation');
        await attendre(1000);
        const page = lire('1234567890');
        verifier(page.blocs_resume_ia.some(t => t.includes('Des participants')), 'résumé différé lu malgré titre générique');
        verifier(page.blocs_resume_ia.every(t => !t.includes('jamais être récupéré')), 'recommandation exclue du résumé');
        const sansIA = lire('1234567890', false);
        verifier(sansIA.description === 'Légende originale', 'légende conservée sans IA');
        verifier(!sansIA.blocs_resume_ia.length && !sansIA.texte_article_deplie && !sansIA.resume_ia_tiktok, 'recherche de résumé désactivée sans IA');
        verifier(!deplier('1234567890'), 'ne clique pas sur Moins');
        document.getElementById('resume').innerHTML = '<div><h2>Résumé IA</h2><p>Une autre synthèse correctement identifiée.</p></div>';
        verifier(lire('1234567890').resume_ia_tiktok === 'Une autre synthèse correctement identifiée.', 'titre IA retiré du texte');
        document.getElementById('bilan').textContent = 'SUCCÈS — ' + resultats.length + ' vérifications\\n' + resultats.join('\\n');
    } catch (e) {
        document.getElementById('bilan').textContent = 'ÉCHEC : ' + e.message + '\\n' + resultats.join('\\n');
    }
})();
</script></body></html>'''
    return page.replace('LECTURE', json.dumps(PAGE_JS)).replace('DEPLIAGE', json.dumps(DEPLIER_LEGENDE_JS))


if __name__ == '__main__':
    Path(sys.argv[1]).write_text(construire_page(), encoding='utf-8')
