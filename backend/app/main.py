# app/main.py
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import config, crud, schemas, security, seed
from .database import Base, SessionLocal, attendre_base, engine, verrou_demarrage

ADMIN_USER = config.ADMIN_USER
ADMIN_PASSWORD = config.ADMIN_PASSWORD


@asynccontextmanager
async def lifespan(_: FastAPI):
    attendre_base()
    # Plusieurs pods démarrent en même temps : un seul initialise la base à la fois.
    with verrou_demarrage():
        Base.metadata.create_all(bind=engine)
        with SessionLocal() as db:
            seed.charger(db)
    yield


app = FastAPI(title="SenAlert API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def exiger_admin(authorization: str = Header(default="")):
    prefixe = "Bearer "
    utilisateur = (
        security.verifier_jeton(authorization[len(prefixe):])
        if authorization.startswith(prefixe)
        else None
    )
    if utilisateur != ADMIN_USER:
        raise HTTPException(status_code=401, detail="Connexion administrateur requise.")


@app.get("/health")
def health():
    """Sonde de vivacité (livenessProbe) : l'API répond."""
    return {"status": "ok"}


@app.get("/ready")
def ready(db: Session = Depends(get_db)):
    """Sonde de disponibilité (readinessProbe) : l'API et la base répondent."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(status_code=503, detail="Base de données indisponible.")
    return {"status": "ok"}


@app.get("/api/health")
def health_api():
    # Même sonde, joignable à travers nginx (/api) depuis le navigateur
    return {"status": "ok"}


@app.get("/api/signalements", response_model=list[schemas.SignalementOut])
def lire_signalements(db: Session = Depends(get_db)):
    return crud.get_signalements(db)


@app.get("/api/signalements/{signalement_id}", response_model=schemas.SignalementOut)
def lire_signalement(signalement_id: str, db: Session = Depends(get_db)):
    s = crud.get_signalement(db, signalement_id.upper())
    if s is None:
        raise HTTPException(status_code=404, detail="Aucun signalement avec ce code.")
    return s


@app.post("/api/signalements", response_model=schemas.SignalementOut, status_code=201)
def creer_signalement(data: schemas.SignalementCreate, db: Session = Depends(get_db)):
    return crud.create_signalement(db, data)


@app.post("/api/admin/login", response_model=schemas.Jeton)
def connexion(data: schemas.Connexion):
    ok_user = secrets.compare_digest(data.username, ADMIN_USER)
    ok_pass = secrets.compare_digest(data.password, ADMIN_PASSWORD)
    if not (ok_user and ok_pass):
        raise HTTPException(status_code=401, detail="Identifiants incorrects.")
    return {"token": security.creer_jeton(data.username)}


@app.patch(
    "/api/signalements/{signalement_id}/statut",
    response_model=schemas.SignalementOut,
    dependencies=[Depends(exiger_admin)],
)
def changer_statut(signalement_id: str, data: schemas.ChangementStatut, db: Session = Depends(get_db)):
    s = crud.get_signalement(db, signalement_id.upper())
    if s is None:
        raise HTTPException(status_code=404, detail="Aucun signalement avec ce code.")
    try:
        return crud.changer_statut(db, s, data)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))
