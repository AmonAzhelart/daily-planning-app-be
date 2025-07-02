import enum
from sqlalchemy import Column, Integer, String, Date, Boolean, Enum, DateTime, Text, CHAR, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.associationproxy import association_proxy
from datetime import datetime
from .database import Base

# --- ENUMERAZIONI ---

class DPStatus(enum.Enum):
    NUOVO = "NUOVO"
    APERTO = "APERTO"
    CHIUSO = "CHIUSO"
    MODIFICATO = "MODIFICATO"

class FasciaOraria(str, enum.Enum):
    AM = "AM"
    PM = "PM"

class MaterialeDisponibile(str, enum.Enum):
    SI = "SI"
    NO = "NO"

# --- MODELLI DEL DATABASE (ORDINE CORRETTO) ---

class DPTesta(Base):
    __tablename__ = "dp_testata"
    id = Column(Integer, primary_key=True, index=True)
    giorno = Column(Date, unique=True, index=True, comment='giorno di riferimento del dp')
    stato = Column(Enum(DPStatus), default=DPStatus.NUOVO, comment='stato del dp')
    revisione = Column(Integer, default=1, comment='revisione del dp dopo la chiusura')
    created = Column(DateTime, default=datetime.now)
    createdby = Column(String(255), nullable=True, comment='oauth_users id')
    modified = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    modifiedby = Column(String(255), nullable=True, comment='oauth_users id')

    dettagli = relationship("DPDetail", back_populates="testata_dp", cascade="all, delete-orphan")

class Role(Base):
    __tablename__ = "roles"
    id = Column(Integer, primary_key=True)
    name = Column(String(50), nullable=False, default='')
    description = Column(String(255), nullable=True, default='')
    priority = Column(Integer, nullable=True)

class OauthUser(Base):
    __tablename__ = "oauth_users"
    username = Column(String(255), primary_key=True)
    password = Column(String(2000), nullable=True)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    active = Column(Integer, default=1)
    super = Column(Integer, default=0)
    gestione_congressi = Column(Integer, default=0)
    hide_is_search = Column(Integer, default=0)
    parent_id = Column(String(255), nullable=True)
    role_id = Column("role", Integer, ForeignKey("roles.id"))
    
    role = relationship("Role", foreign_keys=[role_id])
    dettaglio_associations = relationship("DPDetailAGPSPM", back_populates="agpspm_user")

class DPDetailAGPSPM(Base):
    """
    Modello per la tabella di associazione `dp_dettaglio_agpspm`.
    """
    __tablename__ = "dp_dettaglio_agpspm"
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_dettaglio = Column(Integer, ForeignKey("dp_dettaglio.id"), nullable=False)
    id_agpspm = Column(String(255), ForeignKey("oauth_users.username"), nullable=False)

    dettaglio = relationship("DPDetail", back_populates="agpspm_associations")
    agpspm_user = relationship("OauthUser", back_populates="dettaglio_associations")

class DPDetail(Base):
    __tablename__ = "dp_dettaglio"
    id = Column(Integer, primary_key=True, index=True)
    id_testata = Column(Integer, ForeignKey("dp_testata.id"), index=True, nullable=False)
    caluid = Column(String(64), default='', comment='Zoho Calendar event id', unique=True, nullable=True) 
    id_sede = Column(Integer, ForeignKey("sedi.id"), nullable=True, comment='Sede del cliente')
    note = Column(String(1024), nullable=True)
    fasciaoraria = Column(Enum(FasciaOraria), nullable=False)
    materialedisponibile = Column(Enum(MaterialeDisponibile), nullable=True)
    descrizionemanuale= Column(String(1024), nullable=True, default='')
    created = Column(DateTime, nullable=False, default=datetime.now)
    createdby = Column(String(255), nullable=False, default='')
    modified = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)
    modifiedby = Column(String(255), nullable=False, default='')

    # Relazioni
    testata_dp = relationship("DPTesta", back_populates="dettagli")
    sedi = relationship("Sede")
    tipi_interventi_dettaglio = relationship("DPDetailTI", back_populates="dettaglio_dp_parent", cascade="all, delete-orphan")
    
    agpspm_associations = relationship("DPDetailAGPSPM", back_populates="dettaglio", cascade="all, delete-orphan")
    
    # --- CORREZIONE APPLICATA ---
    # Aggiungiamo un 'creator' per istruire il proxy su come creare l'oggetto di associazione.
    # Quando si assegna un oggetto 'OauthUser', il creator lo incapsula in un 'DPDetailAGPSPM',
    # risolvendo il TypeError.
    agpspm_users = association_proxy(
        "agpspm_associations", 
        "agpspm_user",
        creator=lambda user_obj: DPDetailAGPSPM(agpspm_user=user_obj)
    )

class DPDetailTI(Base):
    __tablename__ = "dp_dettaglio_ti"
    id = Column(Integer, primary_key=True, index=True)
    id_dettaglio = Column(Integer, ForeignKey("dp_dettaglio.id"), nullable=False, default=0)
    id_tipi_interventi = Column(Integer, ForeignKey("tipi_interventi.id"), nullable=False, default=0)
    qta = Column(Integer, nullable=False, default=0)

    dettaglio_dp_parent = relationship("DPDetail", back_populates="tipi_interventi_dettaglio")
    tipo_intervento_ref = relationship("TipoIntervento")

class Cliente(Base):
    __tablename__ = "clienti"
    id = Column(Integer, primary_key=True, autoincrement=True)
    ragione_sociale = Column(Text, nullable=False)
    sedi_associate = relationship("Sede", back_populates="cliente_ref")

class Sede(Base):
    __tablename__ = "sedi"
    id = Column(Integer, primary_key=True)
    id_cliente = Column(Integer, ForeignKey("clienti.id"), nullable=False)
    descrizione = Column(String(100), default='')
    stato = Column(CHAR(2), default='')
    id_sap = Column(Integer, nullable=True)
    cliente_ref = relationship("Cliente", back_populates="sedi_associate")

class TipoIntervento(Base):
    __tablename__ = "tipi_interventi"
    id = Column(Integer, primary_key=True)
    descrizione = Column(String(50), nullable=True)

class ZohoToken(Base):
    __tablename__ = "dp_zoho_tokens"
    id = Column(Integer, primary_key=True, index=True)
    access_token = Column(String(512), nullable=False)
    refresh_token = Column(String(512), nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class VistaClientiSedi(Base):
    __tablename__ = "dp_v_clienti"
    id_sede = Column(Integer, primary_key=True, nullable=True)
    cliente = Column(Text, nullable=False)
    sede = Column(Text, nullable=False)

class DpVApspm(Base):
    __tablename__ = 'dp_v_agpspm'
    username = Column(String, primary_key=True)
    last_name = Column(String)
    first_name = Column(String)
    role_id = Column(Integer)
    active = Column(Integer)
    super = Column(Integer)
    gestione_congressi = Column(Integer)
    parent_id = Column(String, nullable=True)
    role_name = Column(String, nullable=True)
    parent_last_name = Column(String, nullable=True)
    parent_first_name = Column(String, nullable=True)

class Config(Base):
    __tablename__ = "dp_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(50), unique=True, nullable=False)
    value = Column(String(255), nullable=False)
    description = Column(String(1024), nullable=True, default='')
