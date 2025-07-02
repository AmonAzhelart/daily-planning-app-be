import os
import httpx
import json
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter()

# Variabili d'ambiente per le credenziali Zoho
ZOHO_CLIENT_ID = os.getenv("ZOHO_CLIENT_ID", "1000.AO37HON1DNM4XK1242RTYDICGSMG0E")
ZOHO_CLIENT_SECRET = os.getenv("ZOHO_CLIENT_SECRET", "35e920b349fe71e6a1efa71ca9c6c77e6d8026fe35")
# ZOHO_REDIRECT_URI: Impostato per lo sviluppo in localhost.
# RICORDA DI CAMBIARLO IN PRODUZIONE E AGGIORNARLO NELLA CONSOLE SVILUPPATORI ZOHO.
ZOHO_REDIRECT_URI = os.getenv("ZOHO_REDIRECT_URI", "http://127.0.0.1:8000/oauth2/callback")

# --- Determina l'URL base di Zoho in base al Data Center (EU in questo caso) ---
# Se il tuo account Zoho è basato su un Data Center diverso (es. .com, .in, .au), cambia questo URL.
ZOHO_ACCOUNTS_URL = os.getenv("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.eu")
# URL specifico per le API di Zoho Calendar come da documentazione: https://calendar.zoho.eu/api
ZOHO_API_URL = os.getenv("ZOHO_API_URL", "https://calendar.zoho.eu/api")


def save_zoho_tokens(db: Session, access_token: str, refresh_token: Optional[str], expires_in_seconds: int):
    """
    Salva o aggiorna l'access token Zoho nel database.
    Il refresh token viene salvato se fornito.
    """
    existing_token_entry = db.query(models.ZohoToken).first()

    # Rinfresca 5 minuti prima della scadenza reale per avere un buffer
    expires_at = datetime.now() + timedelta(seconds=expires_in_seconds - 300)

    if existing_token_entry:
        existing_token_entry.access_token = access_token
        existing_token_entry.expires_at = expires_at
        # Aggiorna il refresh_token solo se ne viene fornito uno nuovo
        # (ad esempio, al primo login OAuth).
        if refresh_token:
            existing_token_entry.refresh_token = refresh_token
        print(f"Access Token aggiornato nel DB. Scade alle: {existing_token_entry.expires_at}")
    else:
        new_token_entry = models.ZohoToken(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        db.add(new_token_entry)
        print(f"Nuovo Access Token salvato nel DB. Scade alle: {new_token_entry.expires_at}")
    db.commit()
    db.refresh(existing_token_entry or new_token_entry)

def get_current_zoho_tokens(db: Session) -> Optional[models.ZohoToken]:
    """
    Recupera l'access token Zoho dal database.
    """
    return db.query(models.ZohoToken).first()

async def refresh_zoho_access_token_if_needed(db: Session = Depends(database.get_db)):
    """
    Controlla se l'access token è scaduto o sta per scadere.
    Se scaduto e un refresh token è disponibile, tenta di ottenere un nuovo access token.
    Altrimenti, richiede una nuova autorizzazione all'utente.
    """
    current_token_entry = get_current_zoho_tokens(db)

    # Se non ci sono token nel DB o l'access token è scaduto
    if not current_token_entry or current_token_entry.expires_at <= datetime.now():
        print("Access token assente o scaduto.")
        if current_token_entry and current_token_entry.refresh_token:
            print("Tento di refreshare l'access token usando il refresh token.")
            refresh_token_value = current_token_entry.refresh_token
            token_url = f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": ZOHO_CLIENT_ID,
                "client_secret": ZOHO_CLIENT_SECRET,
                "redirect_uri": ZOHO_REDIRECT_URI, # Inclusa come da documentazione Zoho
                "refresh_token": refresh_token_value,
                "scope": "ZohoCalendar.calendar.ALL,ZohoCalendar.event.ALL,AaaServer.profile.ALL" # Deve corrispondere allo scope iniziale
            }
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.post(token_url, data=data)
                    response.raise_for_status() # Solleva un'eccezione per errori HTTP (4xx o 5xx)
                    token_info = response.json()

                    new_access_token = token_info.get("access_token")
                    expires_in = token_info.get("expires_in") # Tipicamente 3600 secondi (1 ora)

                    if not new_access_token or not expires_in:
                        raise HTTPException(status_code=500, detail="Nuovo access token o expires_in mancante dalla risposta di refresh.")
                    
                    # Salva il nuovo access token, riutilizzando il refresh token esistente
                    save_zoho_tokens(db, new_access_token, current_token_entry.refresh_token, expires_in)
                    print(f"Access token rinnovato con successo. Nuovo token scade alle: {datetime.now() + timedelta(seconds=expires_in - 300)}")
                    return new_access_token

                except httpx.HTTPStatusError as e:
                    print(f"Errore durante il refresh del token: {e.response.text}")
                    # Se il refresh fallisce, significa che il refresh token potrebbe essere non valido o revocato.
                    raise HTTPException(
                        status_code=401,
                        detail=f"Refresh token non valido o scaduto. È necessaria una nuova autorizzazione di Zoho. Dettagli: {e.response.text}. Visita /zoho_oauth_initiate."
                    )
                except Exception as e:
                    print(f"Errore inatteso durante il refresh del token: {str(e)}")
                    raise HTTPException(status_code=500, detail=f"Errore inatteso durante il refresh del token: {str(e)}")
        else:
            print("Refresh token non disponibile. Richiesta nuova autorizzazione all'utente.")
            raise HTTPException(
                status_code=401,
                detail="Access token assente o scaduto e refresh token non disponibile. È necessaria una nuova autorizzazione di Zoho. Visita /zoho_oauth_initiate."
            )

    # Se l'access token è ancora valido, lo restituisce
    print(f"Access token valido fino a: {current_token_entry.expires_at}")
    return current_token_entry.access_token

# Endpoint simulati per le "viste" e le funzioni complesse.
# Questi endpoint interagiscono con il tuo database locale.

@router.get("/health", summary="Health Check")
def health_check():
    """
    Un endpoint semplice per verificare se l'API è attiva e risponde.
    """
    return {"status": "ok", "message": "Backend is running!"}


@router.get("/clients/", response_model=List[Dict[str, Any]])
def get_clients_view(db: Session = Depends(database.get_db)):
    """
    Recupera i clienti e le loro sedi simulando la vista `dp_v_clienti`.
    La vista `dp_v_clienti` seleziona `id_sede`, `cliente` (ragione_sociale), `sede` (descrizione sede o "(la stessa)").
    """
    try:
        # Questa query cerca di replicare la logica della tua vista SQL per `dp_v_clienti`
        result = db.query(models.VistaClientiSedi).all()

        clients_data = []
        for r in result:
            if(r is not None):
                clients_data.append({
                    "id_sede": r.id_sede if r.id_sede is not None else 0,
                    "cliente": r.cliente,
                    "sede": r.sede
                })
        return clients_data
    except Exception as e:
        print(f"Errore durante il recupero dei clienti dalla vista simulata: {e}")
        # Fallback a dati simulati se la query alla vista fallisce
        return [
            {"id_sede": 1, "cliente": "Cliente Alpha Srl", "sede": "(la stessa)"},
            {"id_sede": 2, "cliente": "Beta Spa", "sede": "Sede Roma"}
        ]


@router.get("/intervention_types/", response_model=List[schemas.TipoInterventoResponse])
def get_intervention_types_view(db: Session = Depends(database.get_db)):
    """
    Recupera le tipologie di intervento dalla tabella `tipi_interventi`.
    """
    try:
        ti = db.query(models.TipoIntervento).all()
        return ti
    except Exception as e:
        print(f"Errore durante il recupero delle tipologie di intervento: {e}")
        # Fallback a dati simulati
        return [
            {"id": 1, "descrizione": "Visita"},
            {"id": 2, "descrizione": "Intervento Chirurgico"},
            {"id": 3, "descrizione": "Controllo"}
        ]

@router.get("/resources/", response_model=List[schemas.OauthUserResponse])
def get_resources_view(db: Session = Depends(database.get_db)):
    """
    Recupera le risorse (AG/PS/PM) simulando la vista `dp_v_agpspm`.
    La vista `dp_v_agpspm` filtra per `hide_is_search` = 0 e `role` in (3,6).
    """
    try:
        resources = db.query(models.DpVApspm).all()
        return resources
    except Exception as e:
        print(f"Errore durante il recupero delle risorse: {e}")
        # Fallback a dati simulati
        return [
            {"username": "carlo.rossi", "first_name": "Carlo", "last_name": "Rossi", "role": 3, "active": 1, "super": 0, "gestione_congressi": 0, "hide_is_search": 0, "parent_id": None},
            {"username": "sara.verdi", "first_name": "Sara", "last_name": "Verdi", "role": 6, "active": 1, "super": 0, "gestione_congressi": 0, "hide_is_search": 0, "parent_id": None}
        ]


@router.get("/zoho_oauth_initiate/", summary="Inizia il processo OAuth2 di Zoho (richiede interazione browser)")
async def zoho_oauth_initiate():
    """
    Genera l'URL di autorizzazione Zoho. L'utente deve visitare questo URL nel browser,
    effettuare l'accesso (se non già loggato) e dare il consenso all'applicazione.
    Zoho reindirizzerà quindi al `redirect_uri` con il `code` di autorizzazione.
    """
    # ***MODIFICATO: Scope per Zoho Calendar API come da documentazione (ZohoCalendar.events.READ).***
    scope = "ZohoCalendar.calendar.ALL,ZohoCalendar.event.ALL,AaaServer.profile.ALL"
    auth_url = (
        f"{ZOHO_ACCOUNTS_URL}/oauth/v2/auth?"
        f"scope={scope}"
        f"&client_id={ZOHO_CLIENT_ID}"
        f"&response_type=code"
        f"&access_type=offline" # Manteniamo questo per indicare a Zoho che desideriamo un refresh token (anche se non lo restituisce)
        f"&redirect_uri={ZOHO_REDIRECT_URI}"
    )
    return {"message": "Visita questo URL nel tuo browser per autorizzare l'applicazione e ottenere il codice iniziale. Sarai reindirizzato a /oauth2/callback", "auth_url": auth_url}

# --- Endpoint di callback per Zoho OAuth2 ---
@router.get("/oauth2/callback", summary="Endpoint di callback per Zoho OAuth2 (gestisce il codice di autorizzazione)")
async def zoho_oauth_callback(code: str = Query(...), db: Session = Depends(database.get_db)):
    """
    Questo endpoint viene chiamato da Zoho dopo che l'utente ha autorizzato la tua applicazione.
    Riceve il 'code' di autorizzazione e lo scambia per l'access_token (e opzionalmente refresh_token, se fornito).
    I token vengono poi salvati nel database.
    """
    token_url = f"{ZOHO_ACCOUNTS_URL}/oauth/v2/token"
    # ***MODIFICATO: Scope nel POST di callback, deve corrispondere a quello della richiesta iniziale.***
    data = {
        "grant_type": "authorization_code",
        "client_id": ZOHO_CLIENT_ID,
        "client_secret": ZOHO_CLIENT_SECRET,
        "redirect_uri": ZOHO_REDIRECT_URI,
        "code": code,
        "scope": "ZohoCalendar.calendar.ALL,ZohoCalendar.event.ALL,AaaServer.profile.ALL" # Deve corrispondere allo scope della richiesta iniziale
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=data)

            print(f"DEBUG: Status Code da Zoho token endpoint (callback): {response.status_code}")
            print(f"DEBUG: Headers da Zoho token endpoint (callback): {response.headers}")
            print(f"DEBUG: Body raw da Zoho token endpoint (callback): {response.text}")

            response.raise_for_status()
            token_info = response.json()

            access_token = token_info.get("access_token")
            # Leggiamo il refresh_token se c'è, ma non è obbligatorio, dato che hai detto che non viene restituito.
            refresh_token = token_info.get("refresh_token")
            expires_in = token_info.get("expires_in")

            if not access_token:
                raise HTTPException(status_code=500, detail="Access token mancante dalla risposta di Zoho.")

            # Salviamo l'access token e il refresh token (se disponibile) nel database.
            save_zoho_tokens(db, access_token,refresh_token, expires_in)

            return {"message": "Access Token Zoho ottenuto e salvato nel database. Ora puoi chiamare /get_zoho_events."}

        except httpx.HTTPStatusError as e:
            print(f"Errore durante lo scambio del token: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Errore durante lo scambio del token: {e.response.text}")
        except Exception as e:
            print(f"Errore inatteso: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Errore inatteso: {str(e)}")

# ***NUOVA FUNZIONE: Recupera la lista dei calendari disponibili per l'utente***
async def fetch_zoho_calendars(access_token: str) -> List[Dict[str, Any]]:
    """
    Recupera la lista dei calendari disponibili dall'API di Zoho Calendar.
    """
    calendars_api_url = f"{ZOHO_API_URL}/v1/calendars?category=all"

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(calendars_api_url, headers=headers)
            response.raise_for_status()
            calendars_data = response.json()

            print(f"Risposta raw da Zoho Calendar (Calendars List): {json.dumps(calendars_data, indent=2)}")
            # Dalla documentazione, i calendari sono spesso sotto la chiave 'data'
            return calendars_data.get("data", [])
        except httpx.HTTPStatusError as e:
            print(f"Errore durante il recupero dei calendari da Zoho Calendar API: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Errore Zoho Calendar API (list calendars): {e.response.text}")
        except Exception as e:
            print(f"Errore inatteso durante il recupero dei calendari Zoho: {e}")
            raise HTTPException(status_code=500, detail=f"Errore inatteso durante il recupero dei calendari Zoho: {str(e)}")

# ***NUOVO ENDPOINT: Per il frontend per ottenere la lista dei calendari***
@router.get("/get_zoho_calendars", summary="Recupera la lista dei calendari Zoho disponibili per l'utente")
async def get_zoho_calendars(db: Session = Depends(database.get_db)):
    """
    Espone la lista dei calendari Zoho Calendar all'applicazione frontend.
    """
    try:
        current_access_token = await refresh_zoho_access_token_if_needed(db) # Ottiene l'access token
    except HTTPException as e:
        raise e # Rilancia l'eccezione se il token non è disponibile/valido

    try:
        calendars = await fetch_zoho_calendars(current_access_token)
        return {"message": "Calendari Zoho recuperati con successo.", "calendars": calendars}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante il recupero dei calendari: {str(e)}")


# --- Funzione per recuperare gli eventi da Zoho Calendar (chiamata interna) ---
async def fetch_zoho_calendar_events(access_token: str, calendar_uid: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
    """
    Recupera eventi da un calendario Zoho specifico (proprio o condiviso) usando l'access token.
    Richiede il CALENDAR_UID.
    """
    calendar_api_url = f"{ZOHO_API_URL}/v1/calendars/{calendar_uid}/events"

    # ***MODIFICATO: `range` come parametro JSON stringa con date
    # Questo è il formato specifico richiesto dalla documentazione di Zoho Calendar API per il parametro `range`.
    range_obj = {
        "start": start_time.strftime("%Y%m%d"), # Formato YYYYMMDD
        "end": end_time.strftime("%Y%m%d")      # Formato YYYYMMDD
    }

    params = {
        "range": json.dumps(range_obj)
    }

    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(calendar_api_url, headers=headers, params=params)
            response.raise_for_status()
            events_data = response.json()

            print(f"Risposta raw da Zoho Calendar API per {calendar_uid}: {json.dumps(events_data, indent=2)}")
            # Dalla documentazione, gli eventi sono spesso sotto la chiave 'events'
            return events_data.get("events", [])
        except httpx.HTTPStatusError as e:
            print(f"Errore durante il recupero degli eventi da Zoho Calendar API: {e.response.text}")
            raise HTTPException(status_code=e.response.status_code, detail=f"Errore Zoho Calendar API: {e.response.text}")
        except Exception as e:
            print(f"Errore inatteso durante il recupero degli eventi Zoho: {e}")
            raise HTTPException(status_code=500, detail=f"Errore inatteso durante il recupero degli eventi Zoho: {str(e)}")

# --- Endpoint principale per l'importazione degli eventi di Zoho Calendar ---
@router.post("/get_zoho_events", summary="Recupera e importa eventi da Zoho Calendar gestendo l'autenticazione", response_model=List[Dict[str, Any]]) # Modificato per restituire una lista di dict
async def get_zoho_events(
    calendar_uid: str = Query(..., description="UID del calendario Zoho da cui recuperare gli eventi."), # Reso obbligatorio
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(database.get_db),
):
    """
    Questo endpoint recupera gli eventi da un calendario Zoho specifico, filtra per colore
    e restituisce una lista formattata al frontend, senza operazioni di salvataggio sul DB.
    Dato che il refresh token non viene gestito, l'access token scadrà dopo 1 ora e richiederà nuova autorizzazione.
    """
    try:
        current_access_token = await refresh_zoho_access_token_if_needed(db)
    except HTTPException as e:
        if e.status_code == 401 and "Access token assente o scaduto" in e.detail:
            raise HTTPException(
                status_code=401,
                detail="Access token scaduto o assente. Esegui una nuova autorizzazione di Zoho visitando /zoho_oauth_initiate e completando il processo via browser."
            )
        raise e

    # I parametri dp_testa_id e current_user_id non vengono più usati per interazioni con il DB in questo endpoint,
    # dato che la richiesta è di tornare solo gli eventi al frontend.

    _start_time = datetime.combine(start_date, datetime.min.time()) if start_date else datetime.now() - timedelta(days=30)
    _end_time = datetime.combine(end_date, datetime.max.time()) if end_date else datetime.now() + timedelta(days=7)

    try:
        raw_events = await fetch_zoho_calendar_events(current_access_token, calendar_uid, _start_time, _end_time)
        # Filtra gli eventi per colore, mantenendo solo quelli con color: #AAD867
        filtered_events = [event for event in raw_events if event.get("color") == "#AAD867"]
        print(f"Recuperati {len(raw_events)} eventi raw da Zoho Calendar per UID {calendar_uid}. Filtrati {len(filtered_events)} eventi con colore #AAD867.")
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=f"Errore nel recupero degli eventi da Zoho: {e.detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore inatteso durante il recupero degli eventi Zoho: {str(e)}")

    formatted_events = []
    filtered_events.sort(key=lambda event: event.get("dateandtime", {}).get("start", ""))

    # Processa solo gli eventi filtrati e li formatta per il frontend
    for event in filtered_events:
        caluid = event.get("uid") # L'UID dell'evento Zoho
        title = event.get("title", "Nome Cliente Sconosciuto") # Il titolo dell'evento
        note = event.get("description", "") or event.get("note", "") # La descrizione dell'evento

        event_start_datetime_str = event.get("dateandtime", {}).get("start")
        event_start_time = None
        if event_start_datetime_str:
            try:
                # Converti il formato "20250102T223000+0100" in datetime object
                event_start_time = datetime.strptime(event_start_datetime_str, "%Y%m%dT%H%M%S%z")
            except ValueError:
                print(f"DEBUG: Impossibile parsare la data/ora di inizio dell'evento: {event_start_datetime_str}. Usando l'ora corrente.")
                event_start_time = datetime.now()
        else:
            event_start_time = datetime.now() # Fallback se la data/ora non è presente

        fascia_oraria = "AM" if event_start_time.hour < 12 else "PM"
        materiale_disponibile = "NO" # Sempre "NO" come richiesto

        formatted_events.append({
            "caluid": caluid,
            "title": title,
            "id_sede": None,
            "id_agpspm": None,
            "note": note,
            "fasciaoraria": fascia_oraria,
            "materialedisponibile": materiale_disponibile
        })

    return formatted_events # Restituisce la lista di eventi formattati direttamente al frontend


@router.post("/export_dp_pdf/{dp_testa_id}")
def export_dp_pdf(dp_testa_id: int, db: Session = Depends(database.get_db), current_user_id: Optional[str] = "admin_simulato"):
    """
    Simula la generazione e l'invio via email del DP in formato PDF.
    """
    dp_testa = db.query(models.DPTesta).filter(models.DPTesta.id == dp_testa_id).first()
    if not dp_testa:
        raise HTTPException(status_code=404, detail="DP Testa non trovata.")

    return {"message": f"Simulazione: DP ID {dp_testa_id} esportato come PDF e inviato via email da {current_user_id}."}

@router.post("/log_operation/")
def log_operation(log_entry: schemas.LogEntry):
    """
    Registra un'operazione nel log.
    """
    print(f"LOG: [{datetime.now()}] User: {log_entry.user}, Operation: {log_entry.operation}, Description: {log_entry.description}")
    return {"message": "Operazione loggata con successo"}

@router.get("/reports/top_resources/")
def get_top_resources(db: Session = Depends(database.get_db)) -> Dict[str, Any]:
    """
    Simula il report delle top 10 risorse impegnate.
    """
    try:
        top_resources_raw = db.query(models.DPDetail.id_agpspm, models.OauthUser.first_name, models.OauthUser.last_name)\
                             .join(models.OauthUser, models.DPDetail.id_agpspm == models.OauthUser.username)\
                             .limit(10).all()

        top_resources_list = [
            {"username": res.id_agpspm, "first_name": res.first_name, "last_name": res.last_name, "engagement_count": 0}
            for res in top_resources_raw
        ]
        return {"message": "Report Top 10 Risorse (simulato)", "data": top_resources_list}
    except Exception as e:
        print(f"Errore durante il recupero del report top resources: {e}")
        return {"message": "Simulazione: Report Top 10 Risorse.", "data": []}

@router.get("/reports/interventions_by_period/")
def get_interventions_by_period(
    start_date: date,
    end_date: date,
    client_name: Optional[str] = None,
    resource_assigned: Optional[str] = None,
    intervention_type: Optional[str] = None,
    db: Session = Depends(database.get_db)
) -> Dict[str, Any]:
    """
    Simula il report del numero di interventi nel periodo, filtrabile.
    """
    query = db.query(models.DPDetail)

    if client_name:
        query = query.filter(models.DPDetail.note.like(f"%{client_name}%"))

    if resource_assigned:
        query = query.filter(models.DPDetail.id_agpspm == resource_assigned)

    if intervention_type:
        query = query.join(models.DPDetailTI).join(models.TipoIntervento)\
                     .filter(models.TipoIntervento.descrizione == intervention_type)

    query = query.filter(models.DPDetail.created >= start_date, models.DPDetail.created <= end_date)
    count = query.count()

    return {
        "message": "Report Interventi per Periodo.",
        "period": f"{start_date} to {end_date}",
        "filters": {
            "client_name": client_name,
            "resource_assigned": resource_assigned,
            "intervention_type": intervention_type
        },
        "count": count
    }