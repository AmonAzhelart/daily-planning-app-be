from fastapi import APIRouter, Depends, HTTPException, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, selectinload
from typing import List, Set

from app.routers import send_dp_report
from .. import models, schemas, database
from datetime import datetime
from collections import defaultdict
import io
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
# Assicurati che questo import sia corretto per il tuo progetto
# from app.services import send_dp_report 

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


@router.post("/", response_model=schemas.DPTestaResponse)
def create_dp_testa(dp_testa: schemas.DPTestaCreate, db: Session = Depends(database.get_db)):
    db_dp_testa = models.DPTesta(**dp_testa.dict())
    db.add(db_dp_testa)
    db.commit()
    db.refresh(db_dp_testa)
    return db_dp_testa


@router.get("/", response_model=List[schemas.DPTestaResponse])
def get_all_dp_testata(db: Session = Depends(database.get_db)):
    return db.query(models.DPTesta).all()


@router.get("/{dp_testa_id}", response_model=schemas.DPTestaResponse)
def get_dp_testa(dp_testa_id: int, db: Session = Depends(database.get_db)):
    db_dp_testa = db.query(models.DPTesta).options(joinedload(models.DPTesta.dettagli)).filter(models.DPTesta.id == dp_testa_id).first()
    if db_dp_testa is None:
        raise HTTPException(status_code=404, detail="Testata DP non trovata")
    return db_dp_testa

@router.put("/{dp_testa_id}", response_model=schemas.DPTestaResponse, summary="Aggiornamento completo del Daily Planning con logica email")
def update_daily_planning(dp_testa_id: int, payload: schemas.DPTestaUpdatePayload, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    db_dp_testa = db.query(models.DPTesta).options(
        joinedload(models.DPTesta.dettagli).joinedload(models.DPDetail.agpspm_associations).joinedload(models.DPDetailAGPSPM.agpspm_user),
        joinedload(models.DPTesta.dettagli).joinedload(models.DPDetail.tipi_interventi_dettaglio)
    ).filter(models.DPTesta.id == dp_testa_id).first()

    if not db_dp_testa:
        raise HTTPException(status_code=404, detail="DP Testa non trovata")

    old_state = db_dp_testa.stato

    # --- Calcolo Robusto delle Risorse Impattate (PRIMA della modifica) ---
    old_resource_assignments = defaultdict(set)
    if payload.details is not None:
        for detail in db_dp_testa.dettagli:
            interventions = frozenset((ti.id_tipi_interventi, ti.qta) for ti in detail.tipi_interventi_dettaglio)
            task_tuple = (
                detail.id_sede, detail.descrizionemanuale, detail.fasciaoraria,
                detail.materialedisponibile, detail.caluid, interventions
            )
            for user in detail.agpspm_users:
                old_resource_assignments[user.username].add(task_tuple)

    # --- Aggiornamento Testata ---
    db_dp_testa.stato = payload.stato
    db_dp_testa.modifiedby = payload.modifiedby
    db_dp_testa.modified = datetime.now()
    if old_state == models.DPStatus.APERTO and payload.stato in [models.DPStatus.CHIUSO, models.DPStatus.MODIFICATO]:
        db_dp_testa.revisione = (db_dp_testa.revisione or 0) + 1

    # --- Aggiornamento dei dettagli (Create, Update, Delete) ---
    new_resource_assignments = defaultdict(set)
    if payload.details is not None:
        existing_detail_ids = {d.id for d in db_dp_testa.dettagli}
        incoming_detail_ids = {d.id for d in payload.details if d.id is not None}
        ids_to_delete = existing_detail_ids - incoming_detail_ids
        if ids_to_delete:
            db.query(models.DPDetail).filter(models.DPDetail.id.in_(ids_to_delete)).delete(synchronize_session=False)

        for detail_data in payload.details:
            db_detail = None
            if detail_data.id is not None:
                db_detail = db.query(models.DPDetail).filter(models.DPDetail.id == detail_data.id).first()
            
            if not db_detail:
                db_detail = models.DPDetail(id_testata=dp_testa_id, createdby=payload.modifiedby)
                db.add(db_detail)

            db_detail.caluid = detail_data.caluid
            db_detail.id_sede = detail_data.id_sede
            db_detail.note = detail_data.note
            db_detail.fasciaoraria = detail_data.fasciaoraria
            db_detail.materialedisponibile = detail_data.materialedisponibile
            db_detail.descrizionemanuale = detail_data.descrizionemanuale
            db_detail.modifiedby = payload.modifiedby
            db_detail.modified = datetime.now()
            
            validated_users = get_and_validate_agpspm_users(db, detail_data.agpspm_users)
            db_detail.agpspm_users = validated_users

            db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == db_detail.id).delete(synchronize_session=False)
            db.flush()
            for ti_data in detail_data.interventions:
                db.add(models.DPDetailTI(id_dettaglio=db_detail.id, **ti_data.dict()))
            
            interventions = frozenset((ti.id_tipi_interventi, ti.qta) for ti in detail_data.interventions)
            task_tuple = (
                detail_data.id_sede, detail_data.descrizionemanuale, detail_data.fasciaoraria,
                detail_data.materialedisponibile, detail_data.caluid, interventions
            )
            for username in detail_data.agpspm_users:
                new_resource_assignments[username].add(task_tuple)

    # --- Logica Condizionale per l'Invio Email ---
    all_involved_resources = set(old_resource_assignments.keys()) | set(new_resource_assignments.keys())
    affected_resources = {res for res in all_involved_resources if old_resource_assignments.get(res, set()) != new_resource_assignments.get(res, set())}
    
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

    db.commit()
    db.refresh(db_dp_testa) # Ricarica l'oggetto per assicurare che le relazioni siano aggiornate

    return db_dp_testa



@router.delete("/{dp_testa_id}")
def delete_dp_testa(dp_testa_id: int, db: Session = Depends(database.get_db)):
    db_dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_testa_id).first()
    if db_dp_testa is None:
        raise HTTPException(status_code=404, detail="Testata DP non trovata")
    db.delete(db_dp_testa)
    db.commit()
    return {"message": "Testata DP e tutti i dettagli correlati eliminati con successo"}


@router.get("/get-pdf-report/{dp_testa_id}", summary="Genera un report PDF per il Daily Planning")
def get_pdf_report(dp_testa_id: int, db: Session = Depends(database.get_db)):
    """
    Genera e restituisce il report PDF completo per una data testata del Daily Planning.
    Il file restituito è lo stesso che verrebbe inviato via email agli uffici.
    """
    db_dp_testa = db.query(models.DPTesta).options(
        selectinload(models.DPTesta.dettagli)
        .selectinload(models.DPDetail.agpspm_associations)
        .selectinload(models.DPDetailAGPSPM.agpspm_user),
        selectinload(models.DPTesta.dettagli)
        .selectinload(models.DPDetail.sedi)
        .selectinload(models.Sede.cliente_ref),
        selectinload(models.DPTesta.dettagli)
        .selectinload(models.DPDetail.tipi_interventi_dettaglio)
        .selectinload(models.DPDetailTI.tipo_intervento_ref)
    ).filter(models.DPTesta.id == dp_testa_id).first()

    if not db_dp_testa:
        raise HTTPException(status_code=404, detail="DP Testa non trovata")

    # 3. Prepara il buffer in memoria per il PDF
    pdf_buffer = io.BytesIO()

    # 4. Definisci il suffisso del titolo e il nome del file
    revision_number = db_dp_testa.revisione -1 if db_dp_testa.revisione > 0 else db_dp_testa.revisione or 1
    title_suffix = f"Completo - Rev. {revision_number}"
    filename_date = db_dp_testa.giorno.strftime('%Y-%m-%d')
    download_filename = f"{filename_date}_rev{revision_number}.pdf"

    # 5. Genera il PDF utilizzando la funzione esistente, scrivendo nel buffer
    send_dp_report.generate_dp_pdf(
        dp_testa=db_dp_testa,
        dp_details=db_dp_testa.dettagli,
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