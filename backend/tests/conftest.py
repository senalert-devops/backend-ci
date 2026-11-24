# Configuration des tests.
#
# L'API exige ses variables d'environnement (voir app/config.py). Pour les tests, on les
# définit ici AVANT l'import de l'application : base SQLite jetable et identifiants
# administrateur tirés au hasard à chaque lancement (rien n'est écrit en dur dans le dépôt).
import os
import secrets

os.environ["DATABASE_URL"] = "sqlite:///./test_senalert.db"
os.environ["ADMIN_USER"] = "admin-test"
os.environ["ADMIN_PASSWORD"] = secrets.token_urlsafe(16)
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
os.environ.pop("SECRET_KEY", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def identifiants():
    return {"username": os.environ["ADMIN_USER"], "password": os.environ["ADMIN_PASSWORD"]}
