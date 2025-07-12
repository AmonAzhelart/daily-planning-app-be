from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List

from .. import models, schemas
from ..database import get_db

router = APIRouter()

@router.get("/", response_model=List[schemas.TipoIntervento])
def get_all_intervention_types(db: Session = Depends(get_db)):
    """
    Recupera tutte le tipologie di intervento.
    Per ogni tipo, calcola se è stato utilizzato almeno una volta.
    """
    intervention_types = db.query(models.TipoIntervento).options(joinedload(models.TipoIntervento.details)).all()
    
    response = []
    for tipo in intervention_types:
        response.append(
            schemas.TipoIntervento(
                id=tipo.id,
                descrizione=tipo.descrizione,
                is_used=len(tipo.details) > 0
            )
        )
    return response

@router.post("/", response_model=schemas.TipoIntervento, status_code=status.HTTP_201_CREATED)
def create_intervention_type(request: schemas.TipoInterventoCreate, db: Session = Depends(get_db)):
    """
    Crea una nuova tipologia di intervento.
    """
    new_intervention_type = models.TipoIntervento(descrizione=request.descrizione)
    db.add(new_intervention_type)
    db.commit()
    db.refresh(new_intervention_type)
    
    # Ritorna l'oggetto completo con is_used=False di default
    return schemas.TipoIntervento(
        id=new_intervention_type.id,
        descrizione=new_intervention_type.descrizione,
        is_used=False
    )

@router.put("/{id}", response_model=schemas.TipoIntervento)
def update_intervention_type(id: int, request: schemas.TipoInterventoUpdate, db: Session = Depends(get_db)):
    """
    Aggiorna la descrizione di una tipologia di intervento.
    """
    intervention_type = db.query(models.TipoIntervento).options(joinedload(models.TipoIntervento.details)).filter(models.TipoIntervento.id == id).first()

    if not intervention_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Tipo di intervento con id {id} non trovato")

    intervention_type.descrizione = request.descrizione
    db.commit()
    db.refresh(intervention_type)

    return schemas.TipoIntervento(
        id=intervention_type.id,
        descrizione=intervention_type.descrizione,
        is_used=len(intervention_type.details) > 0
    )


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intervention_type(id: int, db: Session = Depends(get_db)):
    """
    Elimina una tipologia di intervento solo se non è mai stata utilizzata.
    """
    # Usiamo joinedload per caricare la relazione `details` in modo efficiente
    intervention_type = db.query(models.TipoIntervento).options(joinedload(models.TipoIntervento.details)).filter(models.TipoIntervento.id == id).first()

    if not intervention_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Tipo di intervento con id {id} non trovato")

    # Controlla se ci sono record associati nella tabella di dettaglio
    if len(intervention_type.details) > 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail="Impossibile eliminare il tipo di intervento perché è già stato utilizzato.")

    db.delete(intervention_type)
    db.commit()
    return

