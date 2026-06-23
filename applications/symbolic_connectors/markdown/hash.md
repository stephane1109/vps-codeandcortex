### Analyse de l'onglet Hash

- Dans l’onglet **Hash**, le mode « Entre connecteurs uniquement (ignore la ponctuation) » découpe le texte en ne tenant compte que des connecteurs fournis à la fonction, sans ajouter de ponctuation forte ; la regex construit explicitement un motif pour chaque connecteur et l’utilise seule lorsqu’on choisit ce mode. Comme le dictionnaire inclut « retour à la ligne » sous la forme du caractère `\n`, et que la construction de motif accepte les connecteurs faits uniquement d’espaces ou de ponctuation, ce retour à la ligne est bien considéré comme un connecteur dès qu’il est sélectionné dans l’onglet Connecteurs, même quand la ponctuation est ignorée.

- Connecteurs disponibles par étiquette dans `dictionnaires/connecteurs.json` :
  - **ALTERNATIVE** : « sinon », « ou », « ou bien », « ou alors », « soit », « soit ... soit », « autrement », « dans le cas contraire », « à défaut », « a defaut », « faute de quoi », « sans quoi », « à défaut de », « a defaut de », « le cas échéant », « le cas echeant », « à défaut d'accord », « a defaut d'accord », « au contraire », « en revanche », « à l'inverse », « a l'inverse », « inversement », « plutôt que », « plutot que », « ou encore », « au choix ».

  - **CONDITION** : « si », « s'il », « s'ils », « si l'on », « si on », « si tu », « si vous », « si jamais », « si seulement », « pourvu que », « à condition que », « a condition que », « à condition de », « a condition de », « à condition d' », « a condition d' », « sous réserve que », « sous reserve que », « sous condition que », « dans le cas où », « dans le cas ou », « au cas où », « au cas ou », « sous certaines conditions ».

  - **WHILE** : « tant que ».

  - **AND** : « et », « puis », « ensuite », « aussi », « également », « de plus », « en plus », « en outre », « ainsi que ».

  - **ALORS** : « alors », « donc », « dès lors », « des lors », « par conséquent », « par consequent », « en conséquence », « en consequence », « de ce fait », « ainsi », « dans ce cas », « en ce cas », « auquel cas », « de sorte que », « de façon que », « de facon que », « c'est pourquoi », « ceci explique pourquoi », « en cas de ».

  - **RETOUR À LA LIGNE** : le caractère de nouvelle ligne `\n`.
