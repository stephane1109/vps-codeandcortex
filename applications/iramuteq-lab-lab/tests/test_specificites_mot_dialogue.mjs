// Test de régression du calcul de spécificités lexicales d'un mot.
// Le clic sur une forme de la CHD doit conserver la boîte de dialogue ouverte.
// Les spécificités par variables étoilées constituent une interface indépendante.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import test from "node:test";

const repertoire = dirname(fileURLToPath(import.meta.url));
const code = readFileSync(resolve(repertoire, "../frontend/app.js"), "utf8");
const debut = code.indexOf("function viderResultatsMotDialogue()");
const fin = code.indexOf("function closeChronologyDialog()", debut);
assert.ok(debut >= 0 && fin > debut, "Fonctions historiques du dialogue introuvables");
const fonctions = code.slice(debut, fin);

function element(nom = "div") {
  return {
    nom, children: [], hidden: true, disabled: false, textContent: "",
    classList: { toggle() {} },
    appendChild(enfant) { this.children.push(enfant); },
    append(...enfants) { this.children.push(...enfants); },
    replaceChildren() { this.children = []; },
    removeAttribute(cle) { delete this[cle]; },
    close() { this.open = false; }
  };
}

test("Le mot ouvre ses résultats dans le dialogue sans changer l'onglet CHD", async () => {
  const elements = Object.fromEntries([
    "specificitiesDialogResults", "specificitiesDialogResultTitle",
    "specificitiesDialogResultSummary", "specificitiesDialogResultTable",
    "specificitiesDialogResultGraph", "specificitiesDialogArchive",
    "specificitiesDialogStatus", "specificitiesDialog", "specificitiesVariable",
    "specificitiesIndex", "runSpecificitiesBtn",
    "specificitiesDialogTitle", "specificitiesDialogMeta"
  ].map((nom) => [nom, element(nom)]));
  elements.specificitiesDialog.open = true;
  elements.specificitiesVariable.value = "*source";
  elements.specificitiesIndex.value = "hypergeo";

  const etat = {
    specificitiesRequest: { analysisId: "chd-test", term: "violence", classLabel: "1" },
    analysisHistory: [],
    activeAnalysisHistoryId: "chd-test",
    outputDir: "/exports/chd-test"
  };
  const parametres = [
    "appState", ...Object.keys(elements),
    "document", "formatSummaryValue", "parseCsv", "renderTable",
    "callAnalysisHistoryApi", "normalizePersistentAnalysisHistoryEntry",
    "rememberAnalysisHistoryEntry", "renderAnalysisHistory",
    "setSidebarRuntimeStatus", "log", "handleExportsFolderSelection",
    "renderAnalysisSteps", "renderAnalysisSummary"
  ];
  let navigations = 0;
  let tableaux = 0;
  const valeurs = [
    etat, ...Object.values(elements),
    { createElement: element },
    (valeur) => String(valeur),
    () => ({ headers: ["terme", "modalite", "score_specificite"],
      rows: [["violence", "original", "4"], ["violence", "ia", "-4"]] }),
    () => { tableaux += 1; },
    async () => ({
      analysis: { id: "specificites-test", analysisKind: "specificites" },
      analysisId: "specificites-test",
      summary: {
        term: "violence", variable: "*source", index: "hypergeo",
        variable_label: "source", index_label: "Lafon",
        n_modalities: 2, best_modality: "original", best_score: 4
      },
      files: [
        { relativePath: "specificites_terme_modalites.csv", encoding: "utf8",
          data: "terme,modalite,score_specificite\nviolence,original,4\nviolence,ia,-4" },
        { relativePath: "graphique_specificites.png", encoding: "base64", data: "cG5n" }
      ]
    }),
    (analyse) => ({ ...analyse, persisted: true }),
    (analyse) => { etat.analysisHistory.push(analyse); etat.activeAnalysisHistoryId = analyse.id; },
    () => {}, () => {}, () => {},
    () => { navigations += 1; }, () => {}, () => {}
  ];
  const scenario = new Function(...parametres, fonctions +
    "\nreturn { runSpecificitiesFromDialog, closeSpecificitiesDialog };"
  )(...valeurs);

  await scenario.runSpecificitiesFromDialog();
  assert.equal(navigations, 0);
  assert.equal(etat.activeAnalysisHistoryId, "chd-test");
  assert.equal(etat.outputDir, "/exports/chd-test");
  assert.equal(elements.specificitiesDialog.open, true);
  assert.equal(elements.specificitiesDialogResults.hidden, false);
  assert.equal(elements.specificitiesDialogResultTitle.textContent,
    "Spécificités de « violence » par source");
  assert.equal(tableaux, 1);
  assert.equal(elements.specificitiesDialogResultGraph.children[0].src,
    "data:image/png;base64,cG5n");
  assert.equal(elements.specificitiesDialogArchive.href,
    "/api/analyses/specificites-test/archive");
  assert.equal(etat.analysisHistory.length, 1);

  scenario.closeSpecificitiesDialog();
  assert.equal(elements.specificitiesDialogResults.hidden, true);
  assert.equal(elements.specificitiesDialogResultGraph.children.length, 0);
});
