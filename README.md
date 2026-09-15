# Stock AI Predictor

AI-powered cloud-based stock analytics platform combining NSE bhavcopy data ingestion, technical analysis, ML predictions, news sentiment, portfolio analytics, and backtesting.

---

## Project Structure

```
Stock_Ai_Predictor/
│
├── Backend/
│   ├── main.py                   # FastAPI entry point — pipeline auto-starts on boot
│   ├── pipeline_runner.py        # Pipeline orchestrator (5 stages)
│   ├── paths.py                  # Centralised path config (portable, no hardcoded paths)
│   ├── requirements.txt
│   └── bhavpipeline/
│       ├── config/
│       │   ├── pipeline_master.json
│       │   └── flag_policy.json
│       └── src/
│           ├── tempbhav_maker.py              # Stage 1
│           ├── split_corrector.py             # Stage 2
│           ├── shareregistry_checker.py       # Stage 3
│           ├── msid_rename_handler.py         # Stage 4
│           ├── tempbhav_to_master.py          # Stage 5
│           ├── pipeline_checks.py
│           ├── nse_bhavcopycsv_downloader_main.py
│           ├── nse_bhavcopycsv_logic.py
│           ├── symbolchange_downloader.py
│           └── pipeline_ui.py
│
├── Data/
│   ├── db/                       # Drop Nse_Mainbhavdata.db here
│   ├── RawBhvcopy/               # NSE CSV files go here
│   ├── csvjson/                  # JSON intermediates (auto-created by pipeline)
│   └── Nse_data.db               # Slim analytics snapshot DB
│
├── _create_nse_data_db.py        # One-off script to build Nse_data.db
└── _inspect_db.py                # Utility to inspect source DB schema
```

---

## Getting Started

### Prerequisites

- Python 3.10+
- NSE main database: `Nse_Mainbhavdata.db` placed at `Data/db/Nse_Mainbhavdata.db`
- Raw NSE bhavcopy CSVs placed in `Data/RawBhvcopy/`

### Install dependencies

```bash
cd Backend
pip install -r requirements.txt
```

### Run the backend

```bash
cd Backend
uvicorn main:app --reload
```

The pipeline starts automatically in a background thread on server boot. No manual trigger needed.

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Health check |
| `GET` | `/health` | Health check |
| `POST` | `/pipeline/run?max_days=N` | Manually trigger a pipeline batch |
| `GET` | `/pipeline/status` | Show pending and completed date counts |

---

## Data Pipeline

The pipeline processes NSE trading data one date at a time in chronological order. A date is eligible when its CSV has been downloaded and it has not yet been processed.

### 5 Stages

| Stage | File | Description |
|-------|------|-------------|
| 1 | `tempbhav_maker.py` | Reads NSE CSV, filters series, computes MSID hash, detects stock splits, inserts into staging table |
| 2 | `split_corrector.py` | Runs only when splits detected — smooths split ratios and retroactively corrects all historical prices |
| 3 | `shareregistry_checker.py` | Compares today's data against the share registry — adds new stocks, deactivates missing ones |
| 4 | `msid_rename_handler.py` | Runs only when missing shares found — resolves NSE symbol renames, updates all historical rows |
| 5 | `tempbhav_to_master.py` | Promotes validated staging data to master table with row-count validation and rollback on mismatch |

### Pipeline Flow

```
NSE CSV (Data/RawBhvcopy/)
        │
        ▼  Stage 1
   tempbhav_tb  (staging)
        │
        ├──► [splits?] Stage 2 — correct prices in tempbhav + all historical rows
        │
        ▼  Stage 3
   shareregistry_tb  (new shares added / missing deactivated)
        │
        ├──► [missing shares?] Stage 4 — rename handler updates historical data
        │
        ▼  Stage 5
   bhavdata_master_tb  (permanent store)
```

### Flag State Machine

Each trading date in `master_wdate_tb` tracks pipeline progress via flags:

| Flag | Values | Meaning |
|------|--------|---------|
| `isholidayflag` | `0` / `1` | `1` = trading day |
| `bhavdownload_flag` | `0` / `1` | `1` = CSV downloaded |
| `tmpbhvupd_flag` | `0` / `1` / `-2` | Stage 1+2: pending / done / error or splits |
| `sharereg_flag` | `0` / `1` / `-2` | Stage 3+4: pending / done / missing shares |
| `bhavupdator_flag` | `0` / `1` / `-2` | Stage 5: pending / done / failed |

---

## Databases

### `Nse_Mainbhavdata.db` — Main Pipeline Database

The live working database. All pipeline stages read from and write to it.

| Table | Description |
|-------|-------------|
| `bhavdata_master_tb` | All historical bhavcopy data (~1.7M rows, one per stock per trading day) |
| `tempbhav_tb` | Staging area for today's data before promotion |
| `shareregistry_tb` | Active/inactive stock registry |
| `msidchange_tb` | Audit log of all renames and delistings |
| `master_wdate_tb` | One row per calendar date with pipeline flags |
| `splitdata_tb` | Detected and corrected split records |

### `Nse_data.db` — Analytics Snapshot Database

A slim copy for the AI/analytics layer. Rebuild anytime with:

```bash
python _create_nse_data_db.py
```

| Table | Source | Rows | Notes |
|-------|--------|------|-------|
| `bhav_tb` | `bhavdata_master_tb` | ~193K | Last 60 trading dates |
| `split_tb` | `splitdata_tb` | 345 | All rows |
| `master_tb` | `shareregistry_tb` | 3,828 | Core columns only |
| `rename_tb` | `msidchange_tb` | 4,652 | All rows |
| `wmaster_tb` | `master_wdate_tb` | 887 | Pipeline flags only |

---

## MSID — Stock Identifier

MSID is a 13-digit deterministic hash of a stock's symbol name. It always starts with `9`. When a stock is renamed on NSE, its MSID changes and the rename handler retroactively updates all historical rows.

---

## CSV File Naming

Place NSE bhavcopy CSV files in `Data/RawBhvcopy/`. Supported filename formats:

- `sec_bhavdata_full_DDMMYYYY.csv`
- `sec_bhavdata_full_DD-MM-YYYY.csv`
- `cmDDMONYYYYbhav.csv`
- `bhav_YYYYMMDD.csv`
