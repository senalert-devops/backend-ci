# app/security.py : jeton administrateur signé (sans état)
#
# Le jeton n'est pas stocké : il est signé avec SECRET_KEY (HMAC-SHA256).
# Tous les pods qui partagent la même SECRET_KEY (Secret Kubernetes) acceptent
# donc les mêmes jetons, et un redémarrage ne déconnecte personne.
import base64
import hashlib
import hmac
import time
from typing import Optional

from . import config


def cle_depuis_mot_de_passe(mot_de_passe: str) -> str:
    """Clé de signature dérivée du mot de passe administrateur.

    Utilisée quand SECRET_KEY n'est pas fournie : le Secret Kubernetes contient déjà
    ADMIN_PASSWORD, identique sur tous les pods, donc tous les pods signent et vérifient
    de la même façon. Conséquence : changer ADMIN_PASSWORD invalide les jetons en cours.
    """
    return hmac.new(mot_de_passe.encode(), b"senalert-jeton-admin", hashlib.sha256).hexdigest()


# SECRET_KEY si elle est définie, sinon dérivée de ADMIN_PASSWORD. Jamais de clé écrite dans le code.
SECRET_KEY = config.SECRET_KEY or cle_depuis_mot_de_passe(config.ADMIN_PASSWORD)

DUREE_JETON = config.TOKEN_TTL_SECONDS


def _b64(donnees: bytes) -> str:
    return base64.urlsafe_b64encode(donnees).decode().rstrip("=")


def _unb64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def _signature(corps: str) -> str:
    return _b64(hmac.new(SECRET_KEY.encode(), corps.encode(), hashlib.sha256).digest())


def creer_jeton(utilisateur: str, maintenant: Optional[float] = None) -> str:
    expiration = int((maintenant if maintenant is not None else time.time()) + DUREE_JETON)
    corps = _b64(f"{utilisateur}:{expiration}".encode())
    return f"{corps}.{_signature(corps)}"


def verifier_jeton(jeton: str, maintenant: Optional[float] = None) -> Optional[str]:
    """Retourne le nom d'utilisateur si le jeton est valide et non expiré, sinon None."""
    try:
        corps, signature = jeton.split(".")
        if not hmac.compare_digest(signature, _signature(corps)):
            return None
        utilisateur, expiration = _unb64(corps).decode().rsplit(":", 1)
        if int(expiration) <= (maintenant if maintenant is not None else time.time()):
            return None
        return utilisateur
    except (ValueError, UnicodeDecodeError):
        return None
