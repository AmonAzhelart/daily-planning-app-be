from collections import defaultdict
import io
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Set, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from app.routers import send_dp_report

from .. import models, schemas, database

router = APIRouter()

# --- GLI ENDPOINT GET, POST (create), E DELETE RIMANGONO INVARIATI ---

@router.post("/", response_model=schemas.DPTestaResponse)
def create_dp_testa(dp_testa: schemas.DPTestaCreate, db: Session = Depends(database.get_db)):
    """
    Crea una nuova testata del Daily Planning.
    """
    db_dp_testa = models.DPTesta(**dp_testa.dict(), created=datetime.now(), modified=datetime.now())
    db.add(db_dp_testa)
    db.commit()
    db.refresh(db_dp_testa)
    return db_dp_testa

@router.get("/{dp_testa_id}", response_model=schemas.DPTestaResponse)
def get_dp_testa(dp_testa_id: int, db: Session = Depends(database.get_db)):
    """
    Recupera una testata del Daily Planning tramite ID.
    """
    db_dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_testa_id).first()
    if db_dp_testa is None:
        raise HTTPException(status_code=404, detail="DP Testa non trovata")
    return db_dp_testa

@router.get("/", response_model=List[schemas.DPTestaResponse])
def get_all_dp_testas(db: Session = Depends(database.get_db)):
    """
    Recupera tutte le testate del Daily Planning.
    """
    return db.query(models.DPTesta).all()

# update per inviare mail custom
# @router.put("/{dp_testa_id}", response_model=schemas.DPTestaResponse)
# def update_daily_planning(
#     dp_testa_id: int, 
#     payload: schemas.DPTestaUpdatePayload, 
#     background_tasks: BackgroundTasks, 
#     db: Session = Depends(database.get_db)
# ):
#     """
#     Aggiorna un Daily Planning. Se 'details' è presente nel payload, aggiorna i dettagli
#     con una strategia "Delete-and-Replace". Altrimenti, aggiorna solo la testata.
#     Gestisce la finalizzazione e l'invio condizionale delle email.
#     """
#     db_dp_testa = db.query(models.DPTesta).options(
#         joinedload(models.DPTesta.dettagli).joinedload(models.DPDetail.tipi_interventi_dettaglio)
#     ).filter(models.DPTesta.id == dp_testa_id).first()

#     if not db_dp_testa:
#         raise HTTPException(status_code=404, detail="DP Testa non trovata")

#     old_state = db_dp_testa.stato
#     affected_resources = set()

#     # --- Aggiornamento dei dettagli (SOLO se forniti nel payload) ---
#     if payload.details is not None:
#         # --- Calcolo Robusto delle Risorse Impattate (PRIMA della modifica) ---
#         # Confronta l'intero set di attività per ogni risorsa, non solo le sedi.
#         old_resource_assignments = defaultdict(set)
#         for detail in db_dp_testa.dettagli:
#             if detail.id_agpspm:
#                 interventions = frozenset(
#                     (ti.id_tipi_interventi, ti.qta) for ti in detail.tipi_interventi_dettaglio
#                 )
#                 # Crea una tupla che rappresenta univocamente l'attività
#                 task_tuple = (
#                     detail.id_sede,
#                     detail.descrizionemanuale,
#                     detail.fasciaoraria,
#                     detail.materialedisponibile,
#                     detail.id_agpspm,
#                     detail.caluid,
#                     interventions
#                 )
#                 old_resource_assignments[detail.id_agpspm].add(task_tuple)

#         # Esegui la strategia "Delete-and-Replace"
#         for detail in db_dp_testa.dettagli:
#             db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == detail.id).delete(synchronize_session=False)
#         db.query(models.DPDetail).filter(models.DPDetail.id_testata == dp_testa_id).delete(synchronize_session=False)
        
#         # Crea i nuovi dettagli e calcola le NUOVE assegnazioni
#         new_resource_assignments = defaultdict(set)
#         for detail_data in payload.details:
#             db_detail = models.DPDetail(
#                 caluid=detail_data.caluid,
#                 id_testata=dp_testa_id,
#                 id_sede=detail_data.id_sede,
#                 id_agpspm=detail_data.id_agpspm,
#                 descrizionemanuale=detail_data.descrizionemanuale,
#                 note=detail_data.note,
#                 fasciaoraria=detail_data.fasciaoraria,
#                 materialedisponibile=detail_data.materialedisponibile,
#                 createdby=payload.modifiedby,
#                 modifiedby=payload.modifiedby
#             )
#             db.add(db_detail)
#             db.flush()
            
#             # Aggiungi la nuova attività al set per il confronto
#             if detail_data.id_agpspm:
#                 interventions = frozenset(
#                     (ti.id_tipi_interventi, ti.qta) for ti in detail_data.interventions
#                 ) if detail_data.interventions else frozenset()
#                 task_tuple = (
#                     detail_data.caluid,
#                     detail_data.id_agpspm,
#                     detail_data.id_sede,
#                     detail_data.descrizionemanuale,
#                     detail_data.fasciaoraria,
#                     detail_data.materialedisponibile,
#                     interventions
#                 )
#                 new_resource_assignments[detail_data.id_agpspm].add(task_tuple)
            
#             if detail_data.interventions:
#                 for ti_data in detail_data.interventions:
#                     db.add(models.DPDetailTI(id_dettaglio=db_detail.id, **ti_data.dict()))
        
#         # Confronta i set di attività vecchie e nuove per trovare le risorse impattate
#         all_involved_resources = set(old_resource_assignments.keys()) | set(new_resource_assignments.keys())
#         for resource_email in all_involved_resources:
#             if old_resource_assignments.get(resource_email, set()) != new_resource_assignments.get(resource_email, set()):
#                 affected_resources.add(resource_email)

#     # --- Logica Condizionale per l'Invio Email ---
#     new_state = payload.stato
    
#     if new_state == models.DPStatus.CHIUSO and old_state != models.DPStatus.CHIUSO:
#         db_dp_testa.revisione = 1
#         background_tasks.add_task(send_dp_report.send_initial_dp_emails, dp_testa_id)
#         print(f"DP {dp_testa_id} chiuso per la prima volta. Avvio invio email iniziali.")

#     elif new_state == models.DPStatus.MODIFICATO and old_state != models.DPStatus.MODIFICATO:
#         db_dp_testa.revisione = (db_dp_testa.revisione or 0) + 1
#         if affected_resources:
#             background_tasks.add_task(send_dp_report.send_update_emails, dp_testa_id, list(affected_resources))
#             print(f"DP {dp_testa_id} modificato. Avvio invio email di aggiornamento per: {affected_resources}")
#         else:
#             print(f"DP {dp_testa_id} modificato, ma nessuna modifica rilevata nelle assegnazioni delle risorse.")
            
#     # Aggiornamento finale della testata (avviene sempre)
#     db_dp_testa.stato = new_state
#     db_dp_testa.modifiedby = payload.modifiedby
#     db_dp_testa.modified = datetime.now()

#     db.commit()
#     db.refresh(db_dp_testa)
    
#     return db_dp_testa

@router.put("/{dp_testa_id}", response_model=schemas.DPTestaResponse)
def update_daily_planning(
    dp_testa_id: int, 
    payload: schemas.DPTestaUpdatePayload, 
    background_tasks: BackgroundTasks, 
    db: Session = Depends(database.get_db)
):
    """
    Aggiorna un Daily Planning. Se 'details' è presente nel payload, aggiorna i dettagli
    con una strategia "Delete-and-Replace". Altrimenti, aggiorna solo la testata.
    Gestisce la finalizzazione e l'invio condizionale delle email.
    Questa versione include l'invio di email personalizzate in base alle risorse impattate.
    """
    db_dp_testa = db.query(models.DPTesta).options(
        # Carica i dettagli e i loro tipi di intervento per una serializzazione completa
        joinedload(models.DPTesta.dettagli).joinedload(models.DPDetail.tipi_interventi_dettaglio)
    ).filter(models.DPTesta.id == dp_testa_id).first()

    if not db_dp_testa:
        raise HTTPException(status_code=404, detail="DP Testa non trovata")

    old_state = db_dp_testa.stato
    affected_resources = set()

    # --- Aggiornamento dei dettagli (SOLO se forniti nel payload) ---
    if payload.details is not None:
        # --- Calcolo Robusto delle Risorse Impattate (PRIMA della modifica) ---
        # Confronta l'intero set di attività per ogni risorsa.
        old_resource_assignments = defaultdict(set)
        for detail in db_dp_testa.dettagli:
            if detail.id_agpspm:
                interventions = frozenset(
                    # Crea un frozenset di tuple (id_tipi_interventi, qta) per ogni intervento
                    (ti.id_tipi_interventi, ti.qta) for ti in detail.tipi_interventi_dettaglio
                )
                # Crea una tupla che rappresenta univocamente l'attività per la risorsa
                task_tuple = (
                    detail.id_sede,
                    detail.descrizionemanuale,
                    detail.fasciaoraria,
                    detail.materialedisponibile,
                    detail.id_agpspm,
                    detail.caluid,
                    interventions
                )
                old_resource_assignments[detail.id_agpspm].add(task_tuple)

        # Esegui la strategia "Delete-and-Replace" per i dettagli e i loro interventi
        # Prima elimino gli interventi legati ai dettagli esistenti
        for detail in db_dp_testa.dettagli:
            db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == detail.id).delete(synchronize_session=False)
        # Poi elimino i dettagli stessi
        db.query(models.DPDetail).filter(models.DPDetail.id_testata == dp_testa_id).delete(synchronize_session=False)
        
        # Crea i nuovi dettagli e calcola le NUOVE assegnazioni per il confronto
        new_resource_assignments = defaultdict(set)
        for detail_data in payload.details:
            db_detail = models.DPDetail(
                caluid=detail_data.caluid,
                id_testata=dp_testa_id,
                id_sede=detail_data.id_sede,
                id_agpspm=detail_data.id_agpspm,
                descrizionemanuale=detail_data.descrizionemanuale,
                note=detail_data.note,
                fasciaoraria=detail_data.fasciaoraria,
                materialedisponibile=detail_data.materialedisponibile,
                createdby=payload.modifiedby,
                modifiedby=payload.modifiedby
            )
            db.add(db_detail)
            db.flush() # Assicura che db_detail.id sia popolato prima di aggiungere i tipi di intervento
            
            # Aggiungi la nuova attività al set per il confronto
            if detail_data.id_agpspm:
                interventions = frozenset(
                    (ti.id_tipi_interventi, ti.qta) for ti in detail_data.interventions
                ) if detail_data.interventions else frozenset()
                task_tuple = (
                    detail_data.caluid,
                    detail_data.id_agpspm,
                    detail_data.id_sede,
                    detail_data.descrizionemanuale,
                    detail_data.fasciaoraria,
                    detail_data.materialedisponibile,
                    interventions
                )
                new_resource_assignments[detail_data.id_agpspm].add(task_tuple)
            
            # Aggiungi i tipi di intervento per il nuovo dettaglio
            if detail_data.interventions:
                for ti_data in detail_data.interventions:
                    db.add(models.DPDetailTI(id_dettaglio=db_detail.id, **ti_data.dict()))
        
        # Confronta i set di attività vecchie e nuove per trovare le risorse impattate
        # Tutte le risorse coinvolte (vecchie e nuove)
        all_involved_resources = set(old_resource_assignments.keys()) | set(new_resource_assignments.keys())
        for resource_email in all_involved_resources:
            # Se le assegnazioni per una risorsa sono diverse (o la risorsa è stata aggiunta/rimossa)
            if old_resource_assignments.get(resource_email, set()) != new_resource_assignments.get(resource_email, set()):
                affected_resources.add(resource_email)

    # --- Logica Condizionale per l'Invio Email ---
    new_state = payload.stato
    
    if new_state == models.DPStatus.CHIUSO and old_state != models.DPStatus.CHIUSO:
        # Se il DP viene chiuso per la prima volta
        db_dp_testa.revisione = 1
        background_tasks.add_task(send_dp_report.send_initial_dp_emails, dp_testa_id)
        print(f"DP {dp_testa_id} chiuso per la prima volta. Avvio invio email iniziali.")

    elif new_state == models.DPStatus.MODIFICATO and old_state != models.DPStatus.MODIFICATO:
        # Se il DP viene modificato e non era già in stato MODIFICATO
        db_dp_testa.revisione = (db_dp_testa.revisione or 0) + 1 # Incrementa la revisione
        if affected_resources:
            # Invia email di aggiornamento solo alle risorse che hanno avuto modifiche nelle loro assegnazioni
            background_tasks.add_task(send_dp_report.send_update_emails, dp_testa_id, list(affected_resources))
            print(f"DP {dp_testa_id} modificato. Avvio invio email di aggiornamento per: {affected_resources}")
        else:
            print(f"DP {dp_testa_id} modificato, ma nessuna modifica rilevata nelle assegnazioni delle risorse. Nessuna email di aggiornamento personalizzata inviata.")
            
    # Aggiornamento finale della testata (avviene sempre)
    db_dp_testa.stato = new_state
    db_dp_testa.modifiedby = payload.modifiedby
    db_dp_testa.modified = datetime.now()

    db.commit()
    db.refresh(db_dp_testa) # Ricarica l'oggetto per assicurare che le relazioni siano aggiornate

    return db_dp_testa

@router.delete("/{dp_testa_id}")
def delete_dp_testa(dp_testa_id: int, db: Session = Depends(database.get_db)):
    db_dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_testa_id).first()
    if db_dp_testa is None:
        raise HTTPException(status_code=404, detail="DP Testa non trovata")

    # Elimina prima i figli (DPDetailTI) e poi i padri (DPDetail)
    details_to_delete = db.query(models.DPDetail).filter(models.DPDetail.id_testata == dp_testa_id).all()
    for detail in details_to_delete:
        db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == detail.id).delete(synchronize_session=False)

    db.query(models.DPDetail).filter(models.DPDetail.id_testata == dp_testa_id).delete(synchronize_session=False)

    db.delete(db_dp_testa)
    db.commit()
    return {"message": "DP Testa e dettagli correlati eliminati con successo"}


@router.get("/get-pdf-report/{dp_testa_id}", response_class=StreamingResponse)
def get_pdf_report(dp_testa_id: int, db: Session = Depends(database.get_db)):
    """
    Genera e restituisce il report PDF completo per una data testata del Daily Planning.
    Il file restituito è lo stesso che verrebbe inviato via email agli uffici.
    """
    # 1. Recupera la testata del DP
    db_dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_testa_id).first()
    if not db_dp_testa:
        raise HTTPException(status_code=404, detail="DP Testa non trovata")

    # 2. Recupera tutti i dettagli associati con caricamento 'eager' delle relazioni
    #    Questo è fondamentale per evitare errori di sessione durante la generazione del PDF.
    all_details = db.query(models.DPDetail).options(
        joinedload(models.DPDetail.sedi).joinedload(models.VistaClientiSedi.id_sede),
        joinedload(models.DPDetail.agpspm_user),
        joinedload(models.DPDetail.tipi_interventi_dettaglio).joinedload(models.DPDetailTI.tipo_intervento_ref)
    ).filter(models.DPDetail.id_testata == dp_testa_id).all()

    # 3. Prepara il buffer in memoria per il PDF
    pdf_buffer = io.BytesIO()

    # 4. Definisci il suffisso del titolo e il nome del file
    revision_number = db_dp_testa.revisione -1 if db_dp_testa.revisione >0 else db_dp_testa.revisione or 1
    title_suffix = f"Completo - Rev. {revision_number}"
    filename_date = db_dp_testa.giorno.strftime('%Y-%m-%d')
    download_filename = f"{filename_date}_rev{revision_number}.pdf"

    # 5. Genera il PDF utilizzando la funzione esistente, scrivendo nel buffer
    send_dp_report.generate_dp_pdf(
        dp_testa=db_dp_testa,
        dp_details=all_details,
        file_path=pdf_buffer,  # Scrive direttamente nel buffer in memoria
        report_type='office',  # Genera la versione completa/per l'ufficio
        title_suffix=title_suffix
    )

    # 6. Riporta il cursore del buffer all'inizio per la lettura
    pdf_buffer.seek(0)

    # 7. Restituisci una StreamingResponse
    return StreamingResponse(
        pdf_buffer,
        media_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{download_filename}"'}
    )
