from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from .. import models, schemas, database
from datetime import datetime

router = APIRouter()

# Endpoint per i dettagli del DP (Daily Planning Details)
@router.post("/", response_model=schemas.DPDetailResponse)
def create_dp_detail(dp_detail: schemas.DPDetailCreate, db: Session = Depends(database.get_db)):
    """
    Crea un nuovo dettaglio per un Daily Planning esistente.
    """
    # Verifica che la testata DP esista
    dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_detail.id_testata).first()
    if dp_testa is None:
        raise HTTPException(status_code=404, detail="DP Testa non trovata per l'ID fornito")

    # Verifica che la sede esista se id_sede è fornito
    if dp_detail.id_sede:
        sede = db.query(models.Sede).filter(models.Sede.id == dp_detail.id_sede).first()
        if sede is None:
            raise HTTPException(status_code=404, detail="Sede non trovata per l'ID fornito")
            
    # Verifica che l'utente AG/PS/PM esista se id_agpspm è fornito
    if dp_detail.id_agpspm:
        agpspm_user = db.query(models.OauthUser).filter(models.OauthUser.username == dp_detail.id_agpspm).first()
        if agpspm_user is None:
            raise HTTPException(status_code=404, detail="Utente AG/PS/PM non trovato per l'username fornito")


    db_dp_detail = models.DPDetail(
        id_testata=dp_detail.id_testata,
        caluid=dp_detail.caluid,
        id_sede=dp_detail.id_sede,
        id_agpspm=dp_detail.id_agpspm,
        note=dp_detail.note,
        fasciaoraria=dp_detail.fasciaoraria,
        materialedisponibile=dp_detail.materialedisponibile,
        descrizionemanuale=dp_detail.descrizionemanuale,
        created=datetime.now(),
        createdby=dp_detail.createdby if dp_detail.createdby else '',
        modified=datetime.now(),
        modifiedby=dp_detail.modifiedby if dp_detail.modifiedby else ''
    )
    db.add(db_dp_detail)
    db.commit()
    db.refresh(db_dp_detail)
    return db_dp_detail

@router.get("/by_dp_testa/{id_testata}", response_model=List[schemas.DPDetailResponse])
def get_dp_details_by_dp_testa(id_testata: int, db: Session = Depends(database.get_db)):
    """
    Recupera tutti i dettagli per una specifica testata del Daily Planning.
    """
    details = db.query(models.DPDetail).filter(models.DPDetail.id_testata == id_testata).all()
    return details

@router.put("/{dp_detail_id}", response_model=schemas.DPDetailResponse)
def update_dp_detail(dp_detail_id: int, dp_detail: schemas.DPDetailUpdate, db: Session = Depends(database.get_db)):
    """
    Aggiorna un dettaglio esistente del Daily Planning.hare on
    """
    db_dp_detail = db.query(models.DPDetail).filter(models.DPDetail.id == dp_detail_id).first()
    if db_dp_detail is None:
        raise HTTPException(status_code=404, detail="Dettaglio DP non trovato")

    # Verifica che la sede esista se id_sede è fornito e non None
    if dp_detail.id_sede is not None:
        sede = db.query(models.Sede).filter(models.Sede.id == dp_detail.id_sede).first()
        if sede is None:
            raise HTTPException(status_code=404, detail="Sede non trovata per l'ID fornito")
            
    # Verifica che l'utente AG/PS/PM esista se id_agpspm è fornito e non None
    if dp_detail.id_agpspm is not None:
        agpspm_user = db.query(models.OauthUser).filter(models.OauthUser.username == dp_detail.id_agpspm).first()
        if agpspm_user is None:
            raise HTTPException(status_code=404, detail="Utente AG/PS/PM non trovato per l'username fornito")

    update_data = dp_detail.dict(exclude_unset=True)
    for key, value in update_data.items():
        # Mappa i nomi degli schemi Pydantic ai nomi delle colonne del modello SQLAlchemy
        setattr(db_dp_detail, key, value) # Funziona perché i nomi dei campi negli schemi sono mappati ai nomi delle colonne
        # Esempio: se nel Pydantic c'è 'caluid', e nel modello 'caluid', setattr funziona direttamente

    db_dp_detail.modified = datetime.now() # Aggiorna il timestamp di modifica

    db.commit()
    db.refresh(db_dp_detail)
    return db_dp_detail

@router.delete("/{dp_detail_id}")
def delete_dp_detail(dp_detail_id: int, db: Session = Depends(database.get_db)):
    """
    Elimina un dettaglio specifico del Daily Planning e le tipologie di intervento correlate.
    """
    db_dp_detail = db.query(models.DPDetail).filter(models.DPDetail.id == dp_detail_id).first()
    if db_dp_detail is None:
        raise HTTPException(status_code=404, detail="Dettaglio DP non trovato")
    
    # Elimina le tipologie di intervento correlate
    db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == dp_detail_id).delete()

    db.delete(db_dp_detail)
    db.commit()
    return {"message": "Dettaglio DP e tipologie di intervento correlate eliminate con successo"}