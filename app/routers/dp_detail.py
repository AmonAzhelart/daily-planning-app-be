from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, selectinload, joinedload
from typing import List
from .. import models, schemas, database
from datetime import datetime

router = APIRouter()

# --- FUNZIONE HELPER PER VALIDARE LE RISORSE ---
def get_and_validate_agpspm_users(db: Session, usernames: List[str]) -> List[models.OauthUser]:
    if not usernames:
        return []
    users = db.query(models.OauthUser).filter(models.OauthUser.username.in_(usernames)).all()
    if len(users) != len(set(usernames)):
        found_usernames = {user.username for user in users}
        missing_usernames = set(usernames) - found_usernames
        raise HTTPException(status_code=404, detail=f"Utenti AG/PS/PM non trovati: {', '.join(missing_usernames)}")
    return users


@router.post("/", response_model=schemas.DPDetailResponse, summary="Crea un nuovo dettaglio per un DP")
def create_dp_detail(dp_detail: schemas.DPDetailCreate, db: Session = Depends(database.get_db)):
    """
    Crea un nuovo dettaglio per un Daily Planning esistente, associando una o più risorse.
    """
    if not db.query(models.DPTesta).filter(models.DPTesta.id == dp_detail.id_testata).first():
        raise HTTPException(status_code=404, detail="DP Testa non trovata per l'ID fornito")
    
    if dp_detail.id_sede and not db.query(models.Sede).filter(models.Sede.id == dp_detail.id_sede).first():
        raise HTTPException(status_code=404, detail="Sede non trovata per l'ID fornito")
            
    validated_users = get_and_validate_agpspm_users(db, dp_detail.agpspm_users)
    
    # Crea l'oggetto senza agpspm_users perché verrà gestito tramite l'association proxy
    detail_data = dp_detail.dict(exclude={'agpspm_users'})
    db_dp_detail = models.DPDetail(**detail_data)
    
    # Assegna gli utenti tramite il proxy
    db_dp_detail.agpspm_users = validated_users

    db.add(db_dp_detail)
    db.commit()
    db.refresh(db_dp_detail)
    return db_dp_detail


@router.get("/by_dp_testa/{id_testata}", response_model=List[schemas.DPDetailResponse], summary="Recupera tutti i dettagli di un DP")
def get_dp_details_by_dp_testa(id_testata: int, db: Session = Depends(database.get_db)):
    """
    Recupera tutti i dettagli per una specifica testata del Daily Planning,
    caricando in modo efficiente (eager loading) le risorse associate per evitare errori di validazione.
    """
    details = (
        db.query(models.DPDetail)
        .filter(models.DPDetail.id_testata == id_testata)
        .options(
            # --- CORREZIONE APPLICATA ---
            # Dobbiamo caricare la relazione reale, non il proxy.
            # Il percorso corretto è: DPDetail -> agpspm_associations -> agpspm_user -> role
            selectinload(models.DPDetail.agpspm_associations)
            .selectinload(models.DPDetailAGPSPM.agpspm_user)
            .selectinload(models.OauthUser.role)
        )
        .all()
    )
    # Anche se carichiamo 'agpspm_associations', Pydantic userà il proxy 'agpspm_users' 
    # per la serializzazione, che ora avrà i dati pre-caricati.
    return details


@router.put("/{dp_detail_id}", response_model=schemas.DPDetailResponse, summary="Aggiorna un singolo dettaglio")
def update_dp_detail(dp_detail_id: int, dp_detail: schemas.DPDetailUpdate, db: Session = Depends(database.get_db)):
    """
    Aggiorna un dettaglio esistente del Daily Planning.
    """
    # Usiamo options anche qui per caricare le relazioni e averle disponibili dopo l'aggiornamento
    db_dp_detail = db.query(models.DPDetail).options(
        selectinload(models.DPDetail.agpspm_associations).selectinload(models.DPDetailAGPSPM.agpspm_user)
    ).filter(models.DPDetail.id == dp_detail_id).first()
    
    if db_dp_detail is None:
        raise HTTPException(status_code=404, detail="Dettaglio DP non trovato")

    update_data = dp_detail.dict(exclude_unset=True)

    # Gestione separata dell'aggiornamento delle risorse
    if 'agpspm_users' in update_data:
        usernames = update_data.pop('agpspm_users')
        if usernames is not None:
            validated_users = get_and_validate_agpspm_users(db, usernames)
            db_dp_detail.agpspm_users = validated_users
        else:
            db_dp_detail.agpspm_users = []


    if 'id_sede' in update_data and update_data['id_sede'] is not None:
        if not db.query(models.Sede).filter(models.Sede.id == update_data['id_sede']).first():
            raise HTTPException(status_code=404, detail="Sede non trovata per l'ID fornito")
    
    for key, value in update_data.items():
        setattr(db_dp_detail, key, value)

    db_dp_detail.modified = datetime.now()
    db.commit()
    db.refresh(db_dp_detail)
    return db_dp_detail


@router.delete("/{dp_detail_id}", summary="Elimina un singolo dettaglio")
def delete_dp_detail(dp_detail_id: int, db: Session = Depends(database.get_db)):
    """
    Elimina un dettaglio specifico del Daily Planning.
    Le associazioni con utenti e tipi di intervento vengono eliminate in cascata.
    """
    db_dp_detail = db.query(models.DPDetail).filter(models.DPDetail.id == dp_detail_id).first()
    if db_dp_detail is None:
        raise HTTPException(status_code=404, detail="Dettaglio DP non trovato")
    
    db.delete(db_dp_detail)
    db.commit()
    return {"message": "Dettaglio DP e le relative associazioni sono stati eliminati con successo"}
