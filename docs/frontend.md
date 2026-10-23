# Frontend

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

React 18 single-page app, built with Vite 5. TypeScript throughout. Tailwind utility
classes for styling, ApexCharts for the candle chart.

## Project Layout
| Path | Role |
|---|---|
| `Frontend/index.html` | Vite entry HTML |
| `Frontend/src/main.tsx` | React root; mounts `<App />` |
| `Frontend/src/App.tsx` | Router + layout shell (`Navbar`, `MarketBar`, `<Routes>`, footer) |
| `Frontend/src/api/client.ts` | Axios client, grouped by resource |
| `Frontend/src/types/index.ts` | TypeScript shapes for every endpoint response |
| `Frontend/src/pages/*` | One component per route |
| `Frontend/src/components/*` | Shared UI pieces |
| `Frontend/src/index.css` | Tailwind layers + custom utility classes (`card`, `btn-ghost`, `tag-*`, `num`, …) |
| `Frontend/vite.config.ts` | Dev server + `/api` proxy |
| `Frontend/tailwind.config.js`, `postcss.config.js` | Styling pipeline |
| `Frontend/tsconfig.json` | TS compiler config |

## Routes (declared in `App.tsx`)
| Path | Component | File |
|---|---|---|
| `/` | `Home` | `src/pages/Home.tsx` |
| `/screener` | `Screener` | `src/pages/Screener.tsx` |
| `/stock/:symbol` | `StockDetail` | `src/pages/StockDetail.tsx` |
| `/sectors` | `Sectors` | `src/pages/Sectors.tsx` |
| `/patterns` | `Patterns` | `src/pages/Patterns.tsx` |

The layout wraps every route with `<Navbar />` and `<MarketBar />` and a footer.
`BrowserRouter` is used (no hash routing).

## Pages

### Home (`src/pages/Home.tsx`)
Loads five requests in parallel on mount:
```
market.overview()
market.movers('gainers', 12)
market.movers('losers',  12)
market.movers('buysignals', 12)
patterns({ limit: 10, sentiment: 'bullish' })
```
Renders four stat cards (trading date, A/D, buy signals, SuperTrend bullish count), a
mover table with tab switcher (`gainers | losers | buysignals`), and a grid of
`PatternMiniCard` entries linking to `/stock/:symbol`.

### Screener (`src/pages/Screener.tsx`)
Local state object (`Filters`) controls the query. Debounce comes from React's own
batching only — a filter change immediately resets `page = 1` and re-fetches. Filter
controls:

| UI field | Query param | Values |
|---|---|---|
| Signal | `signal` | `` | BUY | SELL | HOLD` |
| SuperTrend | `supertrend` | `1` or `-1` |
| Min / Max RSI | `min_rsi`, `max_rsi` | numeric |
| Min / Max Change % | `min_change`, `max_change` | numeric |
| Min Rel. Volume | `min_relvolume` | numeric |
| BB Signal | `bbs` | `BULL | BEAR | NEUTRAL` |
| VT Signal | `vt` | `BUY | SELL | HOLD` |
| Sort By | `sort_by` | `perc_change | rsi14 | ema_strength | relvolume | close_price` |
| Order | `sort_order` | `desc | asc` |

The result table columns: `Symbol, Price, Change %, Signal, RSI 14, EMA Str, RelVol,
BB, VT, Candle, Deliv%`. Row click navigates to `/stock/:symbol`.

### StockDetail (`src/pages/StockDetail.tsx`)
Loads `stocks.detail(symbol)` and `stocks.history(symbol, 120)` in parallel. Renders:
- Header card — symbol, SuperTrend signal badge, latest OHLC and volume.
- `PredictionCard` — composite score, confidence bar, factor chips (all computed server-side; see [api.md](api.md)).
- Candlestick chart (ApexCharts) with EMA 9 / EMA 21 overlays and a thin volume bar chart below. BB upper and lower drawn as horizontal annotations when available.
- `EmaCard`, `RsiCard`, `MacdCard`, `SuperTrendCard`, `BollingerCard`, `CandlePatternCard` — one indicator group each.

Error states: shows `ErrorCard` with `response.data.detail` on API failure. 404s surface as "Symbol 'X' not found".

### Sectors (`src/pages/Sectors.tsx`)
Grid of `SectorCard` buttons. Clicking a card opens a modal drawer and fetches
`sectors.stocks(id)`. Sentiment classification in `SectorCard`:
`advances / stock_count > 55% → bullish`, `< 45% → bearish`, else neutral.

### Patterns (`src/pages/Patterns.tsx`)
Three filter controls — sentiment (`bullish | bearish | all`), pattern type (populated
from `data.pattern_types`), symbol text input. Grid of cards showing Entry / Stop
Loss / Target with R:R, risk %, and score. Each card links to `/stock/:symbol`.

## Components (shared)
| Component | File | Role |
|---|---|---|
| `Navbar` | `src/components/Navbar.tsx` | Logo, nav links, debounced symbol search (250 ms), mobile menu |
| `MarketBar` | `src/components/MarketBar.tsx` | Sticky summary strip: date, A/D, unchanged, buy/sell signals, AD ratio |
| `SignalBadge` | `src/components/SignalBadge.tsx` | Normalizes raw signal strings and applies a `tag-*` class |
| `ChangeCell` | `src/components/ChangeCell.tsx` | Colored +/- percentage with optional trend icon |
| `LoadingSpinner` | `src/components/LoadingSpinner.tsx` | Centered loader |
| `ErrorCard` | `src/components/ErrorCard.tsx` | Error banner with message |

Signal normalization in `SignalBadge.tsx :: normalize()`:
- `STRONG BUY`, `BUY`, anything starting with `BUY` / containing `_BUY` → `BUY` or `STRONG BUY`
- Same mirror logic for `SELL`
- `BULL`, `BEAR`, `NEUTRAL` pass through
- everything else → `HOLD`

Mapped CSS classes: `tag-strong-buy`, `tag-buy`, `tag-hold`, `tag-sell`,
`tag-strong-sell`, `tag-bull`, `tag-bear`, `tag-neutral` (defined in `src/index.css`).

## API Client (`src/api/client.ts`)
Axios instance:
```ts
const http = axios.create({ baseURL: '/api', timeout: 20000 })
```
All calls are relative to `/api`. During dev, Vite proxies `/api/*` to
`http://localhost:8000` (see `vite.config.ts`). In production the frontend must be
hosted so that `/api/*` reaches the FastAPI server (reverse proxy or same origin).

Public surface (grouped by resource):
```ts
api.market.overview()
api.market.movers(type, limit?)
api.market.dates()

api.stocks.search(q)
api.stocks.detail(symbol)
api.stocks.history(symbol, days?)

api.screener(params)
api.sectors.list()
api.sectors.stocks(id)
api.patterns(params)
```
Each method returns the parsed body (`.then(r => r.data)`) and is typed via the
interfaces in `src/types/index.ts`.

## TypeScript Types (`src/types/index.ts`)
One interface per endpoint shape. Highlights:
- `MarketOverview`, `MoversResponse`, `StockMover`
- `StockDetail`, `StockIndicators` (long list of nullable indicator fields), `Prediction`
- `Candle` (used by the chart)
- `ScreenerResponse`, `ScreenerStock`
- `Sector`, `SectorStock`
- `PatternsResponse`, `PatternAlert`

Field names on the frontend mirror backend JSON keys **as-is** — the client does
not do any snake_case → camelCase conversion. Any new API field must also appear in
`types/index.ts`.

## Running the Dev Server
```powershell
cd D:\Stock_Ai_Predictor\Frontend
npm install     # first time only
npm run dev     # Vite on http://localhost:5173
```
Or from the repo root use `start_dev.ps1` which launches both backend and frontend
(see [setup.md](setup.md)).

## Build & Preview
```powershell
cd D:\Stock_Ai_Predictor\Frontend
npm run build   # tsc && vite build -> Frontend/dist/
npm run preview # serves the built bundle
```
`npm run build` runs `tsc` first — a TypeScript error will fail the build.

## Styling Notes
Tailwind utility classes dominate. Custom composite classes live in `src/index.css`
and include: `card`, `card-sm`, `btn-ghost`, `tag-*`, `num` (tabular-nums font),
`up` / `dn` (bull / bear text color), `muted`. Dark theme is the only theme —
`theme: { mode: 'dark' }` is set statically in ApexCharts options.

## Known Gaps
- No error boundary — an uncaught render error anywhere unmounts the whole app.
- No tests (no Vitest / Jest / RTL config). `package.json` has no `test` script.
- Search in `Navbar` has a 250 ms debounce but no in-flight cancellation; rapid typing can race.
- `StockDetail` uses `as any` to feed the ApexCharts mixed series — tightening the types would prevent silent breakage if the chart library's prop shapes change.
- No signup / login UI. OTP auth described in `auth.md` has no corresponding components in this commit.
