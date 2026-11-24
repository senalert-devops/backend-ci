# app/config.py : configuration lue dans l'environnement
#
# Aucune valeur par défaut pour les identifiants ni les secrets : ils viennent du
# ConfigMap et du Secret Kubernetes créés par le pipeline deployment-cd. Si une
# variable manque, l'API refuse de démarrer au lieu d'utiliser un mot de passe de secours.
import os


def requis(nom: str) -> str:
    valeur = os.getenv(nom, "").strip()
    if not valeur:
        raise RuntimeError(
            f"Variable d'environnement {nom} absente ou vide. "
            "Sur Kubernetes, elle vient du Secret « senalert-secret » ou du ConfigMap « senalert-config »."
        )
    return valeur


DATABASE_URL = requis("DATABASE_URL")
ADMIN_USER = requis("ADMIN_USER")
ADMIN_PASSWORD = requis("ADMIN_PASSWORD")

# Optionnelle : si elle est absente, la clé de signature est dérivée de ADMIN_PASSWORD
# (voir security.py). Valeur identique sur tous les pods dans les deux cas.
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()

CORS_ORIGINS = [o.strip() for o in requis("CORS_ORIGINS").split(",") if o.strip()]
TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "28800"))  # 8 heures
