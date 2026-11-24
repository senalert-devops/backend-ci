# app/models.py
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from .database import Base


class Signalement(Base):
    __tablename__ = "signalements"

    id = Column(String, primary_key=True, index=True)  # ex : SIG-000123
    type = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    latitude = Column(Float, nullable=False)  # position GPS (degrés décimaux, WGS84)
    longitude = Column(Float, nullable=False)
    statut = Column(String, nullable=False, default="Signalé")
    photo = Column(Text)  # image encodée en data URL
    apres = Column(Text)  # photo après intervention
    historique = relationship(
        "Etape", back_populates="signalement", order_by="Etape.id", cascade="all, delete-orphan"
    )


class Etape(Base):
    __tablename__ = "etapes"

    id = Column(Integer, primary_key=True, index=True)
    signalement_id = Column(String, ForeignKey("signalements.id"), nullable=False)
    statut = Column(String, nullable=False)
    date = Column(String, nullable=False)  # format jj/mm/aaaa, comme le frontend
    note = Column(Text, default="")
    signalement = relationship("Signalement", back_populates="historique")
