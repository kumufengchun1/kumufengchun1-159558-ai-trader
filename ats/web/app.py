from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from ats.settings import settings
from ats.web.data import dashboard_snapshot

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="ATS 159558 Dashboard", version="0.6.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/dashboard")
def dashboard_api() -> dict:
    return dashboard_snapshot(settings.database_path)


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    snapshot = dashboard_snapshot(settings.database_path)
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"snapshot": snapshot},
    )
