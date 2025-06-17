from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional, List
from .models import DPStatus, FasciaOraria, MaterialeDisponibile # Importa gli Enum aggiornati

# Pydantic Schemas per la validazione dei dati

class DPTestaBase(BaseModel):
    giorno: date
    stato: Optional[DPStatus] = DPStatus.NUOVO
    revisione: Optional[int] = 1
    createdby: Optional[str] = None
    modifiedby: Optional[str] = None

class DPConfig(BaseModel):
    id: int
    key: Optional[str]
    value: Optional[str]
    description: Optional[str] = None

class DPTestaCreate(DPTestaBase):
    pass

class DPTestaUpdate(BaseModel):
    stato: Optional[DPStatus] = None
    revisione: Optional[int] = None
    modifiedby: Optional[str] = None

class DPTestaResponse(DPTestaBase):
    id: int
    created: datetime
    modified: datetime

    class Config:
        orm_mode = True

class DPDetailBase(BaseModel):
    caluid: Optional[str] = None
    id_sede: Optional[int] = None
    id_agpspm: Optional[str] = None
    note: Optional[str] = None
    fasciaoraria: FasciaOraria
    materialedisponibile: MaterialeDisponibile
    descrizionemanuale: Optional[str] = None
    createdby: Optional[str] = None
    modifiedby: Optional[str] = None

class DPDetailCreate(DPDetailBase):
    id_testata: int

class DPDetailUpdate(BaseModel):
    caluid: Optional[str] = None
    id_sede: Optional[int] = None
    id_agpspm: Optional[str] = None
    descrizionemanuale: Optional[str] = None
    note: Optional[str] = None
    fasciaoraria: Optional[FasciaOraria] = None
    materialedisponibile: Optional[MaterialeDisponibile] = None
    modifiedby: Optional[str] = None

class DPDetailResponse(DPDetailBase):
    id: int
    id_testata: int
    created: datetime
    modified: datetime

    class Config:
        orm_mode = True

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

# Schemi per le tabelle sottostanti alle viste (se necessario esporle)
class ClienteBase(BaseModel):
    ragione_sociale: str

class ClienteResponse(ClienteBase):
    id: int
    class Config:
        orm_mode = True

class SedeBase(BaseModel):
    id_cliente: int
    descrizione: Optional[str] = ""
    stato: Optional[str] = ""
    id_sap: Optional[int] = None

class SedeResponse(SedeBase):
    id: int
    class Config:
        orm_mode = True

class TipoInterventoBase(BaseModel):
    descrizione: Optional[str] = None

class TipoInterventoResponse(TipoInterventoBase):
    id: int
    class Config:
        orm_mode = True

class OauthUserBase(BaseModel):
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: int
    active: Optional[int] = 1
    super: Optional[int] = 0
    gestione_congressi: Optional[int] = 0
    hide_is_search: Optional[int] = 0
    parent_id: Optional[str] = None

class RoleBase(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    priority: Optional[int] = None


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
    role: Optional[RoleResponse] = None # Il ruolo è opzionale e usa lo schema RoleResponse

    class Config:
        orm_mode = True        

class InterventionPayload(BaseModel):
    """Definisce un singolo tipo di intervento con la sua quantità."""
    id_tipi_interventi: int
    qta: int

class DPDetailPayload(BaseModel):
    """Definisce una riga di dettaglio completa, inviata dal frontend."""
    id_sede: Optional[int]
    id_agpspm: Optional[str]
    descrizionemanuale: str
    caluid:  Optional[str] = None
    createdby: Optional[str] = None
    modifiedby: Optional[str] = None
    note: Optional[str]
    fasciaoraria: FasciaOraria
    materialedisponibile: MaterialeDisponibile
    interventions: List[InterventionPayload] = []

class DPTestaUpdatePayload(BaseModel):
    """Definisce il payload completo per l'endpoint PUT."""
    stato: DPStatus
    modifiedby: str
    details: Optional[List[DPDetailPayload]]

class DPCloseResponse(BaseModel):
    """Definisce la risposta standard dopo un'operazione di chiusura."""
    message: str
    stato: DPStatus
