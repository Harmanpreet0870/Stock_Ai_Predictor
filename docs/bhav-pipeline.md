# NSE Bhavcopy Pipeline

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

## Purpose
Ingest NSE's daily "bhavcopy with delivery" (end-of-day equity CSV), correct for
corporate actions (splits, symbol renames), and append clean OHLCV rows to
`bhavdata_master_tb`. Driven by one row per trading date in `master_wdate_tb` and a
set of integer flags that gate each stage.

## Entry Points
| Trigger | Where | What runs |
|---|---|---|
| Backend startup | `Backend/main.py :: lifespan()` → `run_pipeline_batch(max_days=10)` | Up to 10 pending dates, sequentially, in a daemon thread |
| HTTP | `POST /pipeline/run?max_days=<n>` → `main.py :: trigger_pipeline` | Same batch runner, same thread model |
| CLI | `python Backend/pipeline_runner.py` | *(no `__main__` guard in the file)* — module import only |
| CLI (download only) | `python Backend/bhavpipeline/src/nse_bhavcopycsv_downloader_main.py` | Downloader has its own `__main__` that calls `run_bhavcopy_downloader_batch()` |

The batch runner lives in `Backend/pipeline_runner.py :: run_pipeline_batch()`.
It picks the oldest `master_wdate_tb` row satisfying
`tmpbhvupd_flag = 0 AND isholidayflag = 1 AND bhavdownload_flag = 1`
(see `get_eligible_date()`), then calls `run_pipeline_for_date()` for each one.

## Stages
```
                    master_wdate_tb row (wid, tsdate) with
                    bhavdownload_flag=1, tmpbhvupd_flag=0, isholidayflag=1
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Stage 1 — TempBhav Maker        tempbhav_maker.run_tempbhav_maker            │
│   Reads   data/RawBhvcopy/sec_bhavdata_full_<DDMMYYYY>.csv                   │
│   Writes  tempbhav_tb (bulk INSERT, DELETE existing rows for tsdate first)   │
│   Side    Detects splits (perc_change ≤ -25%) → writes csvjson/split_info... │
│   Flag    master_wdate_tb.tmpbhvupd_flag ← 1 (clean) or -2 (split present)   │
└──────────────────────────────────────────────────────────────────────────────┘
                                         │  if split_detected
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Stage 2 — Split Corrector       split_corrector.run_split_correction         │
│   Reads   csvjson/split_info_<tsdate>_wid<wid>.json                          │
│   Writes  tempbhav_tb.prev_close /= ratio   (that date's row only)           │
│           bhavdata_master_tb (open/high/low/last/close/prev_close/avg/trg    │
│                               divided; ttl_trd_qnty multiplied by ratio) for │
│                               all historical dates with wid < split wid      │
│   Side    csvjson/split_correction_report_<tsdate>_wid<wid>.csv              │
│   Flag    master_wdate_tb.tmpbhvupd_flag ← 1                                 │
│           error_remark ← 'Split corrected'                                   │
└──────────────────────────────────────────────────────────────────────────────┘
                                         │  always
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Stage 3 — Share Registry        shareregistry_checker.run_shareregistry_check│
│   Reads   tempbhav_tb.msid  vs  shareregistry_tb.msid                        │
│   Writes  shareregistry_tb — INSERT new, UPDATE missing → 'deactivate'       │
│   Side    csvjson/newoldshareinfo_<tsdate>.json                              │
│   Flag    master_wdate_tb.sharereg_flag ← 1 (no missing) or -2 (missing)     │
└──────────────────────────────────────────────────────────────────────────────┘
                                         │  if missing_shares > 0
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Stage 4 — MSID Rename Handler   msid_rename_handler.run_msid_rename          │
│   Reads   csvjson/newoldshareinfo_<tsdate>.json                              │
│           csvjson/symbolchange.json  (external — see downloader)             │
│   Writes  bhavdata_master_tb — UPDATE symbol, msid for all historical rows   │
│           shareregistry_tb — old symbol → 'deactivate', new symbol inserted  │
│           msidchange_tb — INSERT one row per rename / delisting              │
│   Side    csvjson/rename_log_<tsdate>.json                                   │
│   Flag    master_wdate_tb.sharereg_flag ← 1                                  │
└──────────────────────────────────────────────────────────────────────────────┘
                                         │  always
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ Stage 5 — TempBhav → Master     tempbhav_to_master.run_tempbhav_to_master    │
│   Writes  INSERT INTO bhavdata_master_tb SELECT ... FROM tempbhav_tb WHERE   │
│           tsdate = ?                                                         │
│   Checks  staging_count must equal master_count after the INSERT             │
│   Side    DELETE previous tsdate's rows from tempbhav_tb                     │
│   Flag    master_wdate_tb.bhavupdator_flag ← 1 (or -2 on mismatch / failure) │
│           bhavupd_count, bhavdatarow_count updated                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

## File-by-file Roles

### `pipeline_runner.py`
Orchestrator. Public functions:
- `get_eligible_date(db_path)` — returns the oldest `(wid, tsdate)` ready for Stage 1.
- `run_pipeline_for_date(wid, tsdate, db_path)` — runs stages 1→5. **Stops on failure** at any stage and returns `False`.
- `run_pipeline_batch(db_path, max_days)` — loops `run_pipeline_for_date` up to `max_days` times.

Stage 2 is skipped when `r1['detailed_work']['split_detected']` is false.
Stage 4 is skipped when `r3['detailed_work']['missing_shares']` is zero.

### `nse_bhavcopycsv_downloader_main.py`
Standalone downloader (not called by `pipeline_runner.py`). Pulls bhavcopy CSVs via
`nselib.capital_market.bhav_copy_with_delivery` and writes them to
`data/RawBhvcopy/sec_bhavdata_full_<DDMMYYYY>.csv`. Setting
`bhavdownload_flag = 1` on `master_wdate_tb` is what makes a row eligible for Stage 1.

Behaviour:
- Walks `master_wdate_tb` rows where `bhavdownload_flag = 0`, oldest first.
- Caps at `MAX_BHAV_DOWNLOADS_PER_RUN = 10` per invocation.
- For a `tsdate_normalized < today`: single try, then interactive prompt (`Y/N`) to mark the date as a holiday (`isholidayflag = 0`) and continue.
- For `tsdate_normalized == today`: `download_with_phased_retry()` — 5 attempts at 5-minute intervals (Phase 1), then 5 attempts at 30-minute intervals (Phase 2) — see `nse_bhavcopycsv_logic.py`.
- Honours `Ctrl+C` via a module-level `_termination_requested` flag.

### `nse_bhavcopycsv_logic.py`
Low-level helpers for the downloader:
- `download_bhavcopy_for_trade_date(trade_date_str, ddmmyyyy_str)` — calls `nselib.capital_market.bhav_copy_with_delivery(trade_date=...)` and saves the DataFrame as CSV. Raises if empty.
- `download_with_phased_retry()` — the two-phase retry loop.
- `wait_with_countdown()` — prints a per-second countdown; returns early if `_termination_requested` is set.

### `tempbhav_maker.py`
Reads the CSV for `tsdate`, parses it, drops excluded series (`EXCLUDE_SERIES`), and
bulk-inserts into `tempbhav_tb` after deleting any existing rows for the same
`tsdate`.
- `encode_symbol(symbol)` — deterministic 13-character hash: starts with `'9'`, followed by a 12-digit decimal derived from the symbol. Used as `msid` for new shares.
- `detect_splits(rows)` — flags rows where `perc_change ≤ -25.0` and computes a raw split ratio = `round(prev_close / close / 0.05) * 0.05`.
- On any detected split: writes `data/csvjson/split_info_<tsdate>_wid<wid>.json` and sets `tmpbhvupd_flag = -2` with `error_remark = "Split (<n> stocks) - DATA UPLOADED"`.

### `split_corrector.py`
Applies corrections for splits detected in Stage 1. Driven by the JSON file written by
`tempbhav_maker`.
- `smooth_split_ratio(ratio)` — snaps the raw ratio to the nearest value in `STANDARD_SPLIT_RATIOS = [1.5, 1.75, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50, 100]` and reports deviation. Deviations over `MAX_DEVIATION_PERCENT = 15.0%` produce warnings but still apply.
- `apply_split_correction_tempbhav(conn, msid, split_tsdate, ratio)` — divides `prev_close` only, on the current `tsdate` row.
- `apply_split_correction_bhav_master(conn, msid, historical_tsdates, ratio)` — divides every price column plus `trg` and `avg_price` and **multiplies** `ttl_trd_qnty` for historical rows with `wid < split_wid`.
- Writes `data/csvjson/split_correction_report_<tsdate>_wid<wid>.csv`.
- On success, sets `tmpbhvupd_flag = 1` and `error_remark = 'Split corrected'`.

### `shareregistry_checker.py`
Diffs today's `tempbhav_tb` against `shareregistry_tb` to find:
- new shares (in temp, not in registry) — inserted with `status = 'active'`.
- missing shares (active in registry, not in temp) — updated to `status = 'deactivate'`.
- Writes `data/csvjson/newoldshareinfo_<tsdate>.json`.
- Sets `sharereg_flag = -2` with `error_remark = "Missing <n> shares"` if any missing shares exist; otherwise `1`.
- `bootstrap_registry(db_path)` is the one-shot seeder for an empty registry (uses the earliest `tempbhav_tb` date).

### `msid_rename_handler.py`
Resolves missing shares by cross-referencing NSE's symbol-change feed.
- `load_symbolchange_mapping(json_path)` — reads `csvjson/symbolchange.json` and builds `old_symbol → {new_symbol, date}`.
- `classify_missing_shares(...)` — splits the missing list into `renamed` (old symbol has a mapping) and `delisted`.
- For each rename: `UPDATE bhavdata_master_tb SET symbol=?, msid=?` for all historical `tsdate`s (via `get_historical_tsdates`), then updates `shareregistry_tb` (deactivate old, insert / reactivate new), then logs the event in `msidchange_tb`.
- On completion: sets `sharereg_flag = 1` and writes `data/csvjson/rename_log_<tsdate>.json`.

### `tempbhav_to_master.py`
Transfers `tempbhav_tb` rows for one `tsdate` into `bhavdata_master_tb`. Column list
is hard-coded in `TRANSFER_COLUMNS`. After a successful transfer:
- `bhavupdator_flag = 1`, `bhavupd_count` and `bhavdatarow_count` set.
- Rows for the **previous** `tsdate` are deleted from `tempbhav_tb` (keeps staging small).
- On row-count mismatch: raises → rolls back → sets `bhavupdator_flag = -2`.

### `symbolchange_downloader.py`
Standalone utility. Fetches `https://nsearchives.nseindia.com/content/equities/symbolchange.csv`
with retries, filters rows to `SM_APPLICABLE_FROM` year ≥ `YEAR_FILTER_MIN = 2022`, and
writes `data/csvjson/symbolchange.json` (consumed by Stage 4). Not called by the
runner — must be run manually.

### `pipeline_checks.py`
Pre-run validation and generic flag helpers. Reads
`Backend/bhavpipeline/config/pipeline_master.json` and `flag_policy.json`. Owns
`FLAG_ERROR = -2`, `FLAG_HOLIDAY = -1`, `FLAG_PENDING = 0`, `FLAG_DONE = 1`,
`FLAG_ROLLED_OUT = 2` and `VALID_FLAG_VALUES`. Not called by `pipeline_runner.py`;
kept available for ad-hoc checks and TUI reporting.

### `pipeline_ui.py`
Rich-style ASCII tables used by `pipeline_checks` for diagnostics. No side effects
on data.

## Config Files

### `Backend/bhavpipeline/config/pipeline_master.json`
Declares every component with `component_id`, module `name`, `execution_order`,
`dependencies`, and `enabled`. Used by `pipeline_checks.get_component_status()` and
`validate_files()`. Changing `enabled` here does **not** affect
`pipeline_runner.py` — the runner has its own hard-coded stage sequence.

Current components:
| ID | Module (name) | Order | Enabled |
|---|---|---|---|
| `Share_Renamer` | `nse_bhavcopycsv_downloader_main` | 1 | false |
| `Temp_Bhav` | `tempbhav_maker` | 2 | true |
| `Split_Corrector` | `split_corrector` | 3 | true |
| `Share_Registry` | `shareregistry_checker` | 4 | true |
| `MSID_Corrector` | `msid_rename_handler` | 5 | true |
| `Bhav_Master` | `tempbhav_to_master` | 6 | true |

### `Backend/bhavpipeline/config/flag_policy.json`
Defines the flag value → description map and three rules:
- `isholidayflag=0 blocks all processing`
- `flag=1 cannot be retried`
- `flag=2 cannot be retried`

## Side-effect Files Written to `data/csvjson/`
| File | Written by | Consumed by |
|---|---|---|
| `split_info_<tsdate>_wid<wid>.json` | `tempbhav_maker` | `split_corrector` |
| `split_correction_report_<tsdate>_wid<wid>.csv` | `split_corrector` | audit only |
| `newoldshareinfo_<tsdate>.json` | `shareregistry_checker` | `msid_rename_handler` |
| `symbolchange.json` | `symbolchange_downloader` (manual) | `msid_rename_handler` |
| `rename_log_<tsdate>.json` | `msid_rename_handler` | audit only |

## Running the Pipeline

### Automatic (preferred)
Start the backend. `main.py :: lifespan` schedules a background batch with
`max_days = 10`.

### HTTP trigger
```
POST http://localhost:8000/pipeline/run?max_days=10
```
Returns `202 Accepted` immediately. Watch logs on the backend process.

### Standalone download
```powershell
cd D:\Stock_Ai_Predictor\Backend
python -m bhavpipeline.src.nse_bhavcopycsv_downloader_main
```
This only populates `data/RawBhvcopy/` and sets `bhavdownload_flag = 1`. Follow with a
backend restart or `POST /pipeline/run` to drive the remaining stages.

### Status check
```
GET http://localhost:8000/pipeline/status
```
Reports pending vs. completed date counts from `master_wdate_tb`.

## Debugging Guide
| Symptom | Likely cause | Where to look |
|---|---|---|
| Pipeline does nothing on startup | No row in `master_wdate_tb` satisfies the eligibility clause | `pipeline_runner.get_eligible_date` SQL. Confirm flags with `SELECT * FROM master_wdate_tb WHERE tsdate = ?` |
| Stage 1 fails with "CSV file not found" | Download step did not run or filename did not match `get_bhav_csv_path` patterns | Check `data/RawBhvcopy/`; run the downloader |
| `tmpbhvupd_flag = -2` after Stage 1 | Splits detected OR a database / parsing error | Open `csvjson/split_info_<tsdate>_wid<wid>.json`; `error_remark` has detail |
| Stage 2 reports high deviation | Observed ratio is far from any `STANDARD_SPLIT_RATIOS` entry | Verify split in NSE announcement; may be a stock-specific unusual ratio |
| `sharereg_flag = -2` | Missing shares — either genuine delistings or renames | `csvjson/newoldshareinfo_<tsdate>.json`; make sure `csvjson/symbolchange.json` is fresh and re-run Stage 4 |
| Stage 5 raises "Row count mismatch" | Trigger / unique-constraint rejected some rows | Diff `tempbhav_tb` vs `bhavdata_master_tb` for that `tsdate`; roll back is automatic |
| API returns empty / 404 after pipeline ran | API reads a different DB file than the pipeline wrote | See [database.md](database.md) — `DB_PATH` vs `MAIN_DB_PATH` |

## Known Gaps
- `pipeline_runner.py` has no `if __name__ == "__main__"` block — cannot be run directly as a script.
- Pipeline logs go to stdout only. There is no file sink even though `PIPELINE_LOG_PATH` is declared in `paths.py`.
- `symbolchange_downloader.py` is not called by the pipeline runner; stale `symbolchange.json` silently causes Stage 4 to classify every missing share as delisted.
- `pipeline_master.json` component flags are not honored by `pipeline_runner.py` — order and dependency changes made there have no effect on live runs.
