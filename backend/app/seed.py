# app/seed.py : données de démonstration chargées si la base est vide
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models

DONNEES = [
    ("SIG-000117", "Rue bouchée", "Signalement déjà fait ailleurs.", 14.7157, -17.2733, "Rejeté",
     [("Signalé", "25/10/2026", ""), ("Rejeté", "27/10/2026", "Motif : doublon")]),
    ("SIG-000118", "Caniveau bouché", "Caniveau rempli de sable devant le marché.", 14.7549, -17.3908, "Résolu",
     [("Signalé", "28/10/2026", ""), ("Vérifié", "29/10/2026", ""), ("En traitement", "31/10/2026", ""),
      ("Résolu", "03/11/2026", "Caniveau curé par l’équipe communale.")]),
    ("SIG-000119", "Rue bouchée", "Eau stagnante qui bloque la rue principale.", 14.7692, -17.3900, "En traitement",
     [("Signalé", "01/11/2026", ""), ("Vérifié", "02/11/2026", ""),
      ("En traitement", "04/11/2026", "Intervention prévue cette semaine.")]),
    ("SIG-000120", "Canal bouché", "Canal à ciel ouvert plein de déchets.", 14.7833, -17.3167, "Vérifié",
     [("Signalé", "03/11/2026", ""), ("Vérifié", "05/11/2026", "")]),
    ("SIG-000121", "Caniveau bouché", "Grille d’évacuation obstruée près de l’école.", 14.7580, -17.4400, "Signalé",
     [("Signalé", "06/11/2026", "")]),
    ("SIG-000122", "Caniveau bouché", "Caniveau effondré et rempli de gravats.", 14.7480, -17.3850, "Signalé",
     [("Signalé", "07/11/2026", "")]),
]


def charger(db: Session) -> None:
    """Charge les données de démo si la base est vide (sans danger si appelée deux fois)."""
    if db.query(models.Signalement).first():
        return
    for id_, type_, desc, lat, lon, statut, etapes in DONNEES:
        s = models.Signalement(
            id=id_, type=type_, description=desc, latitude=lat, longitude=lon, statut=statut
        )
        s.historique = [models.Etape(statut=st, date=d, note=n) for st, d, n in etapes]
        db.add(s)
    try:
        db.commit()
    except IntegrityError:
        # Un autre pod vient de charger les mêmes données : rien à faire.
        db.rollback()
