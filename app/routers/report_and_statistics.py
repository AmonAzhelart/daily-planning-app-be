import os
import httpx
import json
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from .. import models, schemas, database

router = APIRouter()

#Statistica top 10 clienti serviti da interventi
@router.get("/get_top_10_clienti", response_model=List[schemas.StatisticaTop10Clienti])
def get_top_10_clienti(db: Session = Depends(database.get_db)):
    return db.query(models.StatisticaTop10Clienti).limit(10).all()

#Statistica top 10 risorse impegnate
@router.get("/get_top_10_risorse", response_model=List[schemas.StatisticaTop10Risorse])
def get_top_10_risorse(db: Session = Depends(database.get_db)):
    return db.query(models.StatisticaTop10Risorse).limit(10).all()