"""Point d’entrée CI : démarrage supervisé et contrôle TikTok dans Streamlit."""
from smoke_demarrage import principale as verifier_demarrage
from smoke_controle import principale as verifier_controle

if __name__ == "__main__":
    verifier_demarrage()
    verifier_controle()
