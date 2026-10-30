/* Tester sans TikTok l'action de navigation selon différents DOM de profil. */
const assert = require("node:assert/strict");
const vm = require("node:vm");
const fs = require("node:fs");

const fonctions = fs.readFileSync("/tmp/presse-playwright.js", "utf8");

function element({tag="A",href="",label="Vidéos",profile=true,selected=null}) {
  return {
    tagName:tag,href,innerText:label,
    getClientRects:()=>[{}],
    getAttribute(name) {
      return name === "aria-selected" ? selected : null;
    },
    closest() {return profile ? {} : null;},
    click() {this.clicked = (this.clicked || 0) + 1;}
  };
}
function visiter(items, compte="bfmtv") {
  const url="https://www.tiktok.com/@bfmtv";
  const contexte = {
    URL, location:{href:url,pathname:"/@bfmtv"},
    document:{
      querySelectorAll(){return items;},
      querySelector(){return null;}
    },
    getComputedStyle(){return {display:"block",visibility:"visible"};}
  };
  const naviguer = vm.runInNewContext(fonctions + "\nnav", contexte);
  return naviguer(compte);
}
const lien = element({href:"https://www.tiktok.com/@bfmtv?tab=videos",
                      label:"Voir toutes les vidéos"});
let resultat = visiter([lien]);
assert.equal(resultat.statut,"clic");
assert.equal(resultat.type,"lien_profil");
assert.equal(lien.clicked,1);
const externe=element({href:"https://www.tiktok.com/@autre?tab=videos",label:"Vidéos"});
assert.equal(visiter([externe]).statut,"introuvable");
assert.equal(externe.clicked,undefined);
const onglet=element({tag:"BUTTON",label:"Vidéos",profile:true,selected:"false"});
assert.equal(visiter([onglet]).statut,"clic");
assert.equal(onglet.clicked,1);
const navigationGenerale=element({tag:"BUTTON",label:"Vidéos",profile:false});
assert.equal(visiter([navigationGenerale]).statut,"introuvable");
console.log("Navigation TikTok : lien du profil, onglet, et exclusion hors profil OK");

const actifSansGrille=element({tag:"BUTTON",label:"Vidéos",profile:true,selected:"true"});
assert.equal(visiter([actifSansGrille]).statut,"deja_actif");
assert.equal(actifSansGrille.clicked,undefined);
