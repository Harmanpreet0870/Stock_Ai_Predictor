# API Reference

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

FastAPI app is defined in `Backend/main.py`. Interactive docs:
`http://localhost:8000/docs`. OpenAPI JSON: `http://localhost:8000/openapi.json`.

CORS allows `http://localhost:5173` and `http://127.0.0.1:5173` only.

All data-returning endpoints are **read-only `GET`**. There is no authentication, no
rate limiting, and no permission layer in the source at this commit.

## Endpoint Index
| Method | Path | Handler | Purpose |
|---|---|---|---|
| GET | `/` | `main.py :: root` | Service banner |
| GET | `/health` | `main.py :: health` | Liveness probe |
| POST | `/pipeline/run` | `main.py :: trigger_pipeline` | Manually launch pipeline batch |
| GET | `/pipeline/status` | `main.py :: pipeline_status` | Count pending / completed dates |
| GET | `/api/market/overview` | `routers/market.py :: market_overview` | A/D counts and signal totals |
| GET | `/api/market/movers` | `routers/market.py :: market_movers` | Gainers / losers / volume / buy signals |
| GET | `/api/market/dates` | `routers/market.py :: trading_dates` | Last N downloaded trading dates |
| GET | `/api/stocks/search` | `routers/stocks.py :: search_stocks` | Symbol autocomplete |
| GET | `/api/stocks/{symbol}` | `routers/stocks.py :: stock_detail` | Latest-day OHLC + indicators + composite signal |
| GET | `/api/stocks/{symbol}/history` | `routers/stocks.py :: stock_history` | Candle series (for chart) |
| GET | `/api/screener` | `routers/screener.py :: screener` | Filtered + paginated stock list |
| GET | `/api/sectors` | `routers/sectors.py :: list_sectors` | Sector-level advances / declines |
| GET | `/api/sectors/{sector_id}/stocks` | `routers/sectors.py :: sector_stocks` | Stocks in one sector |
| GET | `/api/patterns` | `routers/patterns.py :: list_patterns` | Pattern alerts, filtered + paginated |

## Health

### `GET /`
Response (200):
```json
{"status": "ok", "service": "Stock AI Predictor API v2"}
```

### `GET /health`
Response (200): `{"status": "ok"}`

## Pipeline Control

### `POST /pipeline/run?max_days=<int>`
Launches `pipeline_runner.run_pipeline_batch` on a daemon thread. Returns immediately.
| Param | In | Type | Default | Notes |
|---|---|---|---|---|
| `max_days` | query | int | 10 | Max pending dates to process in this call |

Response: `202 Accepted` — `{"status": "accepted", "message": "Pipeline started (max_days=<n>)"}`.

### `GET /pipeline/status`
Reads flag counts from `master_wdate_tb` directly.
```json
{"pending_dates": 2, "completed_dates": 1500}
```
Returns `503` if the DB file is missing, `500` on any other DB error.

## Market

### `GET /api/market/overview`
Cached in-process for 300 seconds (`market.py :: _cache["overview"]`).

Response:
| Field | Type | Source |
|---|---|---|
| `trading_date` | string `YYYY-MM-DD` | `MAX(tsdate)` reformatted |
| `total_symbols` | int | `COUNT(*)` on latest date |
| `advances` | int | rows with `perc_change > 0` |
| `declines` | int | rows with `perc_change < 0` |
| `unchanged` | int | `max(total - advances - declines, 0)` |
| `advance_decline_ratio` | float | `round(advances / max(declines, 1), 2)` |
| `buy_signals` | int | rows where `signal LIKE 'BUY%'` |
| `sell_signals` | int | rows where `signal LIKE 'SELL%'` |
| `supertrend_bullish` | int | rows with `direction = 1` |

Returns `{"error": "No data available"}` with status `200` when `master_indicator_tb` is empty.

### `GET /api/market/movers?type=<t>&limit=<n>`
| Param | Enum / Range | Default |
|---|---|---|
| `type` | `gainers | losers | volume | buysignals` | `gainers` |
| `limit` | 5–50 | 10 |

Internal ordering (`market.py :: market_movers`):
| type | order | extra WHERE |
|---|---|---|
| `gainers` | `perc_change DESC` | `AND perc_change > 0` |
| `losers` | `perc_change ASC` | `AND perc_change < 0` |
| `volume` | `relvolume DESC` | `AND relvolume IS NOT NULL AND relvolume > 0` |
| `buysignals` | `ema_strength DESC` | `AND signal LIKE 'BUY%' AND direction = 1` |

Response: `{ type, date, data: StockMover[] }` where `StockMover` has fields
`symbol, close_price, perc_change, volume, signal, ema_strength, rsi14,
supertrend_direction, rel_volume, atr20`.

### `GET /api/market/dates?limit=<n>`
Returns a plain array of date strings, most recent first.
| Param | Range | Default |
|---|---|---|
| `limit` | 5–100 | 20 |

Reads `master_wdate_tb WHERE bhavdownload_flag = 1`.

## Stocks

### `GET /api/stocks/search?q=<prefix>&limit=<n>`
| Param | Rule | Default |
|---|---|---|
| `q` | `min_length=1`, forced upper-case | *(required)* |
| `limit` | 1–30 | 10 |

Two-pass lookup against `shareregistry_tb WHERE status = 'active'`: first `symbol
LIKE 'Q%'`, then if still under the limit `symbol LIKE '%Q%' AND symbol NOT LIKE 'Q%'`.

Response: `[{"symbol": "..."}]`.

### `GET /api/stocks/{symbol}`
Reads the latest row from `master_indicator_tb` for the symbol, computes a composite
signal via `_compute_prediction`, and returns a nested object.

Composite-signal rules in `routers/stocks.py :: _compute_prediction()`:
| Factor | Condition | Score delta |
|---|---|---|
| SuperTrend | `direction = 1` | +2.5 |
| SuperTrend | `direction = -1` | -2.5 |
| EMA strength | `> 1.0` | +2.0 |
| EMA strength | `0..1` | +1.0 |
| EMA strength | `-1..0` | -1.0 |
| EMA strength | `< -1.0` | -2.0 |
| RSI 14 | `> 60` | +1.0 |
| RSI 14 | `< 40` | -1.0 |
| MACD | `macd > signal` and `histogram > 0` | +1.5 |
| MACD | `macd < signal` and `histogram < 0` | -1.5 |
| BBS | `bbs_signal = 'BULL'` | +1.0 |
| BBS | `bbs_signal = 'BEAR'` | -1.0 |
| VT | `vt_signal` contains `BUY` | +1.0 |
| VT | `vt_signal` contains `SELL` | -1.0 |
| 2-/3-candle pattern | contains any of `MORNING, WHITE, BULL, HAMMER, ENGULF` | +0.5 each |
| 2-/3-candle pattern | contains any of `EVENING, CROW, BEAR, DOJI_BEAR, HANG` | -0.5 each |
| Rel. volume | `> 1.5` and current score > 0 | +0.5 |
| Rel. volume | `> 1.5` and current score < 0 | -0.5 |

Signal buckets:
- `score >= 6.5` → `STRONG BUY`
- `score >= 3.5` → `BUY`
- `score <= -6.5` → `STRONG SELL`
- `score <= -3.5` → `SELL`
- otherwise → `HOLD`

`confidence = min(abs(score) / 10.5 * 100, 100)`. `factors` is truncated to 5 items.

Response shape (full): see `Frontend/src/types/index.ts :: StockDetail`. 404 if symbol is not in the latest-date rows.

### `GET /api/stocks/{symbol}/history?days=<n>`
| Param | Range | Default |
|---|---|---|
| `days` | 20–300 | 120 |

Returns a flat array of candles ordered **ascending** by date:
```ts
{ ts: number /* ms */, date: 'YYYY-MM-DD', open, high, low, close, volume,
  ema9, ema21, supertrend, st_dir }
```
`ts` is computed by `_ts_to_ms()` from the `YYYYMMDD` string. 404 if no rows.

## Screener

### `GET /api/screener`
All filters are optional. Only rows on `MAX(tsdate)` are considered.

| Param | Enum / Range | SQL effect |
|---|---|---|
| `signal` | `BUY | SELL | HOLD` | `BUY`/`SELL` match `signal LIKE 'BUY%'` / `'SELL%'`; `HOLD` matches exactly |
| `supertrend` | `-1 | 1` | `direction = ?` |
| `min_rsi` / `max_rsi` | 0–100 | `rsi14 >= ?` / `rsi14 <= ?` |
| `min_change` / `max_change` | — | `perc_change >= ?` / `perc_change <= ?` |
| `min_relvolume` | ≥ 0 | `relvolume >= ?` |
| `bbs` | `BULL | BEAR | NEUTRAL` | `bbs_signal = ?` |
| `vt` | `BUY | SELL | HOLD` | `BUY`/`SELL` use `LIKE '%BUY%'`/`'%SELL%'`; `HOLD` exact |
| `sort_by` | `perc_change | rsi14 | ema_strength | relvolume | close_price` | ORDER BY |
| `sort_order` | `asc | desc` | ORDER BY direction |
| `page` | ≥ 1 | OFFSET |
| `limit` | 10–100 | LIMIT |

Response:
```ts
{
  total: number, page: number, limit: number,
  pages: number,              // ceil(total / limit)
  date: 'YYYY-MM-DD',
  data: ScreenerStock[]       // see types/index.ts
}
```

## Sectors

### `GET /api/sectors`
Cached in-process for 300 seconds. Aggregates **in Python** after four DB queries
(see `routers/sectors.py :: list_sectors`). Only sectors with `level = 2` and at least
one active share are returned.

Per-sector fields:
| Field | Computation |
|---|---|
| `id`, `name`, `level` | from `master_sector_tb` |
| `display_name` | `name.replace('_', ' ').title()` |
| `stock_count` | count of symbols mapped to the sector (via `mapped_sharesector_tb`) |
| `advances` / `declines` | from `perc_change` sign |
| `avg_change` | mean of `perc_change` across sector symbols |
| `buy_count` | count of symbols whose `signal` contains `BUY` |

Response: `{ date: 'YYYY-MM-DD', data: Sector[] }`.

### `GET /api/sectors/{sector_id}/stocks?limit=<n>`
| Param | Range | Default |
|---|---|---|
| `limit` | 10–200 | 100 |

Returns stocks in the sector ordered by `perc_change DESC` with price, signal and
headline indicators. Returns `{"error": "Sector not found"}` with status 200 if the
`sector_id` has no row.

## Patterns

### `GET /api/patterns`
| Param | Rule | SQL effect |
|---|---|---|
| `symbol` | upper-cased in handler | `symbol = ?` |
| `sentiment` | `bullish | bearish` | `sentiment = ?` |
| `pattern_type` | free text | `pattern_type = ?` |
| `limit` | 10–200, default 50 | LIMIT |
| `page` | ≥ 1, default 1 | OFFSET |

Response per row:
| Field | Source / rule |
|---|---|
| `symbol`, `pattern_type`, `signal`, `sentiment` | direct from `pattern_tb` |
| `entry`, `stop_loss`, `target`, `risk_reward` | rounded to 2 dp |
| `score` | `pattern_tb.score * 100` (percent); `null` if DB value is null |
| `trade_date` | reformatted to `YYYY-MM-DD` if `pattern_tb.trade_date` is 8-digit; otherwise passed through |
| `risk_pct` | `round(abs(entry - sl) / entry * 100, 2)` |

Response envelope includes `pattern_types: string[]` — a de-duplicated list from
`SELECT DISTINCT pattern_type FROM pattern_tb` used to populate the UI filter dropdown.

## Error Shapes
- `HTTPException(status_code=404)` → `{"detail": "..."}` (JSON). Used by `/stocks/{symbol}` and `/stocks/{symbol}/history`.
- `/pipeline/status` returns `{"error": "..."}` with status 503/500 on DB problems.
- Validation errors (bad query parameter) return the FastAPI default `422` payload.

## Known Gaps
- No auth, no rate limiting, no API versioning. Any client can call every endpoint.
- `/pipeline/run` has no concurrency guard — two concurrent calls each spawn a thread; both threads will race on the same pending dates.
- `/sectors/{id}/stocks` returns `200` with an `error` field when the id is unknown, instead of a `404`. Inconsistent with the stocks router.
- `/patterns` opens a second connection in the same request just to fetch `pattern_types`.
