import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.db import init_db, SessionLocal
from app.api.routes import router
from app.engine.runner import seed_vendors

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ittracker")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

DEMO_EMAIL, DEMO_PASSWORD = "demo@ittracker.local", "demo1234"


def _start_scheduler():
    """Hourly reminder run inside the app process. SCHEDULER=0 disables it (tests, one-off scripts)."""
    if os.environ.get("SCHEDULER", "1") != "1":
        return None
    from apscheduler.schedulers.background import BackgroundScheduler
    from app.reminders import run_reminders

    def job():
        with SessionLocal() as db:
            try:
                res = run_reminders(db)
                log.info("reminders run: %s", res)
            except Exception:  # noqa: BLE001
                log.exception("reminder run failed")

    sched = BackgroundScheduler(timezone="Asia/Kolkata")
    sched.add_job(job, "interval", hours=1, id="reminders", max_instances=1, coalesce=True)
    sched.start()
    return sched


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with SessionLocal() as db:
        seed_vendors(db)
        if os.environ.get("SEED_SAMPLE", "1") == "1":
            from app.sample import seed_sample_if_empty
            if seed_sample_if_empty(db):
                log.info("sample company loaded")
        from sqlalchemy import select
        from app import models as m
        if db.execute(select(m.User.id).where(m.User.email == DEMO_EMAIL)).first():
            log.info("demo login: %s / %s", DEMO_EMAIL, DEMO_PASSWORD)
    sched = _start_scheduler()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="IT Tracker", version="0.2.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(","),
                   allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def access_log(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api") and request.url.path != "/api/health":
        log.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


app.include_router(router)

# Serve the built frontend (frontend/dist) if present, so one process runs the whole app.
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
