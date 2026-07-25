from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from app.db import engine
from app.services.market_data import update_all
from app.services.features import build_dataset
from app.models.ensemble import train
from app.services.scoring import generate_prediction

router=APIRouter(prefix="/api")

@router.get("/latest")
def latest():
    with engine.connect() as conn:
        row=conn.execute(text("SELECT * FROM predictions ORDER BY trade_date DESC LIMIT 1")).mappings().first()
    return dict(row) if row else {}

@router.post("/refresh")
def refresh():
    try:
        status=update_all(); ds=build_dataset(); bundle=train(ds); pred=generate_prediction(ds)
        return {"status":status,"model":bundle.metrics,"prediction":pred}
    except Exception as e:
        raise HTTPException(500,str(e))
