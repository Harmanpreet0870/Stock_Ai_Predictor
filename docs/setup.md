# Local Development Setup

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

## Prerequisites
| Tool | Version | Notes |
|---|---|---|
| Python | 3.10 or newer | 3.11+ recommended; `sqlite3` is in the stdlib |
| Node.js | 18 or newer | ships with npm; required by Vite 5 |
| PowerShell | 5.1 or newer | needed for `start_dev.ps1` on Windows |
| Git | any | repo is at `D:\Stock_Ai_Predictor` |

The dev launcher is Windows-only. For WSL / Linux / macOS, run the backend and
frontend manually (see "Manual Startup").

## Repo Layout
```
D:\Stock_Ai_Predictor\
├── Backend\             # FastAPI app + pipeline
├── Frontend\            # Vite + React
├── Data\                # Project data (NSE DB, raw CSVs) — legacy name
├── data\                # Pipeline-created data dir (via paths.py)
├── docs\                # These docs
├── start_dev.ps1        # Dev launcher (both servers)
├── _create_nse_data_db.py   # One-off snapshot DB builder
├── _inspect_db.py       # Ad-hoc DB inspection script
└── README.md
```

## 1. Clone and Enter
```powershell
cd D:\
git clone <repo-url> Stock_Ai_Predictor
cd D:\Stock_Ai_Predictor
```

## 2. Backend Setup
```powershell
cd D:\Stock_Ai_Predictor\Backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
`requirements.txt` installs:
- `fastapi`
- `uvicorn[standard]`
- `pandas`
- `tqdm`
- `requests`
- `nselib` (NSE data download helpers)
- `python-multipart`

## 3. Frontend Setup
```powershell
cd D:\Stock_Ai_Predictor\Frontend
npm install
```
Dependencies: `react`, `react-dom`, `react-router-dom`, `axios`, `apexcharts`,
`react-apexcharts`, `lucide-react`. Dev deps include `vite`, `typescript`, `tailwindcss`.

## 4. Database
Two files are referenced by `Backend/paths.py`:
- `DB_PATH = <project>/data/db/Nse_Mainbhavdata.db` — written by the pipeline.
- `MAIN_DB_PATH = D:\database\bhavdatabase\Nse_Mainbhavdata.db` — **hard-coded**, read by every API router.

On a fresh machine neither exists. See [database.md](database.md) for details and
known-issue notes. Options:

### Option A: Start with an existing production DB
If you have a copy of `Nse_Mainbhavdata.db`:
1. Place it at `D:\database\bhavdatabase\Nse_Mainbhavdata.db` (so the API finds it).
2. Place a copy (or symlink) at `<project>/data/db/Nse_Mainbhavdata.db` (so the pipeline finds it).
3. Also populate `<project>/data/RawBhvcopy/` with the needed CSVs if you intend to run the pipeline.

### Option B: Build a snapshot DB from an existing full DB
There is a one-off helper that extracts a 60-day subset:
```powershell
cd D:\Stock_Ai_Predictor
python _create_nse_data_db.py
```
This produces `data/Nse_data.db` with renamed tables (`bhav_tb`, `master_tb`, …).
**Note**: the live API does **not** query this snapshot — the file is a convenience
for inspection and smaller tooling.

### Option C: Build from scratch
Not supported out of the box. There is no script in this repo that creates the full
`Nse_Mainbhavdata.db` schema from zero. You would need to:
1. Create the `master_wdate_tb` calendar and seed it with trading dates (`isholidayflag`, `bhavdownload_flag = 0`).
2. Create `shareregistry_tb`, `tempbhav_tb`, `bhavdata_master_tb`, `master_indicator_tb`, `pattern_tb`, `master_sector_tb`, `mapped_sharesector_tb`, `msidchange_tb` with schemas consistent with [database.md](database.md).
3. Run the downloader to populate `data/RawBhvcopy/`, then let the backend pipeline fill `tempbhav_tb` → `bhavdata_master_tb`.
4. Run the external indicator pipeline (not in this repo) to populate `master_indicator_tb`.

## 5. Environment Variables
No `.env` is required by the committed code. If OTP authentication is implemented
(see [auth.md](auth.md)), add these to `Backend/.env`:
```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_SMS_FROM=
REDIS_URL=redis://localhost:6379/0
```

## 6. Running Both Servers (recommended)
From the repo root:
```powershell
cd D:\Stock_Ai_Predictor
.\start_dev.ps1
```
This opens two new PowerShell windows:
- Backend — `python -m uvicorn main:app --reload --port 8000` from `Backend/`
- Frontend — `npm run dev` from `Frontend/`

URLs:
- Backend API: http://localhost:8000
- Interactive API docs (Swagger UI): http://localhost:8000/docs
- Frontend: http://localhost:5173

The script does **not** activate the Python virtualenv in the backend window —
either activate it before calling `start_dev.ps1`, or edit the script to call the
venv's `python.exe` directly.

## 7. Manual Startup

### Backend
```powershell
cd D:\Stock_Ai_Predictor\Backend
.\.venv\Scripts\Activate.ps1          # if using a venv
python -m uvicorn main:app --reload --port 8000
```
On startup, `main.py :: lifespan()` spawns a daemon thread that runs
`pipeline_runner.run_pipeline_batch(max_days=10)` against `DB_PATH`. Watch the
console for lines like `[1/5] TempBhav Maker`.

### Frontend
```powershell
cd D:\Stock_Ai_Predictor\Frontend
npm run dev
```
Vite proxies `/api/*` to the backend (`vite.config.ts`).

## 8. Verifying the Setup
Open http://localhost:8000/health in a browser → `{"status":"ok"}`.
Open http://localhost:5173 — the home page should load the MarketBar and four stat
tiles. If the API has no data (empty `master_indicator_tb`), the Home page shows
placeholder zeros but will not crash.

## 9. Common Issues
| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: nselib` on backend start | `pip install -r Backend/requirements.txt` with the venv active |
| Pipeline logs "Database not found" | Make sure `data/db/Nse_Mainbhavdata.db` exists (the pipeline uses `DB_PATH`) |
| API returns empty arrays everywhere | API is pointed at `MAIN_DB_PATH` which may differ from the pipeline's DB — see [database.md](database.md) "Known Issues" |
| CORS errors in browser | Ensure the frontend is served from `localhost:5173` (not another port) — the backend only allows two origins |
| `start_dev.ps1` cannot run | PowerShell execution policy. Run once: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Port 8000 or 5173 busy | Change via `--port` for uvicorn, and the `server.port` key in `Frontend/vite.config.ts` |

## 10. Build for Production
Frontend production bundle:
```powershell
cd D:\Stock_Ai_Predictor\Frontend
npm run build        # outputs Frontend/dist
npm run preview      # serves it locally for a sanity check
```
Backend production start (no `--reload`):
```powershell
cd D:\Stock_Ai_Predictor\Backend
python -m uvicorn main:app --port 8000 --workers 1
```
Use `--workers 1` so the startup pipeline thread does not duplicate across workers.
If you need multiple workers, move the pipeline out of the FastAPI process.

## Related
- Code paths and endpoints: [api.md](api.md)
- Pipeline internals: [bhav-pipeline.md](bhav-pipeline.md)
- Frontend details: [frontend.md](frontend.md)
- DB schema: [database.md](database.md)
