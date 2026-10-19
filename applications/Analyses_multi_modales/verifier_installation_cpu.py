"""Refuser une image contenant une version GPU ou des dépendances CUDA."""
from importlib.metadata import distributions


def verifier_installation_cpu():
    """Vérifier les binaires et les paquets après installation de toutes les dépendances."""
    import torch
    import torchvision

    if torch.version.cuda is not None or not torch.__version__.endswith("+cpu"):
        raise RuntimeError("PyTorch doit être une version CPU sans CUDA.")
    if not torchvision.__version__.endswith("+cpu"):
        raise RuntimeError("Torchvision doit être une version CPU.")
    paquets_gpu = sorted(
        paquet.metadata["Name"] for paquet in distributions()
        if (paquet.metadata.get("Name") or "").lower().replace("_", "-").startswith(
            ("nvidia-", "cuda-", "triton"))
    )
    if paquets_gpu:
        raise RuntimeError("Dépendances GPU inattendues : " + ", ".join(paquets_gpu))
    # Exercer une opération compilée de torchvision pour vérifier la paire installée.
    boites = torch.tensor([[0., 0., 10., 10.], [1., 1., 9., 9.]])
    scores = torch.tensor([0.9, 0.8])
    assert torchvision.ops.nms(boites, scores, 0.5).tolist() == [0]
    print(f"Installation CPU vérifiée : torch {torch.__version__}, torchvision {torchvision.__version__}.")


if __name__ == "__main__":
    verifier_installation_cpu()
