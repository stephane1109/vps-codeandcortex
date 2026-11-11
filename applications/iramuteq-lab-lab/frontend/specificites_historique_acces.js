// Accès supplémentaire au calcul de spécificités historique, sans modifier app.js.
// Le calcul, les graphiques et les exports restent produits par le moteur d'origine.

const element = (identifiant) => document.getElementById(identifiant);
const selectAnalyse = element("specTermeAnalyse");
const selectVariable = element("specTermeVariable");
const champTerme = element("specTermeMot");
const selectIndice = element("specTermeIndice");
const boutonActualiser = element("specTermeActualiser");
const boutonCalcul = element("specTermeLancer");
const lienArchive = element("specTermeArchive");
const etat = element("specTermeStatut");
const resultats = element("specTermeResultats");

function notifier(message, erreur = false) {
  if (!etat) return;
  etat.textContent = String(message);
  etat.classList.toggle("is-error", Boolean(erreur));
}

function option(selecteur, valeur, etiquette) {
  const item = document.createElement("option");
  item.value = valeur;
  item.textContent = etiquette;
  selecteur.appendChild(item);
}

async function requete(url, options = {}) {
  const reponse = await fetch(url, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
  });
  const contenu = await reponse.json().catch(() => ({}));
  if (!reponse.ok) {
    throw new Error(String(contenu.detail || contenu.message || "Erreur de calcul."));
  }
  return contenu;
}

async function variables() {
  selectVariable.replaceChildren();
  option(selectVariable, "", "Choisir une variable ou les classes CHD");
  if (!selectAnalyse.value) return;
  const donnees = await requete(
    `/api/analyses/${encodeURIComponent(selectAnalyse.value)}/specificities/options`
  );
  const disponibles = Array.isArray(donnees.variables) ? donnees.variables : [];
  disponibles.forEach((variable) => {
    option(
      selectVariable,
      String(variable.id || ""),
      `${variable.label || variable.id} (${(variable.modalities || []).length} modalités)`
    );
  });
  if (disponibles.length) selectVariable.value = String(disponibles[0].id || "");
  notifier("Saisissez une forme lexicale présente dans la matrice de la CHD.");
}

async function analyses() {
  try {
    const avant = selectAnalyse.value;
    notifier("Lecture des analyses CHD...");
    const donnees = await requete("/api/analyses");
    const disponibles = (Array.isArray(donnees.analyses) ? donnees.analyses : [])
      .filter((analyse) => analyse?.analysisKind === "chd" &&
        analyse.completed === true && analyse.success !== false);
    selectAnalyse.replaceChildren();
    option(selectAnalyse, "", "Sélectionner une CHD terminée");
    disponibles.forEach((analyse) => {
      option(selectAnalyse, String(analyse.id),
        String(analyse.corpusName || analyse.folderName || analyse.id));
    });
    if (disponibles.some((analyse) => String(analyse.id) === avant)) {
      selectAnalyse.value = avant;
    } else if (disponibles.length === 1) {
      selectAnalyse.value = String(disponibles[0].id);
    }
    if (!disponibles.length) {
      notifier("Aucune CHD terminée. Lancez une CHD avant le calcul.");
      return;
    }
    await variables();
  } catch (erreur) {
    notifier(erreur.message || String(erreur), true);
  }
}

function lireCsv(texte) {
  // Les exports historiques emploient le format CSV usuel à virgules avec guillemets.
  const lignes = [];
  let ligne = [];
  let cellule = "";
  let citation = false;
  for (let i = 0; i < texte.length; i += 1) {
    const car = texte[i];
    if (car === '"') {
      if (citation && texte[i + 1] === '"') {
        cellule += '"';
        i += 1;
      } else {
        citation = !citation;
      }
    } else if (car === "," && !citation) {
      ligne.push(cellule);
      cellule = "";
    } else if ((car === "\n" || car === "\r") && !citation) {
      if (car === "\r" && texte[i + 1] === "\n") i += 1;
      ligne.push(cellule);
      if (ligne.some((v) => v.trim())) lignes.push(ligne);
      ligne = [];
      cellule = "";
    } else {
      cellule += car;
    }
  }
  if (ligne.length || cellule) {
    ligne.push(cellule);
    lignes.push(ligne);
  }
  return lignes;
}

function afficher(donnees) {
  resultats.replaceChildren();
  const resume = donnees.summary || {};
  const titre = document.createElement("h4");
  titre.textContent = `Spécificités de « ${resume.term || champTerme.value} » par ${resume.variable_label || selectVariable.value}`;
  resultats.appendChild(titre);

  const fichiers = Array.isArray(donnees.files) ? donnees.files : [];
  const tableau = fichiers.find((f) =>
    String(f.relativePath || "").endsWith("specificites_terme_modalites.csv")
  );
  if (tableau?.encoding === "utf8") {
    const lignes = lireCsv(String(tableau.data || ""));
    if (lignes.length) {
      const conteneur = document.createElement("div");
      conteneur.className = "result-table-wrap";
      const table = document.createElement("table");
      table.className = "result-table";
      const tete = document.createElement("thead");
      const ligneTete = document.createElement("tr");
      lignes[0].forEach((valeur) => {
        const th = document.createElement("th");
        th.textContent = valeur;
        ligneTete.appendChild(th);
      });
      tete.appendChild(ligneTete);
      table.appendChild(tete);
      const corps = document.createElement("tbody");
      lignes.slice(1).forEach((ligne) => {
        const tr = document.createElement("tr");
        ligne.forEach((valeur) => {
          const td = document.createElement("td");
          td.textContent = valeur;
          tr.appendChild(td);
        });
        corps.appendChild(tr);
      });
      table.appendChild(corps);
      conteneur.appendChild(table);
      resultats.appendChild(conteneur);
    }
  }

  const graphique = fichiers.find((f) =>
    String(f.relativePath || "").endsWith("graphique_specificites.png")
  );
  if (graphique?.encoding === "base64" && graphique?.data) {
    const image = document.createElement("img");
    image.src = `data:image/png;base64,${graphique.data}`;
    image.alt = "Graphique historique de spécificités par modalité";
    image.style.maxWidth = "100%";
    resultats.appendChild(image);
  }
}

async function calculer() {
  const identifiant = selectAnalyse.value;
  const mot = champTerme.value.trim();
  const variable = selectVariable.value;
  if (!identifiant || !mot || !variable) {
    notifier("Sélectionnez une CHD, saisissez un terme et choisissez les modalités.", true);
    return;
  }
  boutonCalcul.disabled = true;
  lienArchive.hidden = true;
  notifier("Exécution du moteur historique de spécificités...");
  try {
    const donnees = await requete(
      `/api/analyses/${encodeURIComponent(identifiant)}/specificities`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ term: mot, variable, index: selectIndice.value }),
      }
    );
    afficher(donnees);
    if (donnees.analysisId) {
      lienArchive.href = `/api/analyses/${encodeURIComponent(donnees.analysisId)}/archive`;
      lienArchive.hidden = false;
    }
    notifier("Calcul historique terminé. Les résultats sont aussi conservés dans l'historique.");
  } catch (erreur) {
    notifier(erreur.message || String(erreur), true);
  } finally {
    boutonCalcul.disabled = false;
  }
}

selectAnalyse?.addEventListener("change", () => {
  variables().catch((erreur) => notifier(erreur.message, true));
});
boutonActualiser?.addEventListener("click", () => { void analyses(); });
boutonCalcul?.addEventListener("click", () => { void calculer(); });
document.querySelector('[data-tab-target="specificites"]')?.addEventListener(
  "click", () => { void analyses(); }
);
