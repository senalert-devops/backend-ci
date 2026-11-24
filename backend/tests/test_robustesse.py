# Tests du rôle backend : GPS, sondes, jeton stable, démarrage multi-pods
import subprocess
import sys

import pytest

from app import crud, security, seed
from app.database import SessionLocal
from app.models import Signalement

PHOTO = "data:image/png;base64,AA"
CORPS = {"type": "Caniveau bouché", "description": "Caniveau bouché devant l’école",
         "latitude": 14.7549, "longitude": -17.3908, "photo": PHOTO}


# --- Position GPS -----------------------------------------------------------
def test_position_gps_enregistree(client):
    r = client.post("/api/signalements", json=CORPS)
    assert r.status_code == 201
    assert r.json()["latitude"] == 14.7549
    assert r.json()["longitude"] == -17.3908


@pytest.mark.parametrize("lat,lon", [(0, 0), (48.85, 2.35), (14.7, -5.0), (95, -17.3)])
def test_position_hors_senegal_refusee(client, lat, lon):
    r = client.post("/api/signalements", json={**CORPS, "latitude": lat, "longitude": lon})
    assert r.status_code == 422


def test_ancien_format_xy_refuse(client):
    corps = {k: v for k, v in CORPS.items() if k not in ("latitude", "longitude")}
    assert client.post("/api/signalements", json={**corps, "x": 10, "y": 10}).status_code == 422


# --- Sondes Kubernetes ------------------------------------------------------
def test_health_a_la_racine(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_ready_verifie_la_base(client):
    assert client.get("/ready").status_code == 200


# --- Jeton administrateur stable --------------------------------------------
def test_jeton_identique_a_chaque_verification(client, identifiants):
    r = client.post("/api/admin/login", json=identifiants)
    jeton = r.json()["token"]
    # Valide sur toutes les requêtes, quel que soit le "pod" qui répond
    for _ in range(3):
        h = {"Authorization": f"Bearer {jeton}"}
        r = client.patch("/api/signalements/SIG-000121/statut", json={"statut": "Rejeté"}, headers=h)
        assert r.status_code in (200, 400)  # 400 = transition déjà faite, mais pas 401


def test_jeton_signe_avec_une_autre_cle_refuse(monkeypatch):
    jeton = security.creer_jeton("admin")
    assert security.verifier_jeton(jeton) == "admin"
    monkeypatch.setattr(security, "SECRET_KEY", "autre-cle")
    assert security.verifier_jeton(jeton) is None


def test_jeton_expire_refuse():
    jeton = security.creer_jeton("admin", maintenant=1_000)
    assert security.verifier_jeton(jeton, maintenant=1_000 + security.DUREE_JETON - 1) == "admin"
    assert security.verifier_jeton(jeton, maintenant=1_000 + security.DUREE_JETON + 1) is None


@pytest.mark.parametrize("jeton", ["", "abc", "a.b", "a.b.c", "....", "x" * 200])
def test_jeton_invalide_refuse(jeton):
    assert security.verifier_jeton(jeton) is None


def test_cle_de_signature_derivee_identique_sur_chaque_pod():
    # Sans SECRET_KEY, deux pods qui reçoivent le même ADMIN_PASSWORD signent de la même façon
    a = security.cle_depuis_mot_de_passe("mot-de-passe-du-secret")
    b = security.cle_depuis_mot_de_passe("mot-de-passe-du-secret")
    assert a == b
    assert a != security.cle_depuis_mot_de_passe("autre-mot-de-passe")


# --- Configuration obligatoire ------------------------------------------------
@pytest.mark.parametrize("manquante", ["DATABASE_URL", "ADMIN_USER", "ADMIN_PASSWORD", "CORS_ORIGINS"])
def test_demarrage_refuse_sans_variable_obligatoire(manquante):
    """Pas de valeur de secours : sans la variable, l'API ne démarre pas."""
    import os
    import pathlib

    racine = pathlib.Path(__file__).resolve().parent.parent
    env = {k: v for k, v in os.environ.items() if k != manquante}
    r = subprocess.run([sys.executable, "-c", "import app.config"], env=env,
                       capture_output=True, text=True, cwd=racine)
    assert r.returncode != 0
    assert manquante in r.stderr


# --- Démarrage à plusieurs pods ---------------------------------------------
def test_chargement_des_donnees_de_demo_idempotent(client):
    with SessionLocal() as db:
        avant = db.query(Signalement).count()
        seed.charger(db)
        seed.charger(db)
        assert db.query(Signalement).count() == avant


def test_creation_simultanee_reessaie_avec_un_nouveau_code(client, monkeypatch):
    vrai = crud.prochain_id
    appels = {"n": 0}

    def prochain_id_en_collision(db):
        appels["n"] += 1
        return "SIG-000119" if appels["n"] == 1 else vrai(db)  # SIG-000119 existe déjà

    monkeypatch.setattr(crud, "prochain_id", prochain_id_en_collision)
    r = client.post("/api/signalements", json=CORPS)
    assert r.status_code == 201
    assert r.json()["id"] == "SIG-000123"
    assert appels["n"] == 2
