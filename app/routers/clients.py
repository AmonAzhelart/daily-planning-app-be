from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List

# Importa i modelli, gli schemi e le dipendenze necessarie
from .. import models, schemas, database
# Assumiamo di avere una dipendenza per l'autenticazione e la verifica dei ruoli

router = APIRouter(
)

# --- Endpoint per i Clienti ---

@router.get("/", response_model=List[schemas.ClienteWithSedi], summary="Ottieni tutti i clienti con le loro sedi")
def get_all_clients_with_sedi(db: Session = Depends(database.get_db)):
    clients = db.query(models.Cliente).options(joinedload(models.Cliente.sedi)).all()
    return clients

@router.post("/", response_model=schemas.ClienteWithSedi, status_code=status.HTTP_201_CREATED, summary="Crea un nuovo cliente")
def create_client(client_data: schemas.ClienteCreate, db: Session = Depends(database.get_db)):
    """
    Crea un nuovo cliente. Richiede la ragione sociale e almeno una sede.
    Se viene fornita solo una sede, la sua descrizione può essere uguale alla ragione sociale del cliente.
    """
    if not client_data.sedi:
        raise HTTPException(status_code=400, detail="Un cliente deve avere almeno una sede.")

    db_client = models.Cliente(ragione_sociale=client_data.ragione_sociale)
    db.add(db_client)
    db.flush()  # Ottieni l'ID del cliente prima di creare le sedi

    for sede_data in client_data.sedi:
        db_sede = models.Sede(descrizione=sede_data.descrizione, id_cliente=db_client.id)
        db.add(db_sede)
    
    db.commit()
    db.refresh(db_client)
    return db_client

@router.put("/{client_id}", response_model=schemas.Cliente, summary="Aggiorna la ragione sociale di un cliente")
def update_client(client_id: int, client_update: schemas.ClienteUpdate, db: Session = Depends(database.get_db)):
    """
    Aggiorna la ragione sociale di un cliente esistente.
    """
    db_client = db.query(models.Cliente).filter(models.Cliente.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")
    
    db_client.ragione_sociale = client_update.ragione_sociale
    db.commit()
    db.refresh(db_client)
    return db_client

@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Elimina un cliente")
def delete_client(client_id: int, db: Session = Depends(database.get_db)):
    """
    Elimina un cliente e tutte le sue sedi, solo se nessuna delle sedi è associata
    a un dettaglio del Daily Planning.
    """
    db_client = db.query(models.Cliente).options(joinedload(models.Cliente.sedi)).filter(models.Cliente.id == client_id).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente non trovato.")

    # Controlla se una qualsiasi delle sedi del cliente è in uso
    sedi_ids = [sede.id for sede in db_client.sedi]
    if sedi_ids:
        is_used = db.query(models.DPDetail).filter(models.DPDetail.id_sede.in_(sedi_ids)).first()
        if is_used:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Impossibile eliminare il cliente: una o più delle sue sedi sono utilizzate nel Daily Planning."
            )
            
    db.delete(db_client)
    db.commit()
    return

# --- Endpoint per le Sedi ---

@router.post("/sedi", response_model=schemas.Sede, status_code=status.HTTP_201_CREATED, summary="Aggiungi una nuova sede a un cliente")
def create_sede(sede_data: schemas.SedeCreate, db: Session = Depends(database.get_db)):
    """
    Aggiunge una nuova sede a un cliente esistente.
    """
    db_client = db.query(models.Cliente).filter(models.Cliente.id == sede_data.id_cliente).first()
    if not db_client:
        raise HTTPException(status_code=404, detail="Cliente non trovato per associare la nuova sede.")

    db_sede = models.Sede(**sede_data.dict())
    db.add(db_sede)
    db.commit()
    db.refresh(db_sede)
    return db_sede

@router.put("/sedi/{sede_id}", response_model=schemas.Sede, summary="Aggiorna la descrizione di una sede")
def update_sede(sede_id: int, sede_update: schemas.SedeUpdate, db: Session = Depends(database.get_db)):
    """
    Aggiorna la descrizione di una singola sede.
    """
    db_sede = db.query(models.Sede).filter(models.Sede.id == sede_id).first()
    if not db_sede:
        raise HTTPException(status_code=404, detail="Sede non trovata.")
        
    db_sede.descrizione = sede_update.descrizione
    db.commit()
    db.refresh(db_sede)
    return db_sede

@router.delete("/sedi/{sede_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Elimina una sede")
def delete_sede(sede_id: int, db: Session = Depends(database.get_db)):
    """
    Elimina una singola sede, solo se non è utilizzata nel Daily Planning.
    Inoltre, impedisce l'eliminazione se è l'ultima sede rimasta per un cliente.
    """
    db_sede = db.query(models.Sede).filter(models.Sede.id == sede_id).first()
    if not db_sede:
        raise HTTPException(status_code=404, detail="Sede non trovata.")

    # Controlla se la sede è in uso
    is_used = db.query(models.DPDetail).filter(models.DPDetail.id_sede == sede_id).first()
    if is_used:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Impossibile eliminare la sede: è utilizzata nel Daily Planning."
        )

    # Controlla se è l'ultima sede del cliente
    count_sedi = db.query(models.Sede).filter(models.Sede.id_cliente == db_sede.id_cliente).count()
    if count_sedi <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Impossibile eliminare l'ultima sede di un cliente."
        )

    db.delete(db_sede)
    db.commit()
    return