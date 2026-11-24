# app/crud.py
from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models, schemas

# Transitions autorisées, identiques à l'espace administrateur du frontend
TRANSITIONS = {
    "Signalé": {"Vérifié", "Rejeté"},
    "Vérifié": {"En traitement", "Rejeté"},
    "En traitement": {"Résolu"},
    "Résolu": set(),
    "Rejeté": set(),
}


def aujourd_hui() -> str:
    return date.today().strftime("%d/%m/%Y")


def get_signalements(db: Session):
    return db.query(models.Signalement).order_by(models.Signalement.id).all()


def get_signalement(db: Session, signalement_id: str):
    return db.get(models.Signalement, signalement_id)


def prochain_id(db: Session) -> str:
    dernier = db.query(func.max(models.Signalement.id)).scalar()
    numero = int(dernier.split("-")[1]) + 1 if dernier else 1
    return f"SIG-{numero:06d}"


def create_signalement(db: Session, data: schemas.SignalementCreate):
    # Avec plusieurs pods, deux créations simultanées peuvent calculer le même code :
    # la clé primaire refuse le doublon, on recalcule le code et on réessaie.
    for _ in range(5):
        s = models.Signalement(id=prochain_id(db), statut="Signalé", **data.model_dump())
        s.historique.append(models.Etape(statut="Signalé", date=aujourd_hui(), note=""))
        db.add(s)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(s)
        return s
    raise RuntimeError("Impossible de générer un code de suivi unique.")


def changer_statut(db: Session, s: models.Signalement, data: schemas.ChangementStatut):
    if data.statut not in TRANSITIONS[s.statut]:
        raise ValueError(f"Passage de « {s.statut} » à « {data.statut} » interdit.")
    if data.statut == "Résolu" and not data.note.strip():
        raise ValueError("La note de résolution est obligatoire.")
    s.statut = data.statut
    if data.apres:
        s.apres = data.apres
    s.historique.append(models.Etape(statut=data.statut, date=aujourd_hui(), note=data.note.strip()))
    db.commit()
    db.refresh(s)
    return s
