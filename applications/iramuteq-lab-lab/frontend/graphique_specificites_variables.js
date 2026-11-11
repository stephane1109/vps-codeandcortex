// Représentation graphique indépendante des spécificités lexicales.
// Aucune fonction du calcul historique par terme n'est appelée ni modifiée.

const ESPACE_SVG = "http://www.w3.org/2000/svg";

export function lireCsvSpecificites(texteCsv) {
  // Lecture des CSV R write.csv : guillemets doubles, virgules, CRLF et UTF-8.
  const contenu = String(texteCsv || "").replace(/^\uFEFF/, "");
  const lignes = [];
  let ligne = [];
  let cellule = "";
  let citations = false;
  for (let indice = 0; indice < contenu.length; indice += 1) {
    const caractere = contenu[indice];
    if (caractere === '"') {
      if (citations && contenu[indice + 1] === '"') {
        cellule += '"';
        indice += 1;
      } else {
        citations = !citations;
      }
    } else if (caractere === "," && !citations) {
      ligne.push(cellule);
      cellule = "";
    } else if ((caractere === "\n" || caractere === "\r") && !citations) {
      if (caractere === "\r" && contenu[indice + 1] === "\n") indice += 1;
      ligne.push(cellule);
      if (ligne.some((valeur) => valeur !== "")) lignes.push(ligne);
      ligne = [];
      cellule = "";
    } else {
      cellule += caractere;
    }
  }
  if (ligne.length || cellule !== "") {
    ligne.push(cellule);
    lignes.push(ligne);
  }
  if (!lignes.length) return [];
  const colonnes = lignes.shift();
  const necessaires = ["forme", "modalite", "score_specificite", "p_ajustee_bh"];
  if (necessaires.some((colonne) => !colonnes.includes(colonne))) {
    throw new Error("Le tableau lexical ne contient pas les colonnes nécessaires au graphique.");
  }
  return lignes.map((valeurs) =>
    Object.fromEntries(colonnes.map((colonne, indice) => [colonne, valeurs[indice] ?? ""]))
  ).filter((ligne) => ligne.forme && ligne.modalite);
}

export function preparerGrilleSpecificites(lignes, options = {}) {
  const nomModalite = String(options.modalite || "");
  const nombreMots = Math.max(1, Math.min(50, Number(options.nombreMots) || 25));
  const seulementSignificatifs = Boolean(options.significatifs);
  const lignesValides = lignes.map((ligne) => {
    const scoreBrut = String(ligne.score_specificite ?? "");
    const score = scoreBrut === "Inf" ? Infinity :
      (scoreBrut === "-Inf" ? -Infinity : Number(scoreBrut));
    return {
      ...ligne,
      forme: String(ligne.forme || ""),
      modalite: String(ligne.modalite || ""),
      score,
      pAjustee: Number(ligne.p_ajustee_bh),
      totalModalite: Number(ligne.total_occurrences_modalite || 0)
    };
  }).filter((ligne) => ligne.forme && ligne.modalite && !Number.isNaN(ligne.score));

  const toutesModalites = [...new Set(lignesValides.map((ligne) => ligne.modalite))];
  const totalParModalite = new Map();
  lignesValides.forEach((ligne) => {
    if (!totalParModalite.has(ligne.modalite)) {
      totalParModalite.set(ligne.modalite, ligne.totalModalite);
    }
  });
  const toutesTriees = toutesModalites.sort((a, b) =>
    (totalParModalite.get(b) || 0) - (totalParModalite.get(a) || 0) ||
    a.localeCompare(b, "fr")
  );
  const modalites = nomModalite
    ? toutesTriees.filter((nom) => nom === nomModalite)
    : toutesTriees.slice(0, 12);
  const actifs = new Set(modalites);
  const parForme = new Map();
  lignesValides.forEach((ligne) => {
    if (!actifs.has(ligne.modalite)) return;
    const significatif = Number.isFinite(ligne.pAjustee) && ligne.pAjustee <= 0.05;
    if (!parForme.has(ligne.forme)) parForme.set(ligne.forme, new Map());
    parForme.get(ligne.forme).set(ligne.modalite, {...ligne, significatif});
  });
  const mots = [...parForme.entries()].map(([forme, colonnes]) => {
    const valeurs = [...colonnes.values()];
    const admissibles = seulementSignificatifs
      ? valeurs.filter((valeur) => valeur.significatif)
      : valeurs;
    return {
      forme,
      colonnes,
      nombreSignificatif: valeurs.filter((valeur) => valeur.significatif).length,
      maximum: Math.max(0, ...admissibles.map((valeur) => Math.abs(valeur.score)))
    };
  }).filter((mot) => !seulementSignificatifs || mot.nombreSignificatif > 0);
  mots.sort((a, b) =>
    b.nombreSignificatif - a.nombreSignificatif ||
    b.maximum - a.maximum ||
    a.forme.localeCompare(b.forme, "fr")
  );

  return {
    modalites,
    mots: mots.slice(0, nombreMots),
    totalModalites: toutesTriees.length,
    totalFormes: mots.length
  };
}

function creerElementSvg(nom, attributs = {}, texte = null) {
  const element = document.createElementNS(ESPACE_SVG, nom);
  Object.entries(attributs).forEach(([attribut, valeur]) => {
    element.setAttribute(attribut, String(valeur));
  });
  if (texte !== null) element.textContent = String(texte);
  return element;
}

function melangerCouleur(couleur, proportion) {
  const intensite = Math.max(0, Math.min(1, proportion));
  const blanc = [255, 255, 255];
  return "#" + couleur.map((valeur, indice) =>
    Math.round(blanc[indice] * (1 - intensite) + valeur * intensite)
      .toString(16).padStart(2, "0")
  ).join("");
}

function scoreFormate(score) {
  if (score === Infinity) return "+∞";
  if (score === -Infinity) return "−∞";
  return (score > 0 ? "+" : "") + score.toFixed(2).replace("-", "−");
}

export function dessinerGraphiqueSpecificites(conteneur, donnees, options = {}) {
  if (!conteneur) return;
  conteneur.replaceChildren();
  const grille = preparerGrilleSpecificites(donnees, options);

  const titre = document.createElement("h4");
  titre.textContent = "Carte des spécificités lexicales — " +
    String(options.variable || "variable étoilée");
  conteneur.appendChild(titre);

  if (!grille.modalites.length || !grille.mots.length) {
    const message = document.createElement("p");
    message.textContent = "Aucune forme ne correspond à la sélection de modalités et au seuil statistique.";
    conteneur.appendChild(message);
    return;
  }

  const information = document.createElement("p");
  information.className = "muted";
  information.textContent = "Scores signés : bleu = surreprésentation ; rouge = sous-représentation ; " +
    "gris = p ajustée > 0,05. Le signe et la valeur restent visibles dans chaque cellule.";
  conteneur.appendChild(information);

  if (grille.totalModalites > grille.modalites.length) {
    const limite = document.createElement("p");
    limite.className = "muted";
    limite.textContent = "Le graphique présente " + grille.modalites.length +
      " modalités sur " + grille.totalModalites +
      ". Choisissez une modalité dans le filtre pour consulter les autres.";
    conteneur.appendChild(limite);
  }

  const largeurMots = 225;
  const largeurCellule = 135;
  const hauteurEntete = 91;
  const hauteurLigne = 31;
  const largeur = Math.max(470, largeurMots + largeurCellule * grille.modalites.length + 22);
  const hauteur = hauteurEntete + hauteurLigne * grille.mots.length + 25;
  const svg = creerElementSvg("svg", {
    xmlns: ESPACE_SVG, viewBox: `0 0 ${largeur} ${hauteur}`,
    width: largeur, height: hauteur, role: "img",
    "aria-label": "Tableau graphique des mots et scores de spécificité par modalité",
  });
  svg.appendChild(creerElementSvg("title", {}, "Spécificités lexicales par modalité"));
  svg.appendChild(creerElementSvg("desc", {},
    "Mots en lignes, modalités en colonnes. Bleu : surreprésentation significative. " +
    "Rouge : sous-représentation significative. Gris : absence de significativité."));

  grille.modalites.forEach((modalite, indice) => {
    const x = largeurMots + largeurCellule * indice + largeurCellule / 2;
    const nom = modalite.length > 19 ? modalite.slice(0, 18) + "…" : modalite;
    const label = creerElementSvg("text", {
      x, y: 71, "text-anchor": "middle", "font-size": 13,
      "font-weight": "600", fill: "#344054"
    }, nom);
    label.appendChild(creerElementSvg("title", {}, modalite));
    svg.appendChild(label);
  });

  const maximaux = grille.mots.flatMap((mot) =>
    [...mot.colonnes.values()]
      .filter((valeur) => valeur.significatif && Number.isFinite(valeur.score))
      .map((valeur) => Math.abs(valeur.score))
  );
  const seuilCouleur = Math.max(1, Math.min(15, ...maximaux.filter((x) => x > 0)));
  const intensiteMax = maximaux.length ? Math.max(1, ...maximaux) : seuilCouleur;

  grille.mots.forEach((mot, indice) => {
    const y = hauteurEntete + hauteurLigne * indice;
    if (indice % 2 === 0) {
      svg.appendChild(creerElementSvg("rect", {
        x: 0, y: y - 2, width: largeur, height: hauteurLigne, fill: "#f8fafc"
      }));
    }
    const nom = mot.forme.length > 31 ? mot.forme.slice(0, 30) + "…" : mot.forme;
    const libelle = creerElementSvg("text", {
      x: largeurMots - 13, y: y + 20, "text-anchor": "end",
      "font-size": 13, fill: "#1f2937"
    }, nom);
    libelle.appendChild(creerElementSvg("title", {}, mot.forme));
    svg.appendChild(libelle);

    grille.modalites.forEach((modalite, colonne) => {
      const valeur = mot.colonnes.get(modalite);
      const x = largeurMots + colonne * largeurCellule + 4;
      let remplissage = "#f0f1f3";
      let couleurTexte = "#667085";
      if (valeur?.significatif && valeur.score !== 0) {
        const proportion = Number.isFinite(valeur.score)
          ? Math.min(1, Math.abs(valeur.score) / intensiteMax)
          : 1;
        const saturation = 0.33 + 0.67 * Math.sqrt(proportion);
        remplissage = melangerCouleur(valeur.score > 0
          ? [37, 99, 191] : [207, 78, 68], saturation);
        couleurTexte = saturation >= 0.72 ? "#ffffff" : "#1f2937";
      }
      const rect = creerElementSvg("rect", {
        x, y: y + 2, width: largeurCellule - 8, height: hauteurLigne - 6,
        rx: 4, fill: remplissage,
      });
      const details = valeur
        ? `${mot.forme} / ${modalite} : score ${scoreFormate(valeur.score)} ; ` +
          `p ajustée = ${valeur.p_ajustee_bh} ; observé = ${valeur.occurrences_modalite} ; ` +
          `attendu = ${valeur.occurrences_attendues}`
        : `${mot.forme} / ${modalite} : non renseigné dans la matrice`;
      rect.appendChild(creerElementSvg("title", {}, details));
      svg.appendChild(rect);
      svg.appendChild(creerElementSvg("text", {
        x: x + (largeurCellule - 8) / 2, y: y + 20,
        "text-anchor": "middle", "font-size": 12,
        "font-weight": "600", fill: couleurTexte, "pointer-events": "none",
      }, valeur ? scoreFormate(valeur.score) : "—"));
    });
  });

  const zoneDefilement = document.createElement("div");
  zoneDefilement.style.overflowX = "auto";
  zoneDefilement.style.maxWidth = "100%";
  zoneDefilement.appendChild(svg);
  conteneur.appendChild(zoneDefilement);
  const bas = document.createElement("p");
  bas.className = "muted";
  bas.textContent = `${grille.mots.length} mots affichés sur ${grille.totalFormes} formes classables. ` +
    "Survolez une cellule pour connaître l'effectif observé, l'effectif attendu et la probabilité ajustée.";
  conteneur.appendChild(bas);
}
