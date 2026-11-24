# app/schemas.py
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

Statut = Literal["Signalé", "Vérifié", "En traitement", "Résolu", "Rejeté"]
TypeProbleme = Literal["Rue bouchée", "Canal bouché", "Caniveau bouché"]

# Cadre englobant le Sénégal : refuse les positions manifestement fausses (ex. 0, 0)
LAT_MIN, LAT_MAX = 12.0, 17.0
LON_MIN, LON_MAX = -18.0, -11.0


class EtapeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    statut: Statut
    date: str
    note: str = ""


class SignalementCreate(BaseModel):
    type: TypeProbleme
    description: str = Field(..., min_length=10)
    latitude: float = Field(..., ge=LAT_MIN, le=LAT_MAX)
    longitude: float = Field(..., ge=LON_MIN, le=LON_MAX)
    photo: str = Field(..., min_length=1)


class SignalementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    type: str
    description: str
    latitude: float
    longitude: float
    statut: Statut
    photo: Optional[str] = None
    apres: Optional[str] = None
    historique: list[EtapeOut]


class ChangementStatut(BaseModel):
    statut: Statut
    note: str = ""
    apres: Optional[str] = None


class Connexion(BaseModel):
    username: str
    password: str


class Jeton(BaseModel):
    token: str
