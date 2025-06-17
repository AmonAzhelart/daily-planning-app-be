from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

# Importa tutti i router della tua applicazione
from app.routers import oauth_user, dp_testata, dp_detail, dp_detail_ti, views_and_simulations
# Importa i componenti del database
from .database import Base, engine

# Inizializzazione dell'applicazione FastAPI
app = FastAPI(
    title="Daily Planning Backend",
    description="Backend per la gestione del Daily Planning con FastAPI e MySQL. Compatibile con Python 3.11."
)

# --- CONFIGURAZIONE MIDDLEWARE ---

# 1. Middleware per le Sessioni (FIX)
# Questo middleware è FONDAMENTALE per abilitare request.session.
# Deve essere aggiunto prima dei router che lo utilizzano.
app.add_middleware(
    SessionMiddleware,
    secret_key="la-tua-chiave-segreta-unica-e-difficile-da-indovinare"
)

# 2. Middleware per CORS
# La tua configurazione era già corretta, la manteniamo.
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
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

# Il router 'oauth_user' contiene già il prefisso '/auth' al suo interno,
# quindi lo includiamo senza aggiungere un altro prefisso qui.
app.include_router(oauth_user.router)

# Per gli altri router, manteniamo la tua struttura con i prefissi definiti qui.
# Ho aggiunto il prefisso '/api' per raggrupparli in modo ordinato.
app.include_router(dp_testata.router, prefix="/api/dp_testata", tags=["DP Testata"])
app.include_router(dp_detail.router, prefix="/api/dp_detail", tags=["DP Dettagli"])
app.include_router(dp_detail_ti.router, prefix="/api/dp_detail_ti", tags=["DP Dettagli Tipologie Intervento"])
app.include_router(views_and_simulations.router, prefix="/api", tags=["Viste e Simulazioni"])


# --- ROUTE PRINCIPALE DI BENVENUTO ---

@app.get("/", tags=["Root"])
def read_root():
    return {"message": "Benvenuto nell'API del Daily Planning"}

