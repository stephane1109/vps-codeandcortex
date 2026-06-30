"""### Tests de l'analyse factorielle des correspondances

Cette suite valide la construction de la matrice connecteur × document et
l'exécution de l'AFC sur des jeux de données simplifiés afin de garantir les
comptages et les dimensions attendues."""

import numpy as np
import pandas as pd

from afc import build_connector_matrix, run_afc

def test_build_connector_matrix_removes_empty_rows():
    df = pd.DataFrame(
        {
            "texte": ["", "Le connecteur apparait"],
            "marker": ["A", "B"],
        }
    )
    connectors = {"connecteur": "label"}

    matrix = build_connector_matrix(df, connectors)

    assert matrix.shape == (1, 1)
    assert matrix.index.tolist() == [1]
    assert matrix.iloc[0, 0] == 1


def test_build_connector_matrix_filters_to_connector_subcorpus():
    df = pd.DataFrame(
        {
            "texte": ["aucun connecteur ici", "mais pourtant"],
            "marker": ["A", "A"],
        }
    )
    connectors = {"mais": "opposition", "pourtant": "opposition"}

    matrix = build_connector_matrix(df, connectors, {"marker": ["A"]})

    assert matrix.index.tolist() == [1]
    assert matrix.shape == (1, 2)


def test_run_afc_projects_connectors_as_supplementary_columns():
    df = pd.DataFrame(
        {
            "texte": ["mais pourtant", "mais"],
        }
    )

    connectors = {"mais": "opposition", "pourtant": "opposition"}

    matrix = build_connector_matrix(df, connectors)
    row_df, col_df = run_afc(df, connectors, n_components=1)

    assert matrix.shape == (2, 2)
    assert not row_df.empty
    assert not col_df.empty

    # La projection des connecteurs doit correspondre à une projection manuelle
    # des colonnes supplémentaires sur les axes construits à partir des labels.
    label_matrix = pd.DataFrame({"opposition": matrix.sum(axis=1)}, index=matrix.index)
    label_total = label_matrix.to_numpy().sum()
    label_relative = label_matrix / label_total
    row_masses = label_relative.sum(axis=1).to_numpy()
    col_masses = label_relative.sum(axis=0).to_numpy()
    expected = np.outer(row_masses, col_masses)
    standardized = (label_relative.to_numpy() - expected) / np.sqrt(expected)
    U, singular_values, _ = np.linalg.svd(standardized, full_matrices=False)

    manual_projection = []
    for connector in matrix.columns:
        counts = matrix[connector].to_numpy(dtype=float)
        connector_mass = counts.sum() / label_total
        profile = counts / label_total
        standardized_column = (profile - row_masses * connector_mass) / np.sqrt(
            row_masses * connector_mass
        )
        coords = (standardized_column @ U[:, :1]) / np.sqrt(connector_mass)
        manual_projection.append(coords.squeeze())

    projected_connectors = col_df.iloc[:, 0].to_numpy()

    np.testing.assert_allclose(manual_projection, projected_connectors, atol=1e-9)
