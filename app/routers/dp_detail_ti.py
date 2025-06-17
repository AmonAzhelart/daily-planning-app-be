from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database

router = APIRouter()

# Endpoint per le tipologie di intervento (DP Detail TI)
@router.post("/", response_model=schemas.DPDetailTIResponse)
def create_dp_detail_ti(dp_detail_ti: schemas.DPDetailTICreate, db: Session = Depends(database.get_db)):
    """
    Aggiunge una tipologia di intervento a un dettaglio DP esistente.
    """
    # Verifica che il dettaglio DP esista
    dp_detail = db.query(models.DPDetail).filter(models.DPDetail.id == dp_detail_ti.id_dettaglio).first()
    if dp_detail is None:
        raise HTTPException(status_code=404, detail="Dettaglio DP non trovato per l'ID fornito")
    
    # Verifica che la tipologia di intervento esista
    tipo_intervento = db.query(models.TipoIntervento).filter(models.TipoIntervento.id == dp_detail_ti.id_tipi_interventi).first()
    if tipo_intervento is None:
        raise HTTPException(status_code=404, detail="Tipologia di intervento non trovata per l'ID fornito")


    db_dp_detail_ti = models.DPDetailTI(
        id_dettaglio=dp_detail_ti.id_dettaglio,
        id_tipi_interventi=dp_detail_ti.id_tipi_interventi,
        qta=dp_detail_ti.qta
    )
    db.add(db_dp_detail_ti)
    db.commit()
    db.refresh(db_dp_detail_ti)
    return db_dp_detail_ti

@router.get("/by_dp_detail/{id_dettaglio}", response_model=List[schemas.DPDetailTIResponse])
def get_dp_detail_tis_by_dp_detail(id_dettaglio: int, db: Session = Depends(database.get_db)):
    """
    Recupera tutte le tipologie di intervento per un dettaglio DP specifico.
    """
    tis = db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == id_dettaglio).all()
    return tis

@router.delete("/{dp_detail_ti_id}")
def delete_dp_detail_ti(dp_detail_ti_id: int, db: Session = Depends(database.get_db)):
    """
    Elimina una specifica tipologia di intervento da un dettaglio DP.
    """
    db_dp_detail_ti = db.query(models.DPDetailTI).filter(models.DPDetailTI.id == dp_detail_ti_id).first()
    if db_dp_detail_ti is None:
        raise HTTPException(status_code=404, detail="Tipologia di intervento non trovata")
    db.delete(db_dp_detail_ti)
    db.commit()
    return {"message": "Tipologia di intervento eliminata con successo"}