from __future__ import annotations
import json
from datetime import datetime, timezone
import pandas as pd
from sqlalchemy import text
from app.db import engine
from app.models.ensemble import load_bundle, predict_row

FRIENDLY = {
 "ret_SOX":"SOX", "ret_NVDA":"NVDA", "ret_TSM":"TSM", "ret_ASML":"ASML",
 "ret_SOXS":"SOXS", "ret_VIX":"VIX", "ret_A50":"A50夜盘", "ret_NASDAQ":"纳指",
 "ret_USDCNH":"离岸人民币", "cn_mom5":"159558五日动量", "cn_ma5_gap":"159558均线位置",
 "cn_vol_ratio":"159558量比", "cn_volatility10":"159558波动率"
}
INVERSE = {"ret_SOXS", "ret_VIX", "ret_USDCNH"}

def explain(row: pd.Series) -> list[dict]:
    items=[]
    for k,label in FRIENDLY.items():
        if k not in row or pd.isna(row[k]): continue
        val=float(row[k]); signed=-val if k in INVERSE else val
        impact=max(-12,min(12,round(signed*400)))
        items.append({"factor":label,"value":val,"impact":impact})
    return sorted(items,key=lambda x:abs(x["impact"]),reverse=True)[:10]

def make_signal(prob: float, health: float) -> tuple[int,str,float]:
    score=round(prob*100)
    if score>=72: signal="强偏多"; pos=0.35
    elif score>=62: signal="偏多"; pos=0.20
    elif score>=53: signal="轻度偏多"; pos=0.10
    elif score<=38: signal="回避"; pos=0.0
    else: signal="中性"; pos=0.0
    pos*=max(0.4,min(1.0,health/70))
    return score,signal,round(pos,2)

def generate_prediction(dataset: pd.DataFrame) -> dict:
    bundle=load_bundle(); row=dataset.iloc[[-1]]
    prob, model_probs=predict_row(bundle,row)
    health=max(0,min(100,100-(bundle.metrics.get("test_brier",0.25)-0.15)*250))
    score,signal,pos=make_signal(prob,health)
    exp=explain(row.iloc[0])
    result={"trade_date":str(pd.Timestamp(row.iloc[0]["trade_date"]).date()),"probability":prob,"score":score,"signal":signal,"suggested_position":pos,"model_health":health,"factors":exp,"models":model_probs,"metrics":bundle.metrics}
    with engine.begin() as conn:
        conn.execute(text("""INSERT INTO predictions(trade_date,probability,score,signal,suggested_position,model_health,explanation,created_at)
        VALUES(:trade_date,:probability,:score,:signal,:suggested_position,:model_health,:explanation,:created_at)
        ON CONFLICT(trade_date) DO UPDATE SET probability=excluded.probability,score=excluded.score,signal=excluded.signal,suggested_position=excluded.suggested_position,model_health=excluded.model_health,explanation=excluded.explanation,created_at=excluded.created_at"""),
        {**{k:result[k] for k in ["trade_date","probability","score","signal","suggested_position","model_health"]},"explanation":json.dumps(exp,ensure_ascii=False),"created_at":datetime.now(timezone.utc).isoformat()})
    return result
