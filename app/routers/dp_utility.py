from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database

router = APIRouter()

# Endpoint per le tipologie di intervento (DP Detail TI)
@router.get("/get_url_mainApp", response_model=schemas.DPConfig)
def get_url_mainApp( db: Session = Depends(database.get_db)):
    """
    Aggiunge una tipologia di intervento a un dettaglio DP esistente.
    """
    # Verifica che il dettaglio DP esista
    urlMainApp = db.query(models.Config).filter(models.Config.key == "MAIN_URL").first()
    if urlMainApp is None:
        raise HTTPException(status_code=404, detail="URL principale non trovato")

    return schemas.DPConfig.from_orm(urlMainApp)