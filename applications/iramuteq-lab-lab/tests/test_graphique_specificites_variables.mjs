// Vérification autonome du graphique des variables étoilées (node --test).
// Aucune modification des tests ou des fonctions historiques de spécificité.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import test from "node:test";

const repertoire = dirname(fileURLToPath(import.meta.url));
const chemin = resolve(repertoire, "../frontend/graphique_specificites_variables.js");
// L'import via data: permet de tester le module navigateur sans changer le package.json.
const source = readFileSync(chemin, "utf8");
const bibliotheque = await import("data:text/javascript;base64," +
  Buffer.from(source, "utf8").toString("base64"));

const csv = [
  '"variable","modalite","forme","occurrences_modalite","occurrences_attendues","score_specificite","p_ajustee_bh","total_occurrences_modalite"',
  '"source","original","violence",12,5,8.1,0.0001,100',
  '"source","ia","violence",0,7,-8.1,0.0001,100',
  '"source","original","tensions",2,8,-4.3,0.0004,100',
  '"source","ia","tensions",14,8,4.3,0.0004,100',
  '"source","original","mot, composé",3,3,0,0.98,100',
  '"source","ia","mot, composé",3,3,0,0.98,100'
].join("\r\n");

function creerElement(nom) {
  return {
    nom, enfants: [], attributs: {}, style: {},
    appendChild(element) { this.enfants.push(element); },
    replaceChildren() { this.enfants = []; },
    setAttribute(cle, valeur) { this.attributs[cle] = String(valeur); },
    textContent: ""
  };
}

test("Le CSV des modalités est lu avec les guillemets et les virgules", () => {
  const lignes = bibliotheque.lireCsvSpecificites(csv);
  assert.equal(lignes.length, 6);
  assert.equal(lignes[4].forme, "mot, composé");
  assert.deepEqual(new Set(lignes.map((ligne) => ligne.modalite)), new Set(["original", "ia"]));
});

test("La sélection distingue les formes significatives des autres", () => {
  const lignes = bibliotheque.lireCsvSpecificites(csv);
  const grille = bibliotheque.preparerGrilleSpecificites(lignes, {
    nombreMots: 25, significatifs: true
  });
  assert.equal(grille.mots.length, 2);
  assert.deepEqual(new Set(grille.mots.map((mot) => mot.forme)),
    new Set(["violence", "tensions"]));
  const original = bibliotheque.preparerGrilleSpecificites(lignes, {
    modalite: "original", nombreMots: 25
  });
  assert.deepEqual(original.modalites, ["original"]);
});

test("Le SVG distingue visuellement sur/sous-représentation et absence de significativité", () => {
  globalThis.document = {
    createElement: (nom) => creerElement(nom),
    createElementNS: (_espace, nom) => creerElement(nom)
  };
  try {
    const conteneur = creerElement("div");
    bibliotheque.dessinerGraphiqueSpecificites(
      conteneur, bibliotheque.lireCsvSpecificites(csv),
      { variable: "*source", nombreMots: 25 }
    );
    const defilement = conteneur.enfants.find((enfant) => enfant.nom === "div");
    const svg = defilement?.enfants.find((enfant) => enfant.nom === "svg");
    assert.ok(svg);
    const couleurs = svg.enfants.filter((enfant) => enfant.nom === "rect")
      .map((enfant) => enfant.attributs.fill);
    assert.ok(couleurs.includes("#f0f1f3"));
    assert.ok(couleurs.some((couleur) => couleur.startsWith("#") &&
      couleur !== "#f0f1f3" && couleur !== "#f8fafc"));
  } finally {
    delete globalThis.document;
  }
});
