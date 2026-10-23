# Stock AI Predictor — Documentation Index

> Verified against commit `f972117` on 2026-10-23.

Full-stack NSE (National Stock Exchange of India) market analytics platform. A FastAPI
backend serves a React + TypeScript frontend. Market data is produced by a Python
pipeline that ingests the daily NSE bhavcopy, corrects for splits and symbol renames,
and feeds a SQLite database. Technical indicators and signals (SuperTrend, EMA stack,
RSI, MACD, Bollinger Bands, candle patterns) are consumed by the UI.

## Doc Index
| Doc | What it covers | When to read |
|---|---|---|
| [architecture.md](architecture.md) | Tech stack, service topology, data flow between frontend / backend / DB / pipeline | Starting out, or planning a cross-layer change |
| [database.md](database.md) | SQLite schema, tables, flags, how the pipeline writes it | Changing schema, debugging a query, understanding `wid` / `tsdate` / flag states |
| [api.md](api.md) | Every FastAPI endpoint — request params, response shape, status codes | Wiring a new frontend call, or debugging an API error |
| [bhav-pipeline.md](bhav-pipeline.md) | 5-stage ingestion pipeline, config files, split and rename handling, runner | Pipeline fails for a date, flag stuck, or adding a stage |
| [frontend.md](frontend.md) | React routes, pages, components, API client, dev workflow | Building UI, changing routing, consuming a new endpoint |
| [auth.md](auth.md) | OTP phone authentication — design and current blocker | Setting up Twilio, or implementing signup |
| [setup.md](setup.md) | Local dev prerequisites, install, env, start script, DB creation | First-time setup on a new machine |

## Quick Pointers
- Backend entry point: `Backend/main.py` — launches a background pipeline thread on startup.
- Database file (API consumer): `MAIN_DB_PATH` in `Backend/paths.py` → `D:\database\bhavdatabase\Nse_Mainbhavdata.db`.
- Pipeline DB file: `DB_PATH` in `Backend/paths.py` → `<project>/data/db/Nse_Mainbhavdata.db`.
- Dev script: `start_dev.ps1` opens two PowerShell windows (backend on `:8000`, frontend on `:5173`).
- Frontend proxy: `vite.config.ts` proxies `/api/*` to `http://localhost:8000`.

## Known Discrepancies
See each doc's "Known Gaps" section. The most significant ones are:
- `Backend/paths.py` defines two different DB paths — `DB_PATH` (used by the pipeline) and `MAIN_DB_PATH` (used by every API router). They point to different absolute locations. Documented in [database.md](database.md).
- The repo contains `_create_nse_data_db.py` which builds a slim snapshot DB (`Nse_data.db`) with renamed tables (`bhav_tb`, `master_tb`, …). The live API does **not** use this DB — it queries the full `Nse_Mainbhavdata.db`. Documented in [database.md](database.md).
- OTP authentication is described in team notes but **no source code for it exists in the repo at this commit**. Documented in [auth.md](auth.md).
