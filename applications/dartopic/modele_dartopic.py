"""Reproduction expérimentale de DARTopic : GCN, VAE et ancrage lexical NMF.

Cette implémentation n'est pas le code officiel de Seo et al. (2026).
L'initialisation et l'ancrage NMF sont une adaptation expérimentale conçue
pour réduire l'effondrement des thèmes sur des commentaires courts.
"""
from __future__ import annotations

import gc
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
import torch
from sklearn.decomposition import NMF
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
    frequence_maximale: float = 0.95
    seuil_similarite: float = 0.2
    poids_kl: float = 0.02
    poids_ancrage: float = 0.8
    graine: int = 42
    modele_encodeur: str = MODELE_PLURILINGUE


class ReseauDARTopic(nn.Module):
    """Encodeur neuronal sur graphes de tokens et décodeur multinomial."""

    def __init__(self, dimension_entree: int, nombre_themes: int, vocabulaire: int):
        super().__init__()
        self.convolution_1 = nn.Linear(dimension_entree, 192)
        self.convolution_2 = nn.Linear(192, 128)
        self.moyenne = nn.Linear(128, nombre_themes)
        self.log_variance = nn.Linear(128, nombre_themes)
        self.logits_mots = nn.Parameter(torch.randn(nombre_themes, vocabulaire) * 0.02)

    def forward(
        self, entrees: torch.Tensor, graphes: torch.Tensor,
        masques: torch.Tensor, entrainement: bool = True,
    ):
        cache = F.relu(self.convolution_1(torch.bmm(graphes, entrees)))
        cache = F.relu(self.convolution_2(torch.bmm(graphes, cache)))
        documents = (cache * masques.unsqueeze(-1)).sum(1) / masques.sum(
            1, keepdim=True
        ).clamp_min(1)
        moyenne = self.moyenne(documents)
        log_variance = self.log_variance(documents).clamp(-8, 8)
        if entrainement:
            latent = moyenne + torch.exp(0.5 * log_variance) * torch.randn_like(moyenne)
        else:
            latent = moyenne
        proportions = F.softmax(latent, dim=1)
        reconstruction = F.log_softmax(proportions @ self.logits_mots, dim=1)
        return proportions, reconstruction, moyenne, log_variance


def construire_vectoriseur(parametres: ParametresDARTopic, mots_exclus: list[str] | None):
    """Séparer les contractions françaises pour rendre NLTK opérant."""
    return CountVectorizer(
        max_features=parametres.taille_vocabulaire,
        min_df=parametres.frequence_minimale,
        max_df=parametres.frequence_maximale,
        stop_words=mots_exclus or None,
        lowercase=True,
        # Apostrophes et formes élidées sont séparées : "c'est" -> "est".
        # Les mots d'une lettre, notamment "a", ne polluent plus les thèmes.
        token_pattern=r"(?u)\b\w\w+\b",
    )


def _encoder_tokens(
    textes: list[str],
    parametres: ParametresDARTopic,
    progression: Callable[[float, str], None] | None,
    repertoire: Path,
):
    """Encoder par petits lots vers un memmap disque, sans RAM proportionnelle au corpus."""
    tokenizer = AutoTokenizer.from_pretrained(parametres.modele_encodeur)
    encodeur = AutoModel.from_pretrained(parametres.modele_encodeur)
    encodeur.eval()
    encodeur.to("cpu")
    longueur = parametres.longueur_maximale
    dimension = int(encodeur.config.hidden_size)
    nombre = len(textes)
    embeddings = np.lib.format.open_memmap(
        repertoire / "embeddings.npy", mode="w+", dtype="float16",
        shape=(nombre, longueur, dimension),
    )
    masques = np.lib.format.open_memmap(
        repertoire / "masques.npy", mode="w+", dtype="uint8",
        shape=(nombre, longueur),
    )
    with torch.inference_mode():
        for debut in range(0, nombre, 12):
            fin = min(debut + 12, nombre)
            jetons = tokenizer(
                textes[debut:fin], max_length=longueur,
                padding="max_length", truncation=True, return_tensors="pt",
                return_special_tokens_mask=True,
            )
            speciaux = jetons.pop("special_tokens_mask")
            sortie = encodeur(**jetons).last_hidden_state
            masque = (jetons["attention_mask"].bool() & ~speciaux.bool()).numpy()
            vides = np.where(masque.sum(axis=1) == 0)[0]
            for indice in vides:
                masque[indice, 0] = True
            embeddings[debut:fin] = sortie.cpu().numpy().astype("float16")
            masques[debut:fin] = masque.astype("uint8")
            if progression:
                progression(0.34 * fin / nombre, f"Encodage : {fin}/{nombre}")
    embeddings.flush()
    masques.flush()
    del encodeur, tokenizer
    gc.collect()
    return embeddings, masques


def _construire_graphes(
    plongements: np.ndarray, masques: np.ndarray, seuil: float,
) -> np.ndarray:
    """Construire la matrice d'adjacence normalisée pour un lot de documents."""
    longueur = plongements.shape[1]
    graphes = np.zeros((len(plongements), longueur, longueur), dtype="float32")
    for indice in range(len(plongements)):
        vecteurs = plongements[indice].astype("float32")
        valides = masques[indice].astype(bool)
        vecteurs /= np.maximum(np.linalg.norm(vecteurs, axis=1, keepdims=True), 1e-8)
        similarites = vecteurs @ vecteurs.T
        adjacence = np.where(
            similarites >= seuil, np.maximum(similarites, 0), 0
        ).astype("float32")
        adjacence[~valides, :] = 0
        adjacence[:, ~valides] = 0
        np.fill_diagonal(adjacence, 1.0)
        degres = np.maximum(adjacence.sum(axis=1), 1e-8)
        graphes[indice] = adjacence / np.sqrt(degres[:, None] * degres[None, :])
    return graphes


def _initialiser_nmf(matrice, parametres: ParametresDARTopic):
    """Créer des thèmes initiaux distincts et un guidage lexical non supervisé."""
    nmf = NMF(
        n_components=parametres.nombre_themes,
        init="nndsvda",
        random_state=parametres.graine,
        max_iter=150,
    )
    documents_themes = nmf.fit_transform(matrice).astype("float32")
    themes_mots = nmf.components_.astype("float32")
    # Chaque document informe ses proportions; les lignes nulles sont uniformes.
    sommes = documents_themes.sum(axis=1, keepdims=True)
    cible = np.divide(
        documents_themes, np.maximum(sommes, 1e-8),
        out=np.full_like(documents_themes, 1.0 / parametres.nombre_themes),
        where=sommes > 1e-8,
    )
    mots = themes_mots + 1e-4
    mots /= mots.sum(axis=1, keepdims=True)
    return cible, np.log(mots).astype("float32")


def _diagnostic_themes(
    distribution: np.ndarray,
    listes_mots: list[list[str]],
) -> dict[str, object]:
    """Identifier un éventuel effondrement thématique persistant."""
    chevauchements = []
    for i in range(len(listes_mots)):
        for j in range(i + 1, len(listes_mots)):
            a, b = set(listes_mots[i]), set(listes_mots[j])
            chevauchements.append(len(a & b) / max(1, len(a | b)))
    effectifs = np.bincount(
        np.argmax(distribution, axis=1), minlength=distribution.shape[1]
    )
    moyenne = float(np.mean(chevauchements)) if chevauchements else 0.0
    return {
        "chevauchement_moyen_mots": moyenne,
        "themes_sans_document_dominant": int(np.sum(effectifs == 0)),
        "effectifs_par_theme": [int(n) for n in effectifs],
        "alerte_themes_similaires": bool(
            moyenne > 0.5 or np.sum(effectifs == 0) >= max(1, distribution.shape[1] // 3)
        ),
    }


def entrainer_dartopic(
    textes: list[str],
    parametres: ParametresDARTopic,
    progression: Callable[[float, str], None] | None = None,
    mots_exclus: list[str] | None = None,
) -> dict[str, object]:
    """Analyser jusqu'à 30 000 commentaires avec stockage disque temporaire."""
    if len(textes) < 5:
        raise ValueError("Au moins cinq documents non vides sont nécessaires.")
    if len(textes) > 30000:
        raise ValueError("La limite de sécurité est fixée à 30 000 textes analysés.")
    if any(not texte.strip() for texte in textes):
        raise ValueError("Les textes vides doivent être exclus du calcul.")
    if not 2 <= parametres.nombre_themes <= len(textes):
        raise ValueError("Le nombre de thèmes doit rester entre 2 et le nombre de textes.")
    if not 0 <= parametres.poids_kl <= 2 or not 0 <= parametres.poids_ancrage <= 4:
        raise ValueError("Poids des régularisations hors limites.")

    torch.manual_seed(parametres.graine)
    np.random.seed(parametres.graine)
    torch.set_num_threads(min(4, torch.get_num_threads()))
    vectoriseur = construire_vectoriseur(parametres, mots_exclus)
    try:
        matrice = vectoriseur.fit_transform(textes)
    except ValueError as erreur:
        raise ValueError(
            "Vocabulaire vide : diminuer la fréquence minimale/maximale "
            "ou retirer des exclusions lexicales."
        ) from erreur
    if matrice.shape[1] < parametres.nombre_themes:
        raise ValueError("Vocabulaire trop petit pour le nombre de thèmes demandé.")
    if progression:
        progression(0.02, "Initialisation NMF des thèmes distincts")
    cibles_nmf, logits_nmf = _initialiser_nmf(matrice, parametres)

    nombre = len(textes)
    longueur = parametres.longueur_maximale
    # La dimension 384 donne une estimation conservatrice pour les encodeurs proposés.
    besoin = int(nombre * (longueur * 384 * 2 + longueur * longueur * 4 + longueur) * 1.3)
    dossier_temporaire = Path(os.getenv("DARTOPIC_SCRATCH_DIR", "/tmp"))
    dossier_temporaire.mkdir(parents=True, exist_ok=True)
    libre = shutil.disk_usage(dossier_temporaire).free
    if besoin > libre:
        raise RuntimeError(
            f"Espace disque temporaire insuffisant : environ {besoin / 1e9:.2f} Go "
            f"nécessaires, {libre / 1e9:.2f} Go disponibles. "
            "Configurer DARTOPIC_SCRATCH_DIR sur un volume persistant."
        )

    with tempfile.TemporaryDirectory(prefix="dartopic_", dir=dossier_temporaire) as temp:
        repertoire = Path(temp)
        embeddings, masques = _encoder_tokens(textes, parametres, progression, repertoire)
        graphes = np.lib.format.open_memmap(
            repertoire / "graphes.npy", mode="w+", dtype="float32",
            shape=(nombre, longueur, longueur),
        )
        for debut in range(0, nombre, 24):
            fin = min(debut + 24, nombre)
            graphes[debut:fin] = _construire_graphes(
                embeddings[debut:fin], masques[debut:fin],
                parametres.seuil_similarite,
            )
            if progression:
                progression(
                    0.34 + 0.12 * fin / nombre,
                    f"Graphes : {fin}/{nombre}",
                )
        graphes.flush()

        reseau = ReseauDARTopic(
            embeddings.shape[2], parametres.nombre_themes, matrice.shape[1]
        )
        with torch.no_grad():
            reseau.logits_mots.copy_(torch.from_numpy(logits_nmf))
        optimiseur = torch.optim.Adam(reseau.parameters(), lr=0.0005)
        historique: list[dict[str, float]] = []
        aleatoire = np.random.default_rng(parametres.graine)

        for epoque in range(parametres.nombre_epoques):
            indices = aleatoire.permutation(nombre)
            pertes = []
            for debut in range(0, nombre, parametres.taille_lot):
                lot = indices[debut:debut + parametres.taille_lot]
                donnees = torch.from_numpy(
                    np.asarray(embeddings[lot], dtype="float32")
                )
                adjacences = torch.from_numpy(
                    np.asarray(graphes[lot], dtype="float32")
                )
                masque_lot = torch.from_numpy(
                    np.asarray(masques[lot], dtype="float32")
                )
                comptes = torch.from_numpy(
                    matrice[lot].toarray().astype("float32")
                )
                cible = torch.from_numpy(cibles_nmf[lot])
                reseau.train()
                optimiseur.zero_grad()
                theta, log_probabilites, moyenne, log_variance = reseau(
                    donnees, adjacences, masque_lot,
                )
                reconstruction = -(
                    (comptes * log_probabilites).sum(1) /
                    comptes.sum(1).clamp_min(1)
                ).mean()
                divergence_kl = -0.5 * (
                    1 + log_variance - moyenne.square() - log_variance.exp()
                ).sum(1).mean()
                # L'ancrage NMF limite l'effondrement des proportions vers 1/K.
                ancrage = F.kl_div(
                    theta.clamp_min(1e-8).log(), cible, reduction="batchmean"
                )
                regularisation = parametres.poids_kl * min(
                    1.0, (epoque + 1) / max(1, parametres.nombre_epoques * 0.3)
                )
                perte = (
                    reconstruction + regularisation * divergence_kl +
                    parametres.poids_ancrage * ancrage
                )
                if not torch.isfinite(perte):
                    raise RuntimeError(
                        "Perte non finie : réduire le poids KL ou l'ancrage."
                    )
                perte.backward()
                nn.utils.clip_grad_norm_(reseau.parameters(), 5.0)
                optimiseur.step()
                pertes.append(float(perte.detach()))
            historique.append({
                "epoque": epoque + 1, "perte": float(np.mean(pertes)),
            })
            if progression:
                progression(
                    0.46 + 0.47 * (epoque + 1) / parametres.nombre_epoques,
                    f"Entraînement : {epoque + 1}/{parametres.nombre_epoques}",
                )

        reseau.eval()
        distributions: list[np.ndarray] = []
        with torch.inference_mode():
            for debut in range(0, nombre, parametres.taille_lot):
                fin = min(debut + parametres.taille_lot, nombre)
                theta, _, _, _ = reseau(
                    torch.from_numpy(
                        np.asarray(embeddings[debut:fin], dtype="float32")
                    ),
                    torch.from_numpy(
                        np.asarray(graphes[debut:fin], dtype="float32")
                    ),
                    torch.from_numpy(
                        np.asarray(masques[debut:fin], dtype="float32")
                    ),
                    entrainement=False,
                )
                distributions.append(theta.numpy())
            probabilites_mots = F.softmax(
                reseau.logits_mots, dim=1
            ).numpy()
        distributions_documents = np.concatenate(distributions, axis=0)
        # Libérer les memmap avant la suppression des fichiers temporaires.
        del embeddings, masques, graphes, reseau
        gc.collect()

    vocabulaire = vectoriseur.get_feature_names_out().tolist()
    exclusivite = probabilites_mots / np.maximum(
        probabilites_mots.sum(axis=0, keepdims=True), 1e-10
    )
    # Mots distinctifs : fréquence relative pondérée par l'exclusivité du thème.
    scores = (probabilites_mots ** 0.6) * (exclusivite ** 0.4)
    themes: list[dict[str, object]] = []
    listes: list[list[str]] = []
    for k in range(parametres.nombre_themes):
        meilleurs = np.argsort(-scores[k])[:15]
        plus_frequents = np.argsort(-probabilites_mots[k])[:15]
        liste = [vocabulaire[i] for i in meilleurs]
        listes.append(liste)
        themes.append({
            "theme": k + 1,
            "mots": ", ".join(liste),
            "mots_frequents": ", ".join(vocabulaire[i] for i in plus_frequents),
            "probabilite_mots": [
                float(probabilites_mots[k, i]) for i in meilleurs
            ],
            "mots_liste": liste,
        })
    diagnostic = _diagnostic_themes(distributions_documents, listes)
    if progression:
        progression(1.0, "Calcul terminé")
    return {
        "distribution": distributions_documents,
        "themes": themes,
        "historique": historique,
        "vocabulaire": vocabulaire,
        "taille_corpus": nombre,
        "diagnostic": diagnostic,
        "methode": "GCN-VAE avec initialisation et ancrage NMF (expérimental)",
    }
