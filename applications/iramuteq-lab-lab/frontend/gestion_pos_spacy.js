export const SPACY_POS_CATEGORIES = Object.freeze([
  "ADJ",
  "ADP",
  "ADV",
  "AUX",
  "CCONJ",
  "DET",
  "INTJ",
  "NOUN",
  "NUM",
  "PART",
  "PRON",
  "PROPN",
  "PUNCT",
  "SCONJ",
  "SYM",
  "VERB",
  "X"
]);

export const DEFAULT_SPACY_POS_SELECTION = Object.freeze([
  "NOUN",
  "PROPN",
  "VERB",
  "ADJ"
]);

export function normalizeSpacyPosSelection(values) {
  const allowed = new Set(SPACY_POS_CATEGORIES);
  return [...new Set(values.map((value) => String(value || "").trim().toUpperCase()))]
    .filter((value) => allowed.has(value));
}
