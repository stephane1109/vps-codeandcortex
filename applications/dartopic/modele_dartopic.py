"""Reproduction expérimentale de l'architecture DARTopic (Seo et al., 2026).

Il ne s'agit PAS d'une distribution officielle des auteurs ni d'une reproduction
validée de leurs résultats. GCN à deux couches + VAE sur graphes de tokens.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import torch
from sklearn.feature_extraction.text import CountVectorizer
from torch import nn
from torch.nn import functional as F
from transformers import AutoModel, AutoTokenizer

MODELE_PLURILINGUE = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class ParametresDARTopic:
    nombre_themes: int = 8
    nombre_epoques: int = 35
    taille_lot: int = 16
    longueur_maximale: int = 64
    taille_vocabulaire: int = 1800
    frequence_minimale: int = 2
    seuil_similarite: float = 0.2
    poids_kl: float = 0.25
    graine: int = 42
    modele_encodeur: str = MODELE_PLURILINGUE


class ReseauDARTopic(nn.Module):
    """Apprendre conjointement le GCN et l'inférence variationnelle."""

    def __init__(self, dimension_entree: int, nombre_themes: int, vocabulaire: int):
        super().__init__()
        self.convolution_1 = nn.Linear(dimension_entree, 192)
        self.convolution_2 = nn.Linear(192, 128)
        self.moyenne = nn.Linear(128, nombre_themes)
        self.log_variance = nn.Linear(128, nombre_themes)
        self.logits_mots = nn.Parameter(torch.randn(nombre_themes, vocabulaire) * 0.02)

    def forward(self, entrees: torch.Tensor, graphes: torch.Tensor, masques: torch.Tensor, entrainement: bool = True):
        cache = F.relu(self.convolution_1(torch.bmm(graphes, entrees)))
        cache = F.relu(self.convolution_2(torch.bmm(graphes, cache)))
        documents = (cache * masques.unsqueeze(-1)).sum(1) / masques.sum(1, keepdim=True).clamp_min(1)
        moyenne = self.moyenne(documents)
        log_variance = self.log_variance(documents).clamp(-8, 8)
        if entrainement:
            latent = moyenne + torch.exp(0.5 * log_variance) * torch.randn_like(moyenne)
        else:
            latent = moyenne
        proportions = F.softmax(latent, dim=1)
        # Décodeur BoW, comme la reconstruction du modèle décrit dans l'article.
        reconstruction = F.log_softmax(proportions @ self.logits_mots, dim=1)
        return proportions, reconstruction, moyenne, log_variance


def _encoder_tokens(textes: list[str], parametres: ParametresDARTopic, progression: Callable[[float, str], None] | None):
    """Créer des plongements contextuels figés sur le CPU, par lots."""
    tokenizer = AutoTokenizer.from_pretrained(parametres.modele_encodeur)
    encodeur = AutoModel.from_pretrained(parametres.modele_encodeur)
    encodeur.eval()
    encodeur.to("cpu")
    regroupements: list[np.ndarray] = []
    masques: list[np.ndarray] = []
    with torch.inference_mode():
        for debut in range(0, len(textes), 12):
            fin = min(debut + 12, len(textes))
            tokens = tokenizer(
                textes[debut:fin], max_length=parametres.longueur_maximale,
                padding="max_length", truncation=True, return_tensors="pt",
                return_special_tokens_mask=True,
            )
            special = tokens.pop("special_tokens_mask")
            sortie = encodeur(**tokens).last_hidden_state
            # Les tokens spéciaux et le padding ne forment pas des nœuds du graphe.
            masque = (tokens["attention_mask"].bool() & ~special.bool()).numpy().astype("float32")
            # Un commentaire vide après tokenisation est représenté par un nœud [CLS].
            vides = np.where(masque.sum(axis=1) == 0)[0]
            for indice in vides:
                masque[indice, 0] = 1.0
            regroupements.append(sortie.numpy().astype("float16"))
            masques.append(masque)
            if progression:
                progression(0.40 * fin / len(textes), f"Encodage : {fin}/{len(textes)} documents")
    del encodeur, tokenizer
    return np.concatenate(regroupements, axis=0), np.concatenate(masques, axis=0)


def _construire_graphes(plongements: np.ndarray, masques: np.ndarray, seuil: float) -> np.ndarray:
    """Graphes symétriques à poids cosinus et normalisation GCN."""
    graphes = np.zeros((len(plongements), plongements.shape[1], plongements.shape[1]), dtype="float32")
    for indice in range(len(plongements)):
        x = plongements[indice].astype("float32")
        valide = masques[indice].astype(bool)
        x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)
        similarites = x @ x.T
        adjacence = np.where(similarites >= seuil, np.maximum(similarites, 0), 0).astype("float32")
        adjacence[~valide, :] = 0
        adjacence[:, ~valide] = 0
        np.fill_diagonal(adjacence, 1.0)
        degres = np.maximum(adjacence.sum(axis=1), 1e-8)
        graphes[indice] = adjacence / np.sqrt(degres[:, None] * degres[None, :])
    return graphes


def entrainer_dartopic(
    textes: list[str], parametres: ParametresDARTopic,
    progression: Callable[[float, str], None] | None = None,
    mots_exclus: list[str] | None = None,
) -> dict[str, object]:
    """Renvoyer les distributions thème-document, thème-mot et l'historique."""
    if len(textes) < 5:
        raise ValueError("Au moins cinq documents non vides sont nécessaires.")
    if any(not texte.strip() for texte in textes):
        raise ValueError("Les textes vides doivent être exclus avant le calcul.")
    if not 2 <= parametres.nombre_themes <= len(textes):
        raise ValueError("Le nombre de thèmes doit rester entre 2 et le nombre de documents.")
    torch.manual_seed(parametres.graine)
    np.random.seed(parametres.graine)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    vectoriseur = CountVectorizer(
        max_features=parametres.taille_vocabulaire,
        min_df=parametres.frequence_minimale,
        stop_words=mots_exclus or None,
        lowercase=True,
        token_pattern=r"(?u)\b\w[\w'-]*\b",
    )
    try:
        matrice = vectoriseur.fit_transform(textes)
    except ValueError as erreur:
        raise ValueError("Vocabulaire vide : réduire la fréquence minimale ou les mots exclus.") from erreur
    if matrice.shape[1] < parametres.nombre_themes:
        raise ValueError("Vocabulaire trop petit pour le nombre de thèmes demandé.")

    plongements, masques = _encoder_tokens(textes, parametres, progression)
    graphes = _construire_graphes(plongements, masques, parametres.seuil_similarite)
    if progression:
        progression(0.48, "Graphes sémantiques construits")
    reseau = ReseauDARTopic(plongements.shape[2], parametres.nombre_themes, matrice.shape[1])
    optimiseur = torch.optim.Adam(reseau.parameters(), lr=0.001)
    historique: list[dict[str, float]] = []
    aleatoire = np.random.default_rng(parametres.graine)
    for epoque in range(parametres.nombre_epoques):
        indices = aleatoire.permutation(len(textes))
        pertes = []
        for debut in range(0, len(textes), parametres.taille_lot):
            lot = indices[debut:debut + parametres.taille_lot]
            donnees = torch.from_numpy(plongements[lot].astype("float32"))
            adjacences = torch.from_numpy(graphes[lot])
            masque_lot = torch.from_numpy(masques[lot])
            comptes = torch.from_numpy(matrice[lot].toarray().astype("float32"))
            reseau.train()
            optimiseur.zero_grad()
            _, log_probabilites, moyenne, log_variance = reseau(donnees, adjacences, masque_lot)
            # Normalisation par taille du document : les messages longs ne dominent pas.
            reconstruction = -((comptes * log_probabilites).sum(1) / comptes.sum(1).clamp_min(1)).mean()
            divergence_kl = -0.5 * (1 + log_variance - moyenne.square() - log_variance.exp()).sum(1).mean()
            perte = reconstruction + parametres.poids_kl * divergence_kl
            if not torch.isfinite(perte):
                raise RuntimeError("Perte non finie : ajuster les paramètres d'entraînement.")
            perte.backward()
            nn.utils.clip_grad_norm_(reseau.parameters(), 5.0)
            optimiseur.step()
            pertes.append(float(perte.detach()))
        moyenne_perte = float(np.mean(pertes))
        historique.append({"epoque": epoque + 1, "perte": moyenne_perte})
        if progression:
            progression(0.48 + 0.47 * (epoque + 1) / parametres.nombre_epoques,
                       f"Entraînement : époque {epoque + 1}/{parametres.nombre_epoques}")
    reseau.eval()
    distributions: list[np.ndarray] = []
    with torch.inference_mode():
        for debut in range(0, len(textes), parametres.taille_lot):
            fin = min(debut + parametres.taille_lot, len(textes))
            theta, _, _, _ = reseau(
                torch.from_numpy(plongements[debut:fin].astype("float32")),
                torch.from_numpy(graphes[debut:fin]),
                torch.from_numpy(masques[debut:fin]),
                entrainement=False,
            )
            distributions.append(theta.numpy())
        probabilites_mots = F.softmax(reseau.logits_mots, dim=1).numpy()
    distributions_documents = np.concatenate(distributions, axis=0)
    vocabulaire = vectoriseur.get_feature_names_out().tolist()
    themes = []
    for k in range(parametres.nombre_themes):
        meilleurs = np.argsort(-probabilites_mots[k])[:15]
        themes.append({"theme": k + 1,
                       "mots": ", ".join(vocabulaire[i] for i in meilleurs),
                       "probabilite_mots": [float(probabilites_mots[k, i]) for i in meilleurs],
                       "mots_liste": [vocabulaire[i] for i in meilleurs]})
    if progression:
        progression(1.0, "Calcul terminé")
    return {"distribution": distributions_documents, "themes": themes,
            "historique": historique, "vocabulaire": vocabulaire,
            "taille_corpus": len(textes)}
