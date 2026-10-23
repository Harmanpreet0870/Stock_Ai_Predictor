# Database

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

## Databases in Use

The repo references **two** different SQLite files via `Backend/paths.py`:

| Constant | Path | Used by |
|---|---|---|
| `DB_PATH` | `<project_root>/data/db/Nse_Mainbhavdata.db` | Pipeline (`pipeline_runner.py`, `main.py :: pipeline_status()`) |
| `MAIN_DB_PATH` | `D:\database\bhavdatabase\Nse_Mainbhavdata.db` (hard-coded absolute) | Every API router — `database.py :: get_db()` reads it |

These are **not** the same file. Any production setup must either consolidate them or
ensure that whatever process writes to `DB_PATH` is also what the API reads. See
"Known Issues".

A third file, `data/Nse_data.db`, is built on demand by `_create_nse_data_db.py`; it is a
**snapshot/subset** of the main DB with renamed tables (`bhav_tb`, `master_tb`,
`split_tb`, `rename_tb`, `wmaster_tb`). The live API does **not** query this snapshot.

Connection in `Backend/database.py`:
```
sqlite3.connect(MAIN_DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
```

## Table Index
Tables the application code touches, grouped by role.

| Table | Purpose | Written by | Read by |
|---|---|---|---|
| `master_wdate_tb` | Trading-day calendar with per-stage flags | `nse_bhavcopycsv_downloader_main.py`, every pipeline stage | `main.py :: pipeline_status`, `routers/market.py :: trading_dates`, pipeline runner |
| `tempbhav_tb` | Staging table — one trading date at a time | `tempbhav_maker.py`, `split_corrector.py` | `shareregistry_checker.py`, `tempbhav_to_master.py` |
| `bhavdata_master_tb` | Permanent OHLCV history, one row per (symbol, tsdate) | `tempbhav_to_master.py`, split and rename handlers (updates) | *(not read directly by the API — see note below)* |
| `master_indicator_tb` | Pre-computed indicators per (symbol, tsdate) | External "swing pipeline" (not in this repo) | `routers/stocks.py`, `routers/screener.py`, `routers/sectors.py`, `routers/market.py` |
| `shareregistry_tb` | Active / inactive symbol registry | `shareregistry_checker.py`, `msid_rename_handler.py` | `routers/stocks.py :: search_stocks`, `routers/sectors.py` |
| `msidchange_tb` | Audit log of symbol renames and delistings | `msid_rename_handler.py` | *(logging only)* |
| `master_sector_tb` | Sector hierarchy — one row per sector | *(seeded externally)* | `routers/sectors.py` |
| `mapped_sharesector_tb` | Many-to-many share ↔ sector mapping | *(seeded externally)* | `routers/sectors.py` |
| `pattern_tb` | Candlestick / chart pattern alerts | *(produced externally)* | `routers/patterns.py` |

Note on OHLCV read path: the UI gets prices from `master_indicator_tb` (the "indicator"
table also carries `open_price`, `high_price`, `low_price`, `close_price`,
`ttl_trd_qnty`, `deliv_per`, `perc_change`). `bhavdata_master_tb` is the raw history
written by the pipeline; a separate upstream job computes indicators into
`master_indicator_tb`.

## Table Details

### master_wdate_tb — trading-day calendar
Primary driver for the pipeline. One row per date; flags gate every stage.

| Column | Type | Meaning |
|---|---|---|
| `wid` | INTEGER PK | Sequential working-day id |
| `gdate` | DATE | Gregorian date |
| `tsdate` | TEXT (YYYYMMDD) | Trading-day key used throughout the pipeline |
| `isholidayflag` | INTEGER | 1 = working day, 0 = holiday, -1 = marked holiday after failure |
| `bhavdownload_flag` | INTEGER | 0 = pending, 1 = CSV downloaded, -1 = holiday / non-trading |
| `bhavdatarow_count` | INTEGER | Number of rows in the downloaded CSV |
| `tmpbhvupd_flag` | INTEGER | Stage 1 status (see Flag States) |
| `tmpbhvupd_count` | INTEGER | Rows loaded into `tempbhav_tb` |
| `sharereg_flag` | INTEGER | Stage 3 status |
| `shareregrow_count` | INTEGER | New shares added to `shareregistry_tb` |
| `bhavupdator_flag` | INTEGER | Stage 5 status (transfer to master) |
| `bhavupd_count` | INTEGER | Rows transferred to master |
| `bhavpip_flag` | INTEGER | Overall pipeline flag (used by `pipeline_checks.py`) |
| `ematable_flag` | INTEGER | External indicator-pipeline flag |
| `error_remark` | TEXT | Last error message (truncated to 500 chars) |

Column list reconstructed from reads/writes in `pipeline_runner.py`,
`nse_bhavcopycsv_downloader_main.py`, `tempbhav_maker.py`, `shareregistry_checker.py`,
`tempbhav_to_master.py`, `pipeline_checks.py`, and the snapshot DDL in
`_create_nse_data_db.py`.

### tempbhav_tb — staging table
Loaded by Stage 1 (`tempbhav_maker.py`). Insert list in `tempbhav_maker.py :: run_tempbhav_maker()`:

| Column | Type | Notes |
|---|---|---|
| `msid` | TEXT/BIGINT | Deterministic 13-char hash of symbol (`encode_symbol()` in `tempbhav_maker.py`) |
| `symbol` | TEXT | NSE symbol, upper-cased |
| `series` | TEXT | Series code; rows with `E1 IV P1 RR X1 GS GM N3 GB TO` are excluded in `read_and_parse_bhav_csv()` |
| `date1` | TEXT | Raw date string from CSV |
| `tsdate` | TEXT | YYYYMMDD trading date |
| `prev_close` | REAL | |
| `open_price`, `high_price`, `low_price`, `last_price`, `close_price`, `avg_price` | REAL | |
| `ttl_trd_qnty` | INTEGER | |
| `turnover_lacs` | REAL | Divided by 1e5 if raw value exceeds 1e5 (see `read_and_parse_bhav_csv()`) |
| `no_of_trades`, `deliv_qty` | INTEGER | |
| `deliv_per`, `perc_change` | REAL | `perc_change = ((close - prev_close) / prev_close) * 100` |
| `trg` | REAL | `high_price - low_price` (true range proxy) |

Stage 5 (`tempbhav_to_master.py`) deletes the **previous** day's rows from
`tempbhav_tb` after a successful transfer — the staging table typically holds only the
latest 1–2 trading dates.

### bhavdata_master_tb — permanent OHLCV history
Columns copied directly from `tempbhav_tb` (`TRANSFER_COLUMNS` in `tempbhav_to_master.py`):
```
msid, symbol, series, date1, tsdate, prev_close, open_price,
high_price, low_price, last_price, close_price, avg_price,
ttl_trd_qnty, turnover_lacs, no_of_trades, deliv_qty,
deliv_per, perc_change, trg
```
Updated in place by `split_corrector.py` (divides prices by the ratio; multiplies
`ttl_trd_qnty`) and `msid_rename_handler.py` (rewrites `symbol` and `msid` on
historical rows).

### master_indicator_tb — pre-computed indicators
Produced by an external pipeline (not in this repo — see note on
`paths.py :: MAIN_DB_PATH`). Columns consumed by the API routers:

| Column | Used in |
|---|---|
| `symbol`, `tsdate` | all routers |
| `open_price`, `high_price`, `low_price`, `close_price`, `prev_close` | `stocks.py`, `screener.py`, `market.py` |
| `ttl_trd_qnty`, `deliv_per`, `perc_change` | `stocks.py`, `screener.py`, `market.py` |
| `ema5`, `ema9`, `ema21`, `ema50`, `ema100`, `ema200`, `ema_strength` | `stocks.py`, `screener.py` |
| `supertrend`, `direction`, `signal` | all routers; `direction ∈ {-1, 1}`; `signal` is text like `BUY_NEW`, `SELL_NEW`, `HOLD` |
| `rsi7`, `rsi14` | `stocks.py`, `screener.py`, `sectors.py`, `market.py` |
| `macd`, `macd_signal`, `macd_histogram` | `stocks.py`, `screener.py` |
| `bb_upper`, `bb_basis`, `bb_lower`, `bbs_signal` | `stocks.py`, `screener.py`, `sectors.py` |
| `vt_signal`, `vt_trend` | `stocks.py`, `screener.py`, `sectors.py` |
| `candle_type`, `two_candle_pat`, `three_candle_pat` | `stocks.py`, `screener.py`, `sectors.py` |
| `relvolume`, `money20`, `atr20`, `vwap` | `stocks.py`, `screener.py`, `market.py`, `sectors.py` |

### shareregistry_tb — symbol registry
From `_create_nse_data_db.py` snapshot DDL (confirms live schema):
```
rid     INTEGER PRIMARY KEY AUTOINCREMENT
symbol  TEXT    NOT NULL
msid    BIGINT  NOT NULL
status  TEXT    DEFAULT 'active'  CHECK (status IN ('active','inactive','deactivate'))
tsdate  TEXT    NOT NULL
UNIQUE(symbol, msid)
```
Writers: `shareregistry_checker.py :: add_new_shares` / `deactivate_missing_shares`,
`msid_rename_handler.py :: update_shareregistry`.

### msidchange_tb — rename / delisting audit log
From `_create_nse_data_db.py` snapshot DDL:
```
id          INTEGER PRIMARY KEY AUTOINCREMENT
tsdate      TEXT    NOT NULL
change_type TEXT                      -- 'rename' or 'delisted'
old_symbol  TEXT
new_symbol  TEXT
old_msid    BIGINT
new_msid    BIGINT
change_date TEXT
status      TEXT
```
Written only by `msid_rename_handler.py :: insert_into_msidchange_tb()`. If `old_msid`
and `new_msid` columns are absent, the function falls back to a shorter insert.

### master_sector_tb — sector hierarchy
Columns read in `routers/sectors.py`:
- `sid` — sector id
- `sector_name` — raw name (underscored); UI calls `.replace('_', ' ').title()`
- `level` — hierarchy level; UI only queries `level = 2`
- `parent_id` — parent sector id

### mapped_sharesector_tb — share ↔ sector mapping
Columns read in `routers/sectors.py`:
- `sid` — sector id (join to `master_sector_tb.sid`)
- `rid` — registry id (join to `shareregistry_tb.rid`)
- `status` — only `'active'` rows are returned

### pattern_tb — chart / candlestick pattern alerts
Columns read in `routers/patterns.py`:
- `symbol`
- `pattern_type` — free-text identifier (used in the UI filter dropdown)
- `signal`, `sentiment` (`'bullish' | 'bearish'`)
- `entry`, `stop_loss`, `target` — price levels
- `risk_reward` — ratio stored as float
- `score` — 0..1 (API multiplies by 100 before returning)
- `trade_date` — may be `YYYYMMDD` or `YYYY-MM-DD` (handled in the router)

## Flag States
From `Backend/bhavpipeline/src/pipeline_checks.py` and `bhavpipeline/config/flag_policy.json`.

| Value | Name | Meaning |
|---|---|---|
| `-2` | `FLAG_ERROR` | Stage failed — requires review / retry |
| `-1` | `FLAG_HOLIDAY` | Holiday / non-trading day — skip |
| `0` | `FLAG_PENDING` | Eligible for execution |
| `1` | `FLAG_DONE` | Completed successfully |
| `2` | `FLAG_ROLLED_OUT` | Archived |

Policy rules (`flag_policy.json`):
- `isholidayflag = 0` blocks all processing.
- Flag `1` cannot be retried.
- Flag `2` cannot be retried.

Per-stage flag columns on `master_wdate_tb`:

| Flag column | Set by | Values used |
|---|---|---|
| `bhavdownload_flag` | `nse_bhavcopycsv_downloader_main.py` | `0`, `1`, `-1` |
| `tmpbhvupd_flag` | `tempbhav_maker.py` (`1` or `-2`), `split_corrector.py` (`1` after fix) | `0`, `1`, `-2` |
| `sharereg_flag` | `shareregistry_checker.py` (`1` or `-2`), `msid_rename_handler.py` (`1`) | `0`, `1`, `-2` |
| `bhavupdator_flag` | `tempbhav_to_master.py` (`1` or `-2`) | `0`, `1`, `-2` |
| `bhavpip_flag` | `pipeline_checks.py :: update_bhavpip_flag` | any valid flag value |

## Data Flow
```
NSE API (nselib)
   │ download_bhavcopy_for_trade_date()
   ▼
RawBhvcopy/sec_bhavdata_full_<DDMMYYYY>.csv
   │ run_tempbhav_maker()  →  flag tmpbhvupd_flag = 1 (or -2 if split)
   ▼
tempbhav_tb                           (optionally) csvjson/split_info_<tsdate>_wid<wid>.json
   │                                                │
   │ run_split_correction()  ◄───── reads JSON ─────┘
   │   divides prices in tempbhav_tb AND bhavdata_master_tb (historical)
   │
   │ run_shareregistry_check()
   │   adds new_shares → shareregistry_tb
   │   deactivates missing_shares
   │   writes  csvjson/newoldshareinfo_<tsdate>.json
   │   flag sharereg_flag = 1 (or -2 if missing)
   │
   │ run_msid_rename()  ◄──── reads newoldshareinfo + symbolchange.json
   │   rewrites symbol/msid in bhavdata_master_tb
   │   updates shareregistry_tb (deactivate old, insert new)
   │   logs to msidchange_tb
   │
   ▼
run_tempbhav_to_master()
   INSERT INTO bhavdata_master_tb SELECT ... FROM tempbhav_tb WHERE tsdate = ?
   deletes previous-day rows from tempbhav_tb
   flag bhavupdator_flag = 1

[external pipeline not in this repo]
   bhavdata_master_tb  →  master_indicator_tb
```

## Cache
In-process dicts in two routers (no Redis):
| Router | Key | TTL | Notes |
|---|---|---|---|
| `routers/market.py` | `"overview"` | 300 s | Only `/market/overview` is cached |
| `routers/sectors.py` | `"sectors"` | 300 s | Only `/sectors` (list) is cached; `/sectors/{id}/stocks` is not |

## Indexes (snapshot DDL in `_create_nse_data_db.py` — likely mirrored in the live DB)
| Table | Indexes |
|---|---|
| `bhav_tb` → mirrors `bhavdata_master_tb` | `(msid)`, `(tsdate)`, UNIQUE `(msid, tsdate)` |
| `master_tb` → mirrors `shareregistry_tb` | `(msid)` |
| `rename_tb` → mirrors `msidchange_tb` | `(tsdate)` |
| `wmaster_tb` → mirrors `master_wdate_tb` | `(tsdate)` |
| `split_tb` | `(tsdate)` |

## How to Add a Table or Column
1. Add the column to the physical DB with an `ALTER TABLE` SQL run from `_inspect_db.py` or `sqlite3` CLI.
2. If the pipeline writes it, update the insert list in `tempbhav_maker.py` (`insert_sql`) or in `TRANSFER_COLUMNS` of `tempbhav_to_master.py`.
3. If the API reads it, update the `SELECT` and the response assembler in the appropriate router.
4. If the snapshot `_create_nse_data_db.py` is used, update its CREATE TABLE and INSERT.
5. Update this doc's table and the owning feature's doc.

## Known Issues
- **Two DB paths**. `DB_PATH` and `MAIN_DB_PATH` in `paths.py` point to different files. The pipeline writes to `DB_PATH`; the API reads `MAIN_DB_PATH`. On a fresh checkout only `DB_PATH` is populated by the pipeline, so the API will see no data unless `MAIN_DB_PATH` is manually pointed at the same file. `MAIN_DB_PATH` is also hard-coded to `D:\database\bhavdatabase\…`, which is a Windows-only absolute path.
- **Indicator table has no pipeline in this repo**. `master_indicator_tb` is consumed by every router but produced by an external process. If it is empty, the API returns empty results on all endpoints.
- **`master_sector_tb` and `mapped_sharesector_tb` have no seeder in this repo**. The sectors UI will be empty until these tables are populated out-of-band.
- **`pattern_tb` has no producer in this repo**. The patterns UI will be empty until the external pattern engine runs.

## Change Log
| Date | Change | Reason |
|---|---|---|
| 2026-10-23 | Initial doc set created from commit `f972117` | First documentation pass |
