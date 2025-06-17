from sqlalchemy.orm import Session, joinedload
from fastapi import BackgroundTasks
from typing import List
from collections import defaultdict

from app.routers import send_dp_report

from .. import models, schemas


def handle_dp_closing(db: Session, dp_testa_id: int, new_details_payload: List[schemas.DPDetailPayload], current_user: str, background_tasks: BackgroundTasks):
    """
    Servizio per gestire la chiusura e l'aggiornamento di un Daily Planning.
    """
    # 1. Recupera la testata del DP
    db_dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_testa_id).first()
    if not db_dp_testa:
        raise ValueError("DP Testa non trovata.")

    # 2. Recupera i dettagli attuali dal DB ("before" state)
    old_details = db.query(models.DPDetail).filter(models.DPDetail.id_testata == dp_testa_id).all()
    
    # Crea un set di assegnazioni (risorsa, id_sede) per un confronto rapido
    old_assignments = { (d.id_agpspm, d.id_sede) for d in old_details }

    # 3. Aggiorna il DB con i nuovi dettagli ("after" state) - Strategia "delete-and-replace"
    # Elimina i vecchi TI e Dettagli
    for detail in old_details:
        db.query(models.DPDetailTI).filter(models.DPDetailTI.id_dettaglio == detail.id).delete(synchronize_session=False)
    db.query(models.DPDetail).filter(models.DPDetail.id_testata == dp_testa_id).delete(synchronize_session=False)
    
    # Inserisci i nuovi dettagli dal payload
    new_assignments = set()
    for detail_data in new_details_payload:
        new_assignments.add((detail_data.id_agpspm, detail_data.id_sede))
        db_detail = models.DPDetail(
            id_testata=dp_testa_id,
            id_sede=detail_data.id_sede,
            id_agpspm=detail_data.id_agpspm,
            descrizionemanuale=detail_data.descrizionemanuale,
            note=detail_data.note,
            fasciaoraria=detail_data.fasciaoraria,
            materialedisponibile=detail_data.materialedisponibile,
            createdby=current_user,
            modifiedby=current_user
        )
        db.add(db_detail)
        db.flush() # Per ottenere l'ID del nuovo dettaglio
        # Aggiungi i tipi di intervento per il nuovo dettaglio
        for ti_data in detail_data.interventions:
            db.add(models.DPDetailTI(id_dettaglio=db_detail.id, **ti_data.dict()))
    
    # 4. Determina l'azione e lo stato finale
    final_state = ""
    if db_dp_testa.revisione == 0:
        # Prima chiusura
        final_state = "CHIUSO"
        db_dp_testa.stato = final_state
        db_dp_testa.revisione = 1
        background_tasks.add_task(send_dp_report.send_initial_dp_emails, dp_testa_id)
        
    else:
        # Chiusura successiva (modifica)
        final_state = "MODIFICATO"
        db_dp_testa.stato = final_state
        db_dp_testa.revisione += 1
        
        # 5. Calcola le differenze per notificare solo le risorse interessate
        affected_resources = {res for res, sede in (old_assignments - new_assignments) | (new_assignments - old_assignments) if res}
        
        if affected_resources:
            print(f"Modifiche rilevate per le risorse: {affected_resources}")
            background_tasks.add_task(send_dp_report.send_update_emails, dp_testa_id, list(affected_resources))
        else:
            print("Nessuna modifica rilevata nelle assegnazioni delle risorse.")
            
    db_dp_testa.modifiedby = current_user
    db.commit()

    return {"message": f"Daily Planning {dp_testa_id} finalizzato con successo. Stato: {final_state}", "stato": final_state}
