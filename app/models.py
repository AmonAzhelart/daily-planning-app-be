import enum
from sqlalchemy import Column, Integer, String, Date, Boolean, Enum, DateTime, Text, CHAR, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

# Enumerazione per lo stato del DP (dal campo 'stato' in dp_testata)
class DPStatus(enum.Enum):
    NUOVO = "NUOVO"
    APERTO = "APERTO"
    CHIUSO = "CHIUSO"
    MODIFICATO = "MODIFICATO"

# Enumerazione per Fascia Oraria (dal campo 'fasciaoraria' in dp_dettaglio)
class FasciaOraria(str, enum.Enum): # Aggiunto str per compatibilità con Pydantic Enum su stringhe
    AM = "AM"
    PM = "PM"

# Enumerazione per Materiale Disponibile (dal campo 'materialedisponibile' in dp_dettaglio)
class MaterialeDisponibile(str, enum.Enum): # Aggiunto str
    SI = "SI"
    NO = "NO"

# Modelli del database SQLAlchemy

class ZohoToken(Base):
    __tablename__ = "dp_zoho_tokens" # Nome della tabella nel database
    
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String(512), nullable=False) # Aumentato la lunghezza per sicurezza
    refresh_token = Column(String(512), nullable=True) # Potrebbe essere nullable se non sempre presente
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Se la tua applicazione deve gestire token per più utenti Zoho,
    # potresti aggiungere un campo come zoho_user_id = Column(String, unique=True, index=True)
    # Per una singola integrazione applicazione-Zoho, un'unica riga è sufficiente.

    def __repr__(self):
        return f"<ZohoToken id={self.id} expires_at={self.expires_at}>"

class DPTesta(Base):
    """
    Modello per la tabella `dp_testata`. Rappresenta l'intestazione del Daily Planning.
    """
    __tablename__ = "dp_testata"
    id = Column(Integer, primary_key=True, index=True)
    giorno = Column(Date, unique=True, index=True, comment='giorno di riferimento del dp') # Corrisponde a dp_date
    stato = Column(Enum(DPStatus), default=DPStatus.NUOVO, comment='stato del dp') # Corrisponde a status
    revisione = Column(Integer, default=1, comment='revisione del dp dopo la chiusura') # Corrisponde a revision
    created = Column(DateTime, default=datetime.now)
    createdby = Column(String(255), nullable=True, comment='oauth_users id')
    modified = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    modifiedby = Column(String(255), nullable=True, comment='oauth_users id')

    # Relazione con DPDetail (usando la colonna id_testata in DPDetail)
    dettagli = relationship("DPDetail", back_populates="testata_dp")


class DPDetail(Base):
    """
    Modello per la tabella `dp_dettaglio`. Rappresenta i dettagli degli appuntamenti in un Daily Planning.
    """
    __tablename__ = "dp_dettaglio"
    id = Column(Integer, primary_key=True, index=True)
    id_testata = Column(Integer, ForeignKey("dp_testata.id"), index=True, nullable=False)
    caluid = Column(String(64), default='', comment='Zoho Calendar event id', unique=True) 
    id_sede = Column(Integer, ForeignKey("sedi.id"), nullable=True, comment='Sede del cliente')
    id_agpspm = Column(String(255), ForeignKey("oauth_users.username"), nullable=True, comment='oauth_users id') # FK a username di oauth_users
    note = Column(String(1024), nullable=True) # Corrisponde a notes
    fasciaoraria = Column(Enum(FasciaOraria), nullable=False) # Corrisponde a time_slot
    materialedisponibile = Column(Enum(MaterialeDisponibile), nullable=True) # Corrisponde a material_available
    descrizionemanuale= Column(String(1024), nullable=True, default='', comment='Descrizione manuale dell\'appuntamento') # Aggiunto per descrizione manual
    created = Column(DateTime, nullable=False, default=datetime.now) # Aggiunto default per nuove righe
    createdby = Column(String(255), nullable=False, default='')
    modified = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now) # Aggiunto default/onupdate
    modifiedby = Column(String(255), nullable=False, default='')

    # Relazioni
    testata_dp = relationship("DPTesta", back_populates="dettagli")
    sedi = relationship("Sede")
    agpspm_user = relationship("OauthUser")
    tipi_interventi_dettaglio = relationship("DPDetailTI", back_populates="dettaglio_dp_parent")


class DPDetailTI(Base):
    """
    Modello per la tabella `dp_dettaglio_ti`. Rappresenta le tipologie di intervento per un dettaglio DP.
    """
    __tablename__ = "dp_dettaglio_ti"
    id = Column(Integer, primary_key=True, index=True)
    id_dettaglio = Column(Integer, ForeignKey("dp_dettaglio.id"), nullable=False, default=0)
    id_tipi_interventi = Column(Integer, ForeignKey("tipi_interventi.id"), nullable=False, default=0)
    qta = Column(Integer, nullable=False, default=0) # Corrisponde a quantity

    # Relazioni
    dettaglio_dp_parent = relationship("DPDetail", back_populates="tipi_interventi_dettaglio")
    tipo_intervento_ref = relationship("TipoIntervento")


class Cliente(Base):
    """
    Modello per la tabella `clienti`.
    """
    __tablename__ = "clienti"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ragione_sociale = Column(Text, nullable=False)

    # Relazioni (se necessario, ad esempio con Sedi)
    sedi_associate = relationship("Sede", back_populates="cliente_ref")

class VistaClientiSedi(Base): # <-- NOME MODIFICATO per chiarezza
    """
    Modello per la VISTA `dp_v_clienti`. Usato per la lettura dei dati aggregati.
    """
    __tablename__ = "dp_v_clienti"
    id_sede = Column(Integer, primary_key=True, nullable=True) # Può essere null
    cliente = Column(Text, nullable=False)
    sede = Column(Text, nullable=False)

class Sede(Base):
    """
    Modello per la tabella `sedi`.
    """
    __tablename__ = "sedi"
    id = Column(Integer, primary_key=True)
    id_cliente = Column(Integer, ForeignKey("clienti.id"), nullable=False)
    descrizione = Column(String(100), default='')
    stato = Column(CHAR(2), default='')
    id_sap = Column(Integer, nullable=True, comment='(forse) id del gestionale SAP')

    # Relazioni
    cliente_ref = relationship("Cliente", back_populates="sedi_associate")


class TipoIntervento(Base):
    """
    Modello per la tabella `tipi_interventi`.
    """
    __tablename__ = "tipi_interventi"
    id = Column(Integer, primary_key=True)
    descrizione = Column(String(50), nullable=True)


class OauthUser(Base):
    """
    Modello per la tabella `oauth_users`.
    """
    __tablename__ = "oauth_users"
    username = Column(String(255), primary_key=True)
    password = Column(String(2000), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    active = Column(Integer, default=1, comment='0 = non attivo, 1 = attivo ad effettuare il login')
    super = Column(Integer, default=0)
    gestione_congressi = Column(Integer, default=0)
    hide_is_search = Column(Integer, default=0, comment='0 = mostra, 1 = nascondi nelle liste degli utenti/agenti')
    parent_id = Column(String(255), nullable=True, comment='username con cui si ha rapporto di sub-agente')
    
    # La colonna 'role' nella tabella utenti contiene l'ID del ruolo (ForeignKey)
    role_id = Column("role", Integer, ForeignKey("roles.id"))
    
    # La relazione 'role_ref' collega questo modello al modello 'Role'
    # usando la ForeignKey 'role_id'
    role = relationship("Role", foreign_keys=[role_id])

class DpVApspm(Base):
    """
    Questo modello SQLAlchemy mappa la vista del database `dp_v_agpspm`.
    Le colonne qui definite devono corrispondere esattamente a quelle nella SELECT della VIEW.
    """
    __tablename__ = 'dp_v_agpspm'

    # SQLAlchemy ha bisogno di una chiave primaria per mappare gli oggetti.
    username = Column(String, primary_key=True)
    
    # Colonne dalla tabella 'u' (oauth_users)
    last_name = Column(String)
    first_name = Column(String)
    role_id = Column(Integer)  # La vista ha già rinominato `u.role` in `role_id`
    active = Column(Integer)
    super = Column(Integer)
    gestione_congressi = Column(Integer)
    parent_id = Column(String, nullable=True)

    # Nuova colonna dalla tabella 'r' (roles)
    role_name = Column(String, nullable=True)

    # Nuove colonne dalla tabella 'u2' (join su oauth_users)
    parent_last_name = Column(String, nullable=True)
    parent_first_name = Column(String, nullable=True)

class Role(Base):
    """
    Modello per la tabella `roles`.
    """
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, default='')
    description = Column(String(255), nullable=True, default='')
    priority = Column(Integer, nullable=True, comment='Livello di importanza (1 = max) per la gestione del daily planning')

class Config(Base):
    """
    Modello per la tabella `config`.
    """
    __tablename__ = "dp_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True, default='')
    