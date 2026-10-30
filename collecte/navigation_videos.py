"""Navigation DOM vers la rubrique Vidéos d'un profil TikTok.

Script partagé par Selenium et Playwright. Il ne construit jamais de sous-URL :
il suit uniquement un lien présent sur le profil ou clique son onglet.
"""
NAVIGUER_VIDEOS_JS = r"""(compte) => {
  const attendu = '@' + String(compte).toLowerCase().replace(/^@/, '');
  const visible = e => {
    if (!e || !e.getClientRects().length) return false;
    const s = getComputedStyle(e);
    return s.display !== 'none' && s.visibility !== 'hidden';
  };
  const profil = href => {
    try {
      const u = new URL(href, location.href);
      const premiere = decodeURIComponent(u.pathname.split('/')[1] || '').toLowerCase();
      return ['www.tiktok.com', 'tiktok.com'].includes(u.hostname) && premiere === attendu;
    } catch (_) { return false; }
  };
  const normaliser = s => (s || '').replace(/\s+/g, ' ').trim();
  const libelles = e => [
    normaliser(e.innerText),
    normaliser(e.getAttribute('aria-label')),
    normaliser(e.getAttribute('title')),
    normaliser(e.getAttribute('data-e2e'))
  ].filter(Boolean);
  const video = /^(?:vidéos?|videos?|posts?|publications?)(?:\s*\(\d+\))?$/i;
  const toutes = /^(?:(?:voir|afficher|consulter|see|view|show)\s+(?:toutes?\s+les\s+|all\s+)?(?:vidéos|videos|posts|publications)|(?:all\s+(?:videos|posts)|toutes?\s+les\s+(?:vidéos|publications)))$/i;
  const elements = Array.from(document.querySelectorAll(
    'a,button,[role="tab"],[role="button"],[data-e2e="user-post-tab"],[data-e2e="videos-tab"]'
  )).filter(visible);
  const qualifies = elements.filter(e => {
    const t = libelles(e);
    const balise = e.getAttribute('data-e2e') || '';
    const bonLibelle = t.some(x => video.test(x) || toutes.test(x)) ||
      ['user-post-tab','videos-tab'].includes(balise);
    if (!bonLibelle) return false;
    // Exclure le menu général TikTok et les liens vers d'autres comptes.
    if (e.tagName === 'A') return profil(e.href) &&
      !/\/(?:video|photo)\/\d+\/?$/.test(new URL(e.href).pathname);
    return Boolean(e.closest('main,article,[data-e2e*="profile"],[data-e2e*="user"]'));
  });
  const liens = qualifies.filter(e => e.tagName === 'A' &&
    libelles(e).some(x => toutes.test(x) || video.test(x)) &&
    new URL(e.href).href !== location.href);
  const onglets = qualifies.filter(e => e.getAttribute('role') === 'tab' ||
    ['user-post-tab','videos-tab'].includes(e.getAttribute('data-e2e')) ||
    e.tagName === 'BUTTON');
  const choisi = liens[0] || onglets.find(e => e.getAttribute('aria-selected') !== 'true')
    || onglets[0];
  if (!choisi) return {statut:'introuvable',candidats:elements.length,
    route:location.pathname,liens_video:document.querySelectorAll('a[href*="/video/"]').length};
  const typ = choisi.tagName === 'A' ? 'lien_profil' : 'onglet';
  const destination = choisi.tagName === 'A' ? choisi.href : '';
  // aria-selected='true' décrit uniquement un état d'onglet, pas la
  // disponibilité de la grille : ne jamais annoncer « déjà actif » à vide.
  if (choisi.getAttribute('aria-selected') === 'true') {
    const grille = document.querySelector(
      '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"],' +
      '[data-e2e="user-post-list"]'
    );
    const liens = Array.from(document.querySelectorAll('a[href*="/video/"]'))
      .some(e => profil(e.href));
    return {statut: grille || liens ? 'deja_actif' : 'selectionne_sans_publications',
            type:typ,route:location.pathname,destination,
            grille:!!grille,liens_video:liens};
  }
  choisi.click();
  return {statut:'clic',type:typ,route:location.pathname,destination};
}"""

DIAGNOSTIC_VIDEOS_JS = r"""(compte) => {
  const attendu = '@' + String(compte).toLowerCase().replace(/^@/, '');
  const urls = Array.from(document.querySelectorAll('a[href*="/video/"]'))
    .map(a => a.href).filter(href => {
      try {
        const u = new URL(href);
        return ['tiktok.com','www.tiktok.com'].includes(u.hostname) &&
          decodeURIComponent(u.pathname.split('/')[1]).toLowerCase() === attendu;
      } catch (_) { return false; }
    });
  const grilles = document.querySelectorAll(
    '[data-e2e="user-post-item-list"],[data-e2e^="user-post-item-list"]'
  );
  const tabs = Array.from(document.querySelectorAll('a,button,[role="tab"]'))
    .filter(e => e.getClientRects().length)
    .map(e => (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0,60))
    .filter(t => /vidéos|videos|publications|posts|voir tout|view all/i.test(t))
    .slice(0,12);
  return {route: location.pathname, query:location.search.slice(0,100),
          grilles:grilles.length,liens_video_auteur:new Set(urls).size,
          onglets_detectes:tabs};
}"""
