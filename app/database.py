import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator

# Configurazione del database
# Ora usa il nome del database dal tuo dump SQL: "orthoplus"
ipDatabase = os.getenv("IP_DATABASE", "localhost")
DATABASE_URL = f"mysql+mysqlconnector://root:kYHHNyYg5C98@{ipDatabase}/orthoplus"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
    
# Dipendenza per ottenere la sessione del database
def get_db() -> Generator[Session, None, None]:
    """
    Fornisce una sessione di database per ogni richiesta.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()