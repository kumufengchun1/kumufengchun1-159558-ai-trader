from __future__ import annotations
import json
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from app.config import settings, ROOT
from app.db import init_db, engine
from app.routers.api import router

app=FastAPI(title=settings.app_name)
app.mount("/static", StaticFiles(directory=str(ROOT/"app"/"static")), name="static")
app.include_router(router)
templates=Jinja2Templates(directory=str(ROOT/"app"/"templates"))

@app.on_event("startup")
def startup(): init_db()

@app.get("/health")
def health(): return {"ok":True}

def _authorized(request: Request) -> bool:
    return not settings.app_password or request.cookies.get("ats_auth")==settings.app_password

@app.get("/login",response_class=HTMLResponse)
def login_page(request:Request): return templates.TemplateResponse("login.html",{"request":request,"error":""})

@app.post("/login",response_class=HTMLResponse)
def login(request:Request,password:str=Form(...)):
    if password!=settings.app_password: return templates.TemplateResponse("login.html",{"request":request,"error":"密码错误"},status_code=401)
    r=RedirectResponse("/",303); r.set_cookie("ats_auth",password,httponly=True,samesite="lax"); return r

@app.get("/",response_class=HTMLResponse)
def dashboard(request:Request):
    if not _authorized(request): return RedirectResponse("/login")
    with engine.connect() as conn:
        pred=conn.execute(text("SELECT * FROM predictions ORDER BY trade_date DESC LIMIT 1")).mappings().first()
        statuses=conn.execute(text("SELECT symbol,MAX(trade_date) last_date,MAX(updated_at) updated_at,MAX(source) source FROM market_prices GROUP BY symbol ORDER BY symbol")).mappings().all()
        hist=conn.execute(text("SELECT * FROM predictions ORDER BY trade_date DESC LIMIT 30")).mappings().all()
    p=dict(pred) if pred else None
    if p: p["factors"]=json.loads(p.get("explanation") or "[]")
    return templates.TemplateResponse("dashboard.html",{"request":request,"pred":p,"statuses":[dict(x) for x in statuses],"hist":[dict(x) for x in hist]})
