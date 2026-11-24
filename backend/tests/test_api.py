import pytest

PHOTO = "data:image/png;base64,AA"


@pytest.fixture()
def h(client, identifiants):
    """En-tête d'authentification d'un administrateur connecté avec les vrais identifiants de l'environnement."""
    r = client.post("/api/admin/login", json=identifiants)
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_donnees_de_demo_chargees(client):
    ids = [s["id"] for s in client.get("/api/signalements").json()]
    assert "SIG-000119" in ids


def test_creation_donne_un_identifiant_unique(client):
    corps = {"type": "Caniveau bouché", "description": "Caniveau bouché devant l’école",
             "latitude": 14.75, "longitude": -17.39, "photo": PHOTO}
    a = client.post("/api/signalements", json=corps).json()
    b = client.post("/api/signalements", json=corps).json()
    assert a["id"] != b["id"]
    assert a["statut"] == "Signalé"
    assert client.get(f"/api/signalements/{a['id'].lower()}").status_code == 200


def test_description_trop_courte_refusee(client):
    corps = {"type": "Rue bouchée", "description": "court", "latitude": 14.75, "longitude": -17.39, "photo": PHOTO}
    assert client.post("/api/signalements", json=corps).status_code == 422


def test_mauvais_mot_de_passe(client, identifiants):
    r = client.post("/api/admin/login", json={**identifiants, "password": "faux"})
    assert r.status_code == 401


def test_mauvais_identifiant(client, identifiants):
    r = client.post("/api/admin/login", json={**identifiants, "username": "inconnu"})
    assert r.status_code == 401


@pytest.mark.parametrize("par_defaut", [("admin", "admin123"), ("admin", "demo123"), ("admin", "admin")])
def test_anciens_identifiants_de_simulation_refuses(client, par_defaut):
    r = client.post("/api/admin/login", json={"username": par_defaut[0], "password": par_defaut[1]})
    assert r.status_code == 401


def test_changement_de_statut_reserve_a_l_admin(client):
    r = client.patch("/api/signalements/SIG-000121/statut", json={"statut": "Vérifié"})
    assert r.status_code == 401


def test_historique_et_transitions(client, h):
    r = client.patch("/api/signalements/SIG-000121/statut", json={"statut": "Vérifié"}, headers=h)
    assert [e["statut"] for e in r.json()["historique"]] == ["Signalé", "Vérifié"]
    # Passer directement à « Résolu » est interdit
    r = client.patch("/api/signalements/SIG-000121/statut",
                     json={"statut": "Résolu", "note": "x"}, headers=h)
    assert r.status_code == 400


def test_note_obligatoire_pour_resoudre(client, h):
    r = client.patch("/api/signalements/SIG-000119/statut", json={"statut": "Résolu"}, headers=h)
    assert r.status_code == 400
