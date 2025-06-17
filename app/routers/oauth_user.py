import os
import re # Importato per l'analisi della stringa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session, joinedload
from werkzeug.utils import secure_filename
from typing import List, Optional

# Assumendo che questi file esistano nella cartella superiore (app/)
from .. import models, schemas, database

# Creiamo un router specifico per l'autenticazione
router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

# Percorso della cartella condivisa dove la vecchia app PHP salverà i file
OLD_SESSIONS_PATH = os.path.join(os.getcwd(), "vecchie_sessioni")
os.makedirs(OLD_SESSIONS_PATH, exist_ok=True)


def find_username_in_session_file(content: str) -> Optional[str]:
    """
    Estrae lo username da una stringa di sessione serializzata da PHP (Zend).
    Usa un'espressione regolare per trovare in modo affidabile il campo username.
    Il pattern cerca: s:8:"username";s:LUNGHEZZA:"valore_username"
    """
    match = re.search(r's:8:"username";s:\d+:"([^"]+)"', content)
    if match:
        return match.group(1)
    return None


@router.get('/login')
def bridge_login(request: Request, sid: str, db: Session = Depends(database.get_db)):
    """
    Endpoint "ponte". Legge un file di sessione PHP, estrae lo username,
    e crea una nuova sessione basata sui dati utente presenti nel nuovo DB.
    """
    if not sid:
        raise HTTPException(status_code=400, detail="ID di sessione (sid) mancante.")

    safe_filename = secure_filename(sid)
    session_file_path = os.path.join(OLD_SESSIONS_PATH, safe_filename)

    try:
        # Leggiamo il file come semplice testo con la codifica corretta
        with open(session_file_path, 'r', encoding='utf-8') as f:
            php_session_content = f.read()

        # Estraiamo lo username dal contenuto del file
        username = find_username_in_session_file(php_session_content)
        
        if not username:
            raise HTTPException(status_code=403, detail="Impossibile estrarre lo username dal file di sessione.")

        # Con lo username, carichiamo l'utente completo dal nostro database
        user_from_db = db.query(models.OauthUser).options(
            joinedload(models.OauthUser.role)
        ).filter(models.OauthUser.username == username).first()

        if not user_from_db:
            raise HTTPException(status_code=404, detail=f"Utente '{username}' non trovato nel database.")
        
        # Convertiamo l'utente del DB in un dizionario pulito per la sessione
        user_data_for_session = schemas.OauthUserResponse.from_orm(user_from_db).dict()
        print(f"Utente trovato: {user_data_for_session}")

    except FileNotFoundError:
        raise HTTPException(status_code=403, detail=f"File di sessione '{safe_filename}' non trovato.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore imprevisto durante l'elaborazione della sessione: {e}")
    
    # Imposta la sessione sicura di FastAPI con i dati presi dal nostro DB
    request.session.clear()
    request.session['is_logged_in'] = True
    request.session['user_info'] = user_data_for_session

    # Reindirizza al componente di callback del frontend React
    return RedirectResponse(url="http://localhost:3000/auth/callback")


@router.get('/me', response_model=schemas.OauthUserResponse)
def get_current_user(request: Request):
    """Restituisce i dati dell'utente loggato dalla sessione."""
    if not request.session.get('is_logged_in'):
        raise HTTPException(status_code=401, detail="Nessun utente autenticato")
    return request.session.get('user_info', {})

@router.post('/logout')
def logout(request: Request):
    """Distrugge la sessione corrente."""
    request.session.clear()
    return {"message": "Logout effettuato con successo"}


@router.get("/user/{username}", response_model=schemas.OauthUserResponse)
def get_user_with_role(username: str, db: Session = Depends(database.get_db)):
    """Recupera un utente in base al nome utente, includendo i dettagli del suo ruolo."""
    user = db.query(models.OauthUser).options(
        joinedload(models.OauthUser.role)
    ).filter(models.OauthUser.username == username).first()

    if user is None:
        raise HTTPException(status_code=404, detail="Utente non trovato")
        
    return user
