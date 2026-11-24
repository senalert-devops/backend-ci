# SenAlert : backend (dépôt `backend-ci`)

API REST de SenAlert, écrite avec **FastAPI** et **SQLAlchemy**, base **PostgreSQL**.
Elle gère les signalements (rues, canaux et caniveaux bouchés), leur suivi par code
(ex. `SIG-000123`) et l'espace administrateur.

## Structure

```
backend/
├── app/
│   ├── config.py      lecture des variables d'environnement (obligatoires, sans défaut)
│   ├── main.py        routes, sondes de santé, démarrage
│   ├── models.py      tables SQLAlchemy (signalements, etapes)
│   ├── schemas.py     validation des entrées / sorties (Pydantic)
│   ├── crud.py        accès aux données, transitions de statut
│   ├── security.py    jeton administrateur signé
│   ├── database.py    connexion, attente de la base, verrou de démarrage
│   └── seed.py        données de démonstration
├── tests/             tests pytest (SQLite, identifiants de test aléatoires)
├── .env.example       modèle pour le développement local
├── Dockerfile
├── requirements.txt / requirements-dev.txt
└── pytest.ini
```

## Variables d'environnement

**Aucune valeur par défaut** pour les identifiants, les mots de passe et l'URL de la base :
si une variable obligatoire manque, l'API refuse de démarrer (message d'erreur explicite).

| Variable | Obligatoire | Rôle | Source sur Kubernetes |
|----------|:-----------:|------|-----------------------|
| `DATABASE_URL` | oui | URL de connexion à PostgreSQL | Secret `senalert-secret` |
| `ADMIN_USER` | oui | identifiant administrateur | ConfigMap `senalert-config` |
| `ADMIN_PASSWORD` | oui | mot de passe administrateur | Secret `senalert-secret` |
| `CORS_ORIGINS` | oui | origines autorisées, séparées par des virgules | ConfigMap `senalert-config` |
| `SECRET_KEY` | non | clé de signature du jeton ; si absente, dérivée de `ADMIN_PASSWORD` | (non utilisée aujourd'hui) |
| `TOKEN_TTL_SECONDS` | non | durée de vie du jeton | `28800` (8 h) par défaut |

Le Secret `senalert-secret` est créé par le pipeline de `deployment-cd` à partir des secrets
GitHub `POSTGRES_PASSWORD` et `ADMIN_PASSWORD` : ce sont ces vraies valeurs que l'API utilise.
Rien n'est écrit dans le code, dans l'image ni dans ce dépôt.

## Routes

| Méthode | Route | Rôle |
|---------|-------|------|
| GET | `/health` | sonde de vivacité (`livenessProbe`) |
| GET | `/ready` | sonde de disponibilité (`readinessProbe`), vérifie la base |
| GET | `/api/health` | même sonde, accessible à travers nginx |
| GET | `/api/signalements` | liste des signalements |
| GET | `/api/signalements/{code}` | un signalement et son historique |
| POST | `/api/signalements` | créer un signalement (génère le code) |
| POST | `/api/admin/login` | connexion administrateur, renvoie un jeton |
| PATCH | `/api/signalements/{code}/statut` | changer le statut (jeton requis) |

Documentation interactive : `/docs`.

### Position GPS

Un signalement porte `latitude` et `longitude` (degrés décimaux, WGS84), par exemple
`14.7549` et `-17.3908`. L'API refuse les positions hors d'un cadre englobant le Sénégal
(latitude 12 à 17, longitude -18 à -11).

### Statuts

`Signalé → Vérifié → En traitement → Résolu`, et `Rejeté` depuis `Signalé` ou `Vérifié`.
La note est obligatoire pour passer à `Résolu`.

## Fonctionnement avec plusieurs pods

- **Jeton administrateur stable** : le jeton est signé (HMAC-SHA256) avec `SECRET_KEY`, ou, à défaut, avec une clé dérivée de `ADMIN_PASSWORD` (identique sur tous les pods puisque le Secret est partagé). Il
  contient sa date d'expiration. Rien n'est stocké en mémoire : un jeton émis par un pod est
  accepté par tous les autres, et survit à un redémarrage.
- **Démarrage simultané** : au démarrage, chaque pod attend que PostgreSQL réponde, puis prend un
  verrou PostgreSQL (`pg_advisory_lock`) avant de créer les tables et de charger les données de
  démonstration. Un seul pod le fait ; les autres trouvent la base prête.
- **Codes uniques** : si deux signalements sont créés au même instant sur deux pods, la clé
  primaire refuse le doublon et l'API recalcule le code (jusqu'à 5 essais).

## Développement local

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt    # Linux/macOS : .venv/bin/pip
.venv/Scripts/python -m pytest                       # tests (SQLite, sans PostgreSQL)
```

Lancer l'API avec une base PostgreSQL locale : copier `.env.example` en `.env`, remplir les
valeurs (les vôtres, pas de mot de passe par défaut), puis charger ces variables dans le
terminal et lancer `uvicorn app.main:app --reload`.

> **Changement de schéma** : les colonnes `x` et `y` ont été remplacées par `latitude` et
> `longitude`. Une base créée avec l'ancienne version doit être recréée, car l'API ne fait
> pas de migration.

## Image Docker

```bash
docker build -t senalert-backend ./backend
docker run -p 8000:8000 -e DATABASE_URL=... -e ADMIN_USER=... -e ADMIN_PASSWORD=... \
  -e CORS_ORIGINS=... senalert-backend
```

L'image tourne avec un utilisateur sans privilèges et contient une sonde `HEALTHCHECK`
sur `/health`. Sur Kubernetes, le déploiement utilise `/api/health`.

## Pipeline CI (`.github/workflows/ci.yml`)

| Job | Quand | Ce qu'il fait |
|-----|-------|---------------|
| Tests | push et pull request sur `main` | installe les dépendances, lance `pytest` |
| Image Docker | idem | construit l'image, vérifie qu'elle démarre et répond sur `/health` ; **sur `main` seulement**, la publie sur Docker Hub (`latest` et le SHA du commit) |
| Déclencher le déploiement | push sur `main` | envoie l'évènement `backend-updated` à `deployment-cd`, qui redéploie le backend |

Valeurs lues par le pipeline (étape 3 du guide, niveau organisation) :

| Type | Nom | Rôle |
|------|-----|------|
| Variable | `DOCKERHUB_USER` | compte Docker Hub ; l'image est `DOCKERHUB_USER/senalert-backend` |
| Secret | `DOCKERHUB_TOKEN` | jeton Docker Hub (Read & Write) |
| Secret | `CD_TRIGGER_TOKEN` | jeton GitHub (portée `repo`) pour lancer `deployment-cd` |

Le nom de l'organisation n'est pas écrit en dur : le pipeline utilise le propriétaire du dépôt.
Si la variable ou un secret manque, le pipeline échoue avec un message qui le dit.

## Tests

`pytest` lance les tests de l'API (`test_api.py`) et ceux de la position GPS, des sondes, du
jeton, de la configuration obligatoire et du démarrage multi-pods (`test_robustesse.py`).
Ils utilisent SQLite et des identifiants administrateur tirés au hasard à chaque lancement
(`tests/conftest.py`) : aucune base externe ni aucun secret n'est nécessaire.
