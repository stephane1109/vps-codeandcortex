# Collecte Selenium des profils et des médias

`collecte/profil_selenium.py` est le parcours dédié à la grille d'un compte.
`collecte/comptes.py` l'utilise pour un profil sans hashtag et pour compléter les
résultats des pages de hashtags. Les médias et les profils saisis réutilisent ce
parcours ; les recherches de hashtags conservent leur moteur existant.

1. Le navigateur Chrome/Chromium de la collecte est réutilisé.
2. Un observateur Selenium DevTools est attaché avant d'ouvrir le profil.
3. Le collecteur recherche l'onglet des publications et lit les liens HTML ainsi
   que les publications identifiées dans les données initiales.
4. Selenium fait défiler la grille progressivement. L'observateur lit également
   les réponses `/api/post/item_list/` déjà reçues par ce navigateur, qui peuvent
   contenir des publications absentes des six premières vignettes.
5. Chaque lien est contrôlé par auteur et dédoublonné par identifiant. Les champs
   `cursor` et `hasMore` servent à décrire l'avancement observé.
6. Les limites de publications, de défilement et d'attente restent appliquées.

L'observateur ne réémet aucune requête, ne calcule aucune signature, ne change pas
les cookies et n'envoie pas d'identifiants. Les CAPTCHA détectés restent à résoudre
manuellement dans la fenêtre intégrée. Une invitation à se connecter peut être
fermée avec son bouton ; une restriction persistante est signalée avec conservation
des liens déjà lus. Aucun contournement de cette restriction n'est effectué.

Le rapport distingue notamment : `limit`, `connexion_apres_resultats`,
`fin_signalee_par_tiktok`, `pagination_stagnante`, `pagination_non_observee` et
`max_scrolls`. Un résultat de six liens n'est jamais assimilé au nombre total de
publications du compte. Même un signal de fin reçu ne garantit pas l'historique
exhaustif du compte.

L'observation est bornée à 32 réponses en attente, 100 résumés conservés et 16 Mio
de tampon réseau Chrome (4 Mio par réponse). Elle est désactivée en quittant le
profil. Les paramètres signés, en-têtes et cookies ne sont pas exportés. Si DevTools
est indisponible, le parcours HTML reste actif et la limitation figure au rapport.

Références techniques : [API Selenium `start_devtools`](https://www.selenium.dev/selenium/docs/api/py/selenium_webdriver_remote/selenium.webdriver.remote.webdriver.html#selenium.webdriver.remote.webdriver.WebDriver.start_devtools),
[actions de molette Selenium](https://www.selenium.dev/documentation/webdriver/actions_api/wheel/)
et [format des listes de publications observé par TikTok-Api](https://github.com/davidteather/TikTok-Api/blob/main/TikTokApi/api/user.py).

Cette évolution a uniquement fait l'objet d'une lecture statique. Aucun test,
collecte TikTok ou déploiement Coolify n'a été lancé. Les scénarios locaux fournis
dans `tests/test_pagination_profils.py` restent à exécuter par l'utilisateur.
