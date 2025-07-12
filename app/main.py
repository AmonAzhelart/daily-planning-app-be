# ===============================================================
# FILE: main.py (CORRETTO PER PRODUZIONE CON REVERSE PROXY)
# ===============================================================
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware
import os
import starlette
import sys
import inspect

# Importa tutti i router della tua applicazione
from app.routers import clients, dp_utility, interventions, oauth_user, dp_testata, dp_detail, dp_detail_ti, report_and_statistics, views_and_simulations
# Importa i componenti del database
from .database import Base, engine

# Inizializzazione dell'applicazione FastAPI
app = FastAPI(
    title="Daily Planning Backend",
    description="Backend per la gestione del Daily Planning con FastAPI e MySQL. Compatibile con Python 3.11.",
    version="1.0.0",
    openapi_version="3.1.0"
)

# --- CONFIGURAZIONE MIDDLEWARE ---

SECRET_KEY = os.getenv("SECRET_KEY", "SOSTITUISCIMI_CON_UNA_CHIAVE_SEGRETA_UNICA_E_FORTE_PER_LA_PRODUZIONE")


# 1. Middleware per le Sessioni (FIX IMPORTANTE PER HTTPS e REVERSE PROXY)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    https_only=True, # Fondamentale se usi HTTPS in produzione
    same_site="lax", # 'lax' è un buon default per sicurezza e usabilità
    
    # === MODIFICA CHIAVE PER IL LOGOUT DIETRO UN PROXY ===
    # Imposta esplicitamente il percorso del cookie a "/".
    # Questo assicura che il cookie sia valido per l'intero dominio
    # (es. webapp.mtortho.com) e non solo per un sotto-percorso
    # (es. /api/auth). Senza questo, il logout fallisce perché il browser
    # non riesce a sovrascrivere un cookie con un path più specifico.
    path="/",
    
    # Opzionale ma consigliato: dare un nome specifico al cookie
    # session_cookie="dplanning_session" 
)

# 2. Middleware per CORS (FIX PER PRODUZIONE)
# Assicurati che il dominio del cliente sia presente qui!
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # === MODIFICA CHIAVE PER PRODUZIONE ===
    # DECOMMENTA E INSERISCI IL DOMINIO REALE USATO DAL CLIENTE
    "https://webapp.mtortho.com"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True, # Permette l'invio di cookie
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- EVENTO DI STARTUP ---

@app.on_event("startup")
def on_startup():
    """
    Crea le tabelle del database all'avvio dell'applicazione, se non esistono.
    """
    Base.metadata.create_all(bind=engine)
    print("Tabelle del database create o già esistenti.")


# --- INCLUSIONE DEI ROUTER ---
app.include_router(dp_testata.router, prefix="/dp_testata", tags=["DP Testata"])
app.include_router(dp_detail.router, prefix="/dp_detail", tags=["DP Dettagli"])
app.include_router(dp_detail_ti.router, prefix="/dp_detail_ti", tags=["DP Dettagli Tipologie Intervento"])
app.include_router(views_and_simulations.router,prefix="/views", tags=["Viste e Simulazioni"])
app.include_router(oauth_user.router, prefix="/auth", tags=["Authentication"])
app.include_router(dp_utility.router, prefix="/dp_utility", tags=["DP Utility"])
app.include_router(clients.router, prefix="/clients", tags=["Clienti e Sedi"])
app.include_router(interventions.router, prefix="/interventions", tags=["Interventi"])
app.include_router(report_and_statistics.router, prefix="/report_and_statistics", tags=["Report e Statistiche"])

# --- ROUTE PRINCIPALE DI BENVENUTO ---

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Benvenuto nell'API del Daily Planning"}
