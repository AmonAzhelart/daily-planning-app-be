from pydantic import BaseModel, validator, Field
from datetime import date, datetime
from typing import Optional, List
from .models import DPStatus, FasciaOraria, MaterialeDisponibile

# --- Schemi di base riutilizzabili ---

class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    class Config:
        orm_mode = True

class OauthUserResponse(BaseModel):
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[RoleResponse] = None
    class Config:
        orm_mode = True

# ====================================================================
# --- Schemi per la Gestione di Clienti e Sedi (NUOVO & AGGIORNATO) ---
# ====================================================================

# --- Schemi per le Sedi ---
class SedeBase(BaseModel):
    descrizione: str = Field(..., min_length=1, description="Descrizione della sede")

class SedeCreate(SedeBase):
    id_cliente: int

class SedeUpdate(SedeBase):
    pass # Permette di aggiornare tutti i campi di SedeBase

class Sede(SedeBase):
    id: int
    id_cliente: int
    class Config:
        orm_mode = True

# --- Schemi per i Clienti ---
class ClienteBase(BaseModel):
    ragione_sociale: str = Field(..., min_length=1, description="Nome del cliente")

class ClienteUpdate(ClienteBase):
    pass

# Schema per la creazione di un cliente, che deve includere almeno una sede
class SedeForClienteCreate(BaseModel):
    descrizione: str = Field(..., min_length=1)

class ClienteCreate(ClienteBase):
    # Usiamo Field per validare che la lista non sia vuota
    sedi: List[SedeForClienteCreate] = Field(..., min_items=1)

# Schema per la risposta GET di un cliente con l'elenco delle sue sedi
class Cliente(ClienteBase):
    id: int
    class Config:
        orm_mode = True

class ClienteWithSedi(Cliente):
    sedi: List[Sede] = []

# --- Schema CORE per DPDetail senza campi conflittuali ---
class DPDetailCore(BaseModel):
    caluid: Optional[str] = None
    id_sede: Optional[int] = None
    note: Optional[str] = None
    fasciaoraria: FasciaOraria
    materialedisponibile: MaterialeDisponibile
    descrizionemanuale: Optional[str] = None
    createdby: Optional[str] = None
    modifiedby: Optional[str] = None

# --- Schemi per l'INPUT (usati nelle richieste POST/PUT) ---

class DPDetailBase(DPDetailCore):
    """Schema di base per l'input, si aspetta una lista di username."""
    agpspm_users: List[str] = []

class DPDetailCreate(DPDetailBase):
    id_testata: int

class DPDetailUpdate(BaseModel):
    """Schema per l'aggiornamento parziale di un dettaglio."""
    caluid: Optional[str] = None
    id_sede: Optional[int] = None
    descrizionemanuale: Optional[str] = None
    note: Optional[str] = None
    fasciaoraria: Optional[FasciaOraria] = None
    materialedisponibile: Optional[MaterialeDisponibile] = None
    modifiedby: Optional[str] = None
    agpspm_users: Optional[List[str]] = None

# --- Schemi per l'OUTPUT (usati nelle risposte GET) ---

class DPDetailResponse(DPDetailCore):
    """Schema per la risposta, restituisce una lista di oggetti utente completi."""
    id: int
    id_testata: int
    created: datetime
    modified: datetime
    agpspm_users: List[OauthUserResponse] = []

    # --- CORREZIONE APPLICATA (Sintassi per Pydantic v1) ---
    # Usiamo il decoratore `validator` con `pre=True` che è l'equivalente
    # di `mode='before'` in Pydantic v2.
    @validator('agpspm_users', pre=True, always=True)
    @classmethod
    def handle_association_proxy(cls, v):
        # Converte esplicitamente il proxy in una lista prima della validazione.
        if v is not None:
            return list(v)
        return []

    class Config:
        orm_mode = True


# --- Schemi per la Testa del DP (invariati ma mantenuti per completezza) ---

class DPTestaBase(BaseModel):
    giorno: date
    stato: Optional[DPStatus] = DPStatus.NUOVO
    revisione: Optional[int] = 1
    createdby: Optional[str] = None
    modifiedby: Optional[str] = None

class DPTestaCreate(DPTestaBase):
    pass

class DPTestaResponse(DPTestaBase):
    id: int
    created: datetime
    modified: datetime
    class Config:
        orm_mode = True

# --- PAYLOAD COMPLETI PER LE CHIAMATE API (DAL FRONTEND) ---

class InterventionPayload(BaseModel):
    id_tipi_interventi: int
    qta: int

class DPDetailPayload(BaseModel):
    id: Optional[int] = None
    caluid: Optional[str] = None
    id_sede: Optional[int] = None
    descrizionemanuale: str
    note: Optional[str]
    fasciaoraria: FasciaOraria
    materialedisponibile: MaterialeDisponibile
    agpspm_users: List[str] = []
    interventions: List[InterventionPayload] = []

class DPTestaUpdatePayload(BaseModel):
    stato: DPStatus
    modifiedby: str
    details: Optional[List[DPDetailPayload]]

# --- Tutti gli altri schemi che avevi, mantenuti per completezza ---

class DPDetailTICreate(BaseModel):
    id_dettaglio: int
    id_tipi_interventi: int
    qta: Optional[int] = 0

class DPDetailTIResponse(BaseModel):
    id: int
    id_dettaglio: int
    id_tipi_interventi: int
    qta: int
    class Config:
        orm_mode = True

class LogEntry(BaseModel):
    operation: str
    description: str
    user: Optional[str] = "unknown"

class ClienteResponse(BaseModel):
    id: int
    ragione_sociale: str
    class Config:
        orm_mode = True

class SedeResponse(BaseModel):
    id: int
    id_cliente: int
    descrizione: Optional[str] = ""
    stato: Optional[str] = ""
    id_sap: Optional[int] = None
    class Config:
        orm_mode = True

class TipoInterventoResponse(BaseModel):
    id: int
    descrizione: Optional[str] = None
    class Config:
        orm_mode = True

class TipoInterventoBase(BaseModel):
    descrizione: str = Field(..., min_length=1, max_length=50)

class TipoInterventoCreate(TipoInterventoBase):
    pass

class TipoInterventoUpdate(TipoInterventoBase):
    pass

class TipoIntervento(TipoInterventoBase):
    id: int
    is_used: bool # True se l'intervento è stato usato almeno una volta

    class Config:
        orm_mode = True

class DPCloseResponse(BaseModel):
    message: str
    stato: DPStatus

class DPConfig(BaseModel):
    id: int
    key: Optional[str]
    value: Optional[str]
    description: Optional[str] = None
    class Config:
        orm_mode = True

class StatisticaTop10Clienti(BaseModel):
    ragione_sociale: str
    descrizione: Optional[str] = None
    missioni: int

    class Config:
        orm_mode = True

class StatisticaTop10Risorse(BaseModel):
    id_agpspm: str
    last_name: Optional[str] = None
    first_name: Optional[str] = None
    name: Optional[str] = None
    missioni: int

    class Config:
        orm_mode = True