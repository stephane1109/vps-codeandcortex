"""Tests pour l'import de dictionnaires de connecteurs personnalisés."""

import pytest
from importlib import import_module

connectors_import = import_module("import")


def test_validate_connectors_payload_preserves_newlines():
    payload = {"\n": "RETOUR À LA LIGNE", " si": "CONDITION"}

    connectors = connectors_import._validate_connectors_payload(payload)

    assert connectors == {"\n": "RETOUR À LA LIGNE", "si": "CONDITION"}


def test_validate_connectors_payload_rejects_non_strings():
    with pytest.raises(ValueError):
        connectors_import._validate_connectors_payload({1: "NUMERIC KEY"})

