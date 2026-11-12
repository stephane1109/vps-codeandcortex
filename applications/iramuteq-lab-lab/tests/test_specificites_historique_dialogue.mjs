// Vérifier que les spécificités d'un mot n'ouvrent pas l'onglet général.
// Vérifier aussi la réouverture d'un calcul sauvegardé dans la boîte de dialogue.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const repertoire = dirname(fileURLToPath(import.meta.url));
const code = readFileSync(resolve(repertoire, "../frontend/app.js"), "utf8");

function extraireFonctions(debut, fin) {
  const positionDebut = code.indexOf(debut);
  const positionFin = code.indexOf(fin, positionDebut);
  assert.ok(positionDebut >= 0 && positionFin > positionDebut,
    "Les fonctions du dialogue de spécificités doivent rester disponibles.");
  return code.slice(positionDebut, positionFin);
}

function creerElement() {
  return {
    children: [], open: false, disabled: false, textContent: "", value: "",
    replaceChildren() { this.children = []; },
    appendChild(enfant) { this.children.push(enfant); },
    showModal() { this.open = true; }
  };
}

test("Le résultat historique d'un mot reste dans le dialogue", () => {
  const noms = [
    "specificitiesDialogTitle", "specificitiesDialogMeta",
    "specificitiesVariable", "specificitiesIndex",
    "runSpecificitiesBtn", "specificitiesDialog"
  ];
  const elements = Object.fromEntries(noms.map((nom) => [nom, creerElement()]));
  const etat = { specificitiesRequest: { term: "ancien mot" } };
  let affichage = null;
  let statut = "";
  const fonction = new Function(
    "appState", ...noms, "document", "viderResultatsMotDialogue",
    "afficherResultatsMotDialogue", "setSpecificitiesDialogStatus",
    extraireFonctions(
      "function afficherSpecificitesHistoriques(",
      "function closeSpecificitiesDialog()"
    ) + "\nreturn afficherSpecificitesHistoriques;"
  )(
    etat, ...noms.map((nom) => elements[nom]),
    { createElement: creerElement },
    () => {},
    (...argumentsAffichage) => { affichage = argumentsAffichage; },
    (message) => { statut = message; }
  );

  fonction({
    id: "specificites-sauvegardees",
    analysisId: "specificites-sauvegardees",
    summary: {
      term: "violence", variable: "*source",
      variable_label: "source", index: "hypergeo"
    }
  }, [
    { relativePath: "specificites_terme_modalites.csv", encoding: "utf8", data: "terme\nviolence" }
  ]);

  assert.equal(etat.specificitiesRequest, null);
  assert.equal(elements.specificitiesDialog.open, true);
  assert.equal(elements.runSpecificitiesBtn.disabled, true);
  assert.equal(elements.specificitiesDialogTitle.textContent,
    "Spécificités de « violence » (historique)");
  assert.equal(affichage[1], "violence");
  assert.equal(affichage[2], "*source");
  assert.match(statut, /historique/);
});

test("Le calcul du mot conserve la CHD active sans navigation", () => {
  const fonctions = extraireFonctions(
    "function rememberAnalysisHistoryEntry(",
    "function normalizeRuntimeCorpusName("
  );
  const etat = {
    activeAnalysisHistoryId: "chd-active",
    analysisHistory: [],
    corpusFileName: "corpus.txt"
  };
  const memoriser = new Function(
    "appState", "renderAnalysisHistory",
    fonctions + "\nreturn rememberAnalysisHistoryEntry;"
  )(etat, () => {});
  memoriser({
    id: "specificites-nouvelles",
    analysisKind: "specificites",
    persisted: true
  }, { activer: false });

  assert.equal(etat.activeAnalysisHistoryId, "chd-active");
  assert.equal(etat.analysisHistory.length, 1);
  const calcul = extraireFonctions(
    "async function runSpecificitiesFromDialog()",
    "function closeChronologyDialog()"
  );
  assert.doesNotMatch(calcul, /activateTopTab\s*\(/);
  assert.doesNotMatch(calcul, /handleExportsFolderSelection\s*\(/);
  assert.match(calcul, /rememberAnalysisHistoryEntry\(entry, \{ activer: false \}\)/);
});
