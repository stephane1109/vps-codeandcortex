// Interface indépendante pour les spécificités de toutes les formes.
// Ne modifie pas le gestionnaire historique des spécificités par terme.

const el = (identifiant) => document.getElementById(identifiant);
const choixAnalyse = el("specVarsAnalyse");
const choixVariable = el("specVarsVariable");
const choixIndice = el("specVarsIndice");
const boutonCalculer = el("specVarsLancer");
const boutonActualiser = el("specVarsActualiser");
const boutonTelecharger = el("specVarsTelecharger");
const zoneStatut = el("specVarsStatut");
const zoneResultats = el("specVarsResultats");
let contenuCsv = "";
let chargement = false;
const panneauSpecificites = document.querySelector('[data-panel="specificites"]');

function afficherStatut(message, erreur = false) {
  if (!zoneStatut) return;
  zoneStatut.textContent = String(message);
  zoneStatut.classList.toggle("is-error", Boolean(erreur));
}

function ajouterOption(selecteur, valeur, libelle) {
  const option = document.createElement("option");
  option.value = valeur;
  option.textContent = libelle;
  selecteur.appendChild(option);
}

async function demanderJson(url, options = {}) {
  const reponse = await fetch(url, {
    credentials: "same-origin",
    cache: "no-store",
    ...options,
  });
  let donnees;
  try {
    donnees = await reponse.json();
  } catch (_erreur) {
    throw new Error("Réponse inattendue du serveur.");
  }
  if (!reponse.ok) {
    throw new Error(String(donnees?.detail || donnees?.message || "Erreur du serveur."));
  }
  return donnees;
}

async function chargerVariables() {
  choixVariable.replaceChildren();
  ajouterOption(choixVariable, "", "Choisir une variable étoilée");
  boutonCalculer.disabled = true;
  const identifiant = choixAnalyse.value;
  if (!identifiant) {
    afficherStatut("Sélectionnez d'abord une CHD terminée.");
    return;
  }
  afficherStatut("Lecture des variables étoilées de la CHD sélectionnée...");
  const resultat = await demanderJson(
    `/api/analyses/${encodeURIComponent(identifiant)}/specificities/options`
  );
  const variables = (Array.isArray(resultat.variables) ? resultat.variables : [])
    .filter((variable) => String(variable?.id || "").startsWith("*"));
  variables.forEach((variable) => {
    const modalites = Array.isArray(variable.modalities) ? variable.modalities : [];
    ajouterOption(
      choixVariable,
      String(variable.id),
      `${variable.label || variable.id} (${modalites.join(" / ")})`
    );
  });
  if (variables.length) {
    const source = variables.find((variable) => String(variable.id) === "*source");
    choixVariable.value = String(source?.id || variables[0].id);
    boutonCalculer.disabled = false;
    afficherStatut(
      `${variables.length} variable(s) étoilée(s) disponibles. ` +
      "Vous pouvez changer la sélection puis calculer les spécificités."
    );
  } else {
    afficherStatut(
      "Cette CHD ne contient pas de variable étoilée avec au moins deux modalités. " +
      "Vérifiez que les en-têtes contiennent par exemple *source_original " +
      "et *source_ia, puis relancez une CHD sur ce corpus.",
      true
    );
  }
}

async function chargerAnalyses() {
  if (!choixAnalyse || chargement) return;
  chargement = true;
  try {
    afficherStatut("Lecture des CHD enregistrées...");
    const anciennes = choixAnalyse.value;
    const resultat = await demanderJson("/api/analyses");
    const analyses = (Array.isArray(resultat.analyses) ? resultat.analyses : [])
      .filter((analyse) =>
        analyse && analyse.analysisKind === "chd" &&
        analyse.completed === true && analyse.success !== false
      );
    choixAnalyse.replaceChildren();
    ajouterOption(choixAnalyse, "", "Sélectionner une CHD terminée");
    analyses.forEach((analyse) => {
      const libelle = String(analyse.corpusName || analyse.folderName || analyse.id);
      ajouterOption(choixAnalyse, String(analyse.id), libelle);
    });
    if (analyses.some((analyse) => String(analyse.id) === anciennes)) {
      choixAnalyse.value = anciennes;
    } else if (analyses.length) {
      // L'historique est trié par date décroissante : choisir la dernière CHD.
      choixAnalyse.value = String(analyses[0].id);
    }
    if (!analyses.length) {
      afficherStatut("Aucune CHD terminée dans votre historique. Lancez d'abord une CHD.");
      return;
    }
    await chargerVariables();
  } catch (erreur) {
    afficherStatut(erreur.message || String(erreur), true);
  } finally {
    chargement = false;
  }
}

function afficherTableau(entetes, lignes, resume) {
  zoneResultats.replaceChildren();
  const blocFiltres = el("specVarsFiltres");
  const choixModalite = el("specVarsModalite");
  const caseSignificatif = el("specVarsSignificatif");
  const indiceModalite = entetes.indexOf("modalite");
  const indiceP = entetes.indexOf("p_ajustee_bh");

  const modalites = Array.isArray(resume.modalities) && resume.modalities.length
    ? resume.modalities
    : [...new Set(lignes.map((ligne) => ligne[indiceModalite]))];
  choixModalite.replaceChildren();
  ajouterOption(choixModalite, "", "Toutes les modalités");
  modalites.forEach((modalite) => {
    ajouterOption(choixModalite, String(modalite), String(modalite));
  });
  caseSignificatif.checked = false;
  blocFiltres.hidden = false;

  const metadonnees = document.createElement("p");
  metadonnees.textContent = (
    `${resume.variable_label || resume.variable || ""} : ` +
    `${resume.n_forms || 0} formes, ${resume.n_modalities || 0} modalités, ` +
    `${resume.n_comparisons || 0} comparaisons. ` +
    "Le tableau présente un aperçu équilibré entre modalités ; " +
    "le fichier CSV exporté contient toutes les formes."
  );
  zoneResultats.appendChild(metadonnees);
  const information = document.createElement("p");
  information.className = "muted";
  zoneResultats.appendChild(information);

  const conteneur = document.createElement("div");
  conteneur.className = "result-table-wrap";
  const table = document.createElement("table");
  table.className = "result-table";
  const entete = document.createElement("thead");
  const ligneEntete = document.createElement("tr");
  entetes.forEach((nom) => {
    const cellule = document.createElement("th");
    cellule.textContent = String(nom);
    ligneEntete.appendChild(cellule);
  });
  entete.appendChild(ligneEntete);
  table.appendChild(entete);
  const corps = document.createElement("tbody");
  table.appendChild(corps);
  conteneur.appendChild(table);
  zoneResultats.appendChild(conteneur);

  const actualiser = () => {
    const modalite = choixModalite.value;
    const seulementSignificatif = caseSignificatif.checked;
    const retenues = lignes.filter((ligne) =>
      (!modalite || String(ligne[indiceModalite]) === modalite) &&
      (!seulementSignificatif ||
       (indiceP >= 0 && Number(ligne[indiceP]) <= 0.05))
    );
    corps.replaceChildren();
    retenues.forEach((ligne) => {
      const tr = document.createElement("tr");
      ligne.forEach((valeur) => {
        const cellule = document.createElement("td");
        cellule.textContent = String(valeur ?? "");
        tr.appendChild(cellule);
      });
      corps.appendChild(tr);
    });
    information.textContent = `${retenues.length} ligne(s) affichée(s) dans l'aperçu.`;
  };
  choixModalite.onchange = actualiser;
  caseSignificatif.onchange = actualiser;
  actualiser();
}

async function lancerCalcul() {
  if (!choixAnalyse.value || !choixVariable.value) {
    afficherStatut("Sélectionnez une CHD et une variable étoilée.", true);
    return;
  }
  boutonCalculer.disabled = true;
  boutonTelecharger.hidden = true;
  contenuCsv = "";
  afficherStatut("Calcul indépendant des spécificités lexicales en cours...");
  try {
    const resultat = await demanderJson(
      `/api/analyses/${encodeURIComponent(choixAnalyse.value)}/specificities/variables`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          variable: choixVariable.value,
          index: choixIndice.value,
        }),
      }
    );
    contenuCsv = String(resultat.csv || "");
    afficherTableau(resultat.headers || [], resultat.rows || [], resultat.summary || {});
    boutonTelecharger.hidden = !contenuCsv;
    afficherStatut("Calcul terminé. Le CSV complet est disponible au téléchargement.");
  } catch (erreur) {
    afficherStatut(erreur.message || String(erreur), true);
  } finally {
    boutonCalculer.disabled = false;
  }
}

choixAnalyse?.addEventListener("change", () => {
  chargerVariables().catch((erreur) => afficherStatut(erreur.message, true));
});
boutonActualiser?.addEventListener("click", () => { void chargerAnalyses(); });
boutonCalculer?.addEventListener("click", () => { void lancerCalcul(); });
boutonTelecharger?.addEventListener("click", () => {
  if (!contenuCsv) return;
  const adresse = URL.createObjectURL(new Blob(
    ["\ufeff", contenuCsv], { type: "text/csv;charset=utf-8" }
  ));
  const lien = document.createElement("a");
  lien.href = adresse;
  lien.download = "specificites_formes_variables.csv";
  document.body.appendChild(lien);
  lien.click();
  lien.remove();
  URL.revokeObjectURL(adresse);
});
document.querySelector('[data-tab-target="specificites"]')?.addEventListener(
  "click", () => { void chargerAnalyses(); }
);

// L'onglet peut aussi être ouvert directement par le gestionnaire d'historique.
// Observer son ouverture évite de laisser le menu de variables vide.
if (panneauSpecificites) {
  const observateur = new MutationObserver(() => {
    if (!panneauSpecificites.hidden) void chargerAnalyses();
  });
  observateur.observe(panneauSpecificites, {
    attributes: true,
    attributeFilter: ["hidden"],
  });
  if (!panneauSpecificites.hidden) void chargerAnalyses();
}
