# ====================================================
# File Role    : Master Entry Point
# File Name    : main.py
# Location     : Backend/
# Run          : uvicorn main:app --reload  (from Backend/ directory)
# ====================================================

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from paths import DB_PATH
from pipeline_runner import run_pipeline_batch
from routers import market, stocks, screener, sectors, patterns

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("main")


def _run_pipeline_background():
    try:
        log.info("Pipeline background thread starting...")
        result = run_pipeline_batch(db_path=DB_PATH, max_days=10)
        log.info(f"Pipeline background thread done: {result}")
    except Exception as e:
        log.error(f"Pipeline background thread error: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Backend startup — launching pipeline thread.")
    thread = threading.Thread(
        target=_run_pipeline_background, daemon=True, name="pipeline-startup"
    )
    thread.start()
    yield
    log.info("Backend shutting down.")


app = FastAPI(
    title="Stock AI Predictor",
    description="NSE market data + technical indicator analytics",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────────────
app.include_router(market.router)
app.include_router(stocks.router)
app.include_router(screener.router)
app.include_router(sectors.router)
app.include_router(patterns.router)


# ── Health ────────────────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "Stock AI Predictor API v2"}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}


# ── Pipeline control ──────────────────────────────────────────────
@app.post("/pipeline/run", tags=["Pipeline"])
def trigger_pipeline(max_days: int = 10):
    def run():
        run_pipeline_batch(db_path=DB_PATH, max_days=max_days)

    thread = threading.Thread(target=run, daemon=True, name="pipeline-manual")
    thread.start()
    return JSONResponse(
        status_code=202,
        content={"status": "accepted", "message": f"Pipeline started (max_days={max_days})"},
    )


@app.get("/pipeline/status", tags=["Pipeline"])
def pipeline_status():
    import sqlite3, os
    if not os.path.exists(DB_PATH):
        return JSONResponse(status_code=503, content={"error": "Database not found"})
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM master_wdate_tb WHERE tmpbhvupd_flag = 0 AND isholidayflag = 1 AND bhavdownload_flag = 1"
        )
        pending = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM master_wdate_tb WHERE bhavupdator_flag = 1")
        completed = cursor.fetchone()[0]
        conn.close()
        return {"pending_dates": pending, "completed_dates": completed}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
