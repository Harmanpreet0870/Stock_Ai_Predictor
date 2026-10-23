# Architecture

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

## Tech Stack
| Layer | Technology | File / entry |
|---|---|---|
| Frontend | React 18 + TypeScript + Vite 5 + Tailwind 3 | `Frontend/src/main.tsx`, `Frontend/src/App.tsx` |
| Charts | ApexCharts + react-apexcharts | used in `Frontend/src/pages/StockDetail.tsx` |
| HTTP client | Axios 1.7 | `Frontend/src/api/client.ts` |
| Routing | react-router-dom 6 | `Frontend/src/App.tsx` |
| Backend | FastAPI + Uvicorn | `Backend/main.py` |
| DB driver | `sqlite3` (stdlib) | `Backend/database.py` |
| Pipeline | Python 3, `pandas`, `nselib`, `requests`, `tqdm` | `Backend/bhavpipeline/src/` |
| Database | SQLite (single file, WAL mode) | `D:\database\bhavdatabase\Nse_Mainbhavdata.db` |

Dependencies declared in `Backend/requirements.txt` and `Frontend/package.json`.

## Service Topology
```
┌─────────────────────────┐          ┌──────────────────────────────┐
│  Browser                │          │  Backend (FastAPI, port 8000)│
│  Vite dev server :5173  │  /api/*  │                              │
│  React + Axios          │ ───────► │  Routers: market / stocks /  │
│                         │  (proxy) │  screener / sectors /        │
└─────────────────────────┘          │  patterns                    │
                                     │                              │
                                     │  Startup lifespan:           │
                                     │  → launches pipeline thread  │
                                     └──────────────┬───────────────┘
                                                    │ sqlite3
                                                    ▼
                             ┌───────────────────────────────────────┐
                             │  SQLite  Nse_Mainbhavdata.db          │
                             │  Tables: master_indicator_tb,         │
                             │  bhavdata_master_tb, pattern_tb,      │
                             │  master_sector_tb, shareregistry_tb,  │
                             │  master_wdate_tb, …                   │
                             └──────────────────────▲────────────────┘
                                                    │ writes
                             ┌──────────────────────┴────────────────┐
                             │  Bhav Pipeline (same Python process,  │
                             │  background thread)                   │
                             │                                       │
                             │  5 stages per trading date:           │
                             │  tempbhav_maker → split_corrector →   │
                             │  shareregistry_checker →              │
                             │  msid_rename_handler →                │
                             │  tempbhav_to_master                   │
                             └──────────────────────┬────────────────┘
                                                    │ downloads
                                                    ▼
                             ┌───────────────────────────────────────┐
                             │  NSE India (nselib / HTTPS)           │
                             │  bhav_copy_with_delivery CSV,         │
                             │  symbolchange.csv                     │
                             └───────────────────────────────────────┘
```

## Request Flow (example: open the Screener page)
1. Browser hits Vite dev server at `http://localhost:5173/screener`.
2. React renders `Frontend/src/pages/Screener.tsx` which calls `api.screener(params)` in `Frontend/src/api/client.ts`.
3. Axios issues `GET /api/screener?...`. Vite proxy (`vite.config.ts`) forwards to `http://localhost:8000/api/screener`.
4. FastAPI dispatches to `Backend/routers/screener.py :: screener()`.
5. The handler opens a SQLite connection via `Backend/database.py :: get_db()` which reads `MAIN_DB_PATH`.
6. Rows are serialized to JSON and returned to the browser.

## Pipeline Flow
On FastAPI startup, `main.py :: lifespan()` spawns a daemon thread running
`pipeline_runner.run_pipeline_batch(db_path=DB_PATH, max_days=10)`. For each pending
trading date in `master_wdate_tb` (where `tmpbhvupd_flag = 0 AND isholidayflag = 1
AND bhavdownload_flag = 1`), the runner executes 5 stages in sequence. See
[bhav-pipeline.md](bhav-pipeline.md).

The pipeline can also be triggered manually via `POST /pipeline/run`. See [api.md](api.md).

## Ports and URLs
| Service | URL |
|---|---|
| Frontend dev server | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Interactive API docs (Swagger) | http://localhost:8000/docs |
| OpenAPI JSON | http://localhost:8000/openapi.json |

CORS is enabled for origins `http://localhost:5173` and `http://127.0.0.1:5173` in
`Backend/main.py`. All methods and headers are allowed.

## Deployment Topology
Not deployed. Only a local dev configuration exists at this commit. The dev launcher
is `start_dev.ps1` at the repo root; see [setup.md](setup.md).

## Key Design Decisions
- **SQLite over a server DB**: single-file DB keeps setup trivial; pipeline writers use `PRAGMA journal_mode = WAL`.
- **Pipeline runs in-process, not Celery**: a daemon thread in the FastAPI process (`main.py`) processes up to 10 pending dates per startup. There is no scheduler, task queue, or Redis.
- **Composite signal computation lives in the API, not in the DB**: `Backend/routers/stocks.py :: _compute_prediction()` combines indicators at request time. Indicator *values* are precomputed and stored in `master_indicator_tb`.
- **No ORM**: raw `sqlite3` with parameterized queries. `Backend/database.py` provides a thin context manager with `Row` factory.
