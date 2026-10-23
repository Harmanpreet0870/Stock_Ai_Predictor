export interface MarketOverview {
  trading_date: string
  total_symbols: number
  advances: number
  declines: number
  unchanged: number
  advance_decline_ratio: number
  buy_signals: number
  sell_signals: number
  supertrend_bullish: number
}

export interface StockMover {
  symbol: string
  close_price: number
  perc_change: number
  volume: number
  signal: string
  ema_strength: number
  rsi14: number
  supertrend_direction: number
  rel_volume: number
  atr20: number
}

export interface MoversResponse {
  type: string
  date: string
  data: StockMover[]
}

export interface Prediction {
  signal: string
  score: number
  confidence: number
  factors: string[]
}

export interface StockIndicators {
  ema5: number | null
  ema9: number | null
  ema21: number | null
  ema50: number | null
  ema100: number | null
  ema200: number | null
  ema_strength: number | null
  supertrend: number | null
  supertrend_direction: number | null
  supertrend_signal: string | null
  rsi7: number | null
  rsi14: number | null
  macd: number | null
  macd_signal_line: number | null
  macd_histogram: number | null
  bb_upper: number | null
  bb_basis: number | null
  bb_lower: number | null
  bbs_signal: string | null
  vt_signal: string | null
  vt_trend: string | null
  candle_type: string | null
  two_candle_pat: string | null
  three_candle_pat: string | null
  relvolume: number | null
  money20: number | null
  atr20: number | null
  vwap: number | null
}

export interface StockDetail {
  symbol: string
  latest_date: string
  open_price: number
  high_price: number
  low_price: number
  close_price: number
  perc_change: number
  ttl_trd_qnty: number
  deliv_per: number
  indicators: StockIndicators
  prediction: Prediction
}

export interface Candle {
  ts: number
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  ema9: number | null
  ema21: number | null
  supertrend: number | null
  st_dir: number | null
}

export interface ScreenerStock {
  symbol: string
  close_price: number
  perc_change: number
  signal: string
  rsi14: number
  ema_strength: number
  supertrend_direction: number
  rel_volume: number
  macd_histogram: number
  candle_type: string
  two_candle_pat: string
  three_candle_pat: string
  bbs_signal: string
  vt_signal: string
  atr20: number
  deliv_per: number
}

export interface ScreenerResponse {
  total: number
  page: number
  limit: number
  pages: number
  date: string
  data: ScreenerStock[]
}

export interface Sector {
  id: number
  name: string
  display_name: string
  level: number
  stock_count: number
  advances: number
  declines: number
  avg_change: number
  buy_count: number
}

export interface SectorStock {
  symbol: string
  close_price: number
  perc_change: number
  signal: string
  ema_strength: number
  rsi14: number
  supertrend_direction: number
  rel_volume: number
  bbs_signal: string
  vt_signal: string
  candle_type: string
}

export interface PatternAlert {
  symbol: string
  pattern_type: string
  signal: string
  sentiment: string
  entry: number
  stop_loss: number
  target: number
  risk_reward: number
  score: number | null
  risk_pct: number
  trade_date: string
}

export interface PatternsResponse {
  total: number
  page: number
  limit: number
  pages: number
  pattern_types: string[]
  data: PatternAlert[]
}
