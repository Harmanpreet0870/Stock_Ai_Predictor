import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ArrowLeft, TrendingUp, TrendingDown, Activity } from 'lucide-react'
import ReactApexChart from 'react-apexcharts'
import { ApexOptions } from 'apexcharts'
import { api } from '../api/client'
import type { StockDetail as StockDetailType, Candle } from '../types'
import SignalBadge from '../components/SignalBadge'
import LoadingSpinner from '../components/LoadingSpinner'
import ErrorCard from '../components/ErrorCard'

export default function StockDetail() {
  const { symbol } = useParams<{ symbol: string }>()
  const [stock, setStock] = useState<StockDetailType | null>(null)
  const [candles, setCandles] = useState<Candle[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!symbol) return
    setLoading(true); setError('')
    Promise.all([api.stocks.detail(symbol), api.stocks.history(symbol, 120)])
      .then(([s, c]) => { setStock(s); setCandles(c) })
      .catch(e => setError(e?.response?.data?.detail || 'Failed to load stock'))
      .finally(() => setLoading(false))
  }, [symbol])

  if (loading) return <LoadingSpinner size="lg" label={`Loading ${symbol}…`} />
  if (error) return <div className="max-w-7xl mx-auto px-4 py-6"><ErrorCard message={error} /></div>
  if (!stock) return null

  const { indicators: ind, prediction: pred } = stock
  const isUp = (stock.perc_change ?? 0) >= 0

  const candleSeries = [{
    name: symbol,
    type: 'candlestick',
    data: candles.map(c => ({ x: c.ts, y: [c.open, c.high, c.low, c.close] })),
  }]

  const ema9Series = candles.filter(c => c.ema9).map(c => ({ x: c.ts, y: c.ema9 }))
  const ema21Series = candles.filter(c => c.ema21).map(c => ({ x: c.ts, y: c.ema21 }))

  const chartOptions: ApexOptions = {
    chart: {
      type: 'candlestick',
      background: 'transparent',
      toolbar: { show: true, tools: { download: false } },
      zoom: { enabled: true },
      animations: { enabled: false },
    },
    theme: { mode: 'dark' },
    xaxis: {
      type: 'datetime',
      labels: { style: { colors: '#64748b', fontSize: '11px' } },
      axisBorder: { color: '#1c2e4a' },
      axisTicks: { color: '#1c2e4a' },
    },
    yaxis: {
      labels: {
        style: { colors: '#64748b', fontSize: '11px' },
        formatter: (v: number) => '₹' + v.toFixed(0),
      },
      tooltip: { enabled: true },
    },
    grid: { borderColor: '#1c2e4a', strokeDashArray: 3 },
    plotOptions: {
      candlestick: {
        colors: { upward: '#00c77a', downward: '#f43f5e' },
        wick: { useFillColor: true },
      },
    },
    tooltip: {
      theme: 'dark',
      x: { format: 'dd MMM yyyy' },
    },
    annotations: {
      yaxis: ind.bb_upper ? [
        { y: ind.bb_upper, borderColor: '#3b82f620', label: { text: 'BB Upper', style: { color: '#3b82f6', background: 'transparent', fontSize: '10px' } } },
        { y: ind.bb_lower!, borderColor: '#f43f5e20', label: { text: 'BB Lower', style: { color: '#f43f5e', background: 'transparent', fontSize: '10px' } } },
      ] : [],
    },
  }

  const volumeOptions: ApexOptions = {
    chart: { type: 'bar', background: 'transparent', toolbar: { show: false }, animations: { enabled: false } },
    theme: { mode: 'dark' },
    xaxis: { type: 'datetime', labels: { show: false } },
    yaxis: { labels: { style: { colors: '#64748b', fontSize: '10px' }, formatter: (v: number) => v >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : (v / 1e3).toFixed(0) + 'K' } },
    grid: { borderColor: '#1c2e4a', strokeDashArray: 3 },
    plotOptions: { bar: { columnWidth: '80%' } },
    colors: ['#1d6feb66'],
    tooltip: { theme: 'dark', x: { format: 'dd MMM yyyy' } },
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-5 animate-fadeIn">
      {/* Back */}
      <Link to="/" className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-white transition-colors w-fit">
        <ArrowLeft size={14} /> Back
      </Link>

      {/* Header */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold font-mono">{stock.symbol}</h1>
              <SignalBadge signal={ind.supertrend_signal} size="md" />
            </div>
            <p className="text-xs text-slate-500 mt-1">NSE · {stock.latest_date}</p>
          </div>
          <div className="flex items-end gap-4">
            <div>
              <div className="text-3xl font-bold num">
                ₹{stock.close_price.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
              </div>
              <div className={`flex items-center gap-1 num text-sm mt-0.5 ${isUp ? 'up' : 'dn'}`}>
                {isUp ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                {stock.perc_change > 0 ? '+' : ''}{stock.perc_change}%
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-slate-500">O: <span className="num text-slate-300">₹{stock.open_price}</span></div>
              <div className="text-xs text-slate-500">H: <span className="num text-bullish">₹{stock.high_price}</span></div>
              <div className="text-xs text-slate-500">L: <span className="num text-bearish">₹{stock.low_price}</span></div>
            </div>
            <div className="text-right text-xs text-slate-500">
              <div>Vol: <span className="num text-slate-300">{(stock.ttl_trd_qnty / 1000).toFixed(0)}K</span></div>
              <div>Deliv: <span className="num text-slate-300">{stock.deliv_per}%</span></div>
            </div>
          </div>
        </div>
      </div>

      {/* Prediction Card */}
      <PredictionCard pred={pred} />

      {/* Chart */}
      {candles.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-3">
            <Activity size={14} className="text-primary-light" />
            <h2 className="font-semibold text-sm">Price Chart</h2>
            <span className="text-xs text-slate-500 ml-auto">{candles.length} sessions</span>
          </div>
          <ReactApexChart
            options={{
              ...chartOptions,
              series: [
                ...candleSeries,
                { name: 'EMA 9', type: 'line', data: ema9Series },
                { name: 'EMA 21', type: 'line', data: ema21Series },
              ] as any,
            }}
            series={[
              ...candleSeries,
              { name: 'EMA 9', type: 'line', data: ema9Series, color: '#f59e0b' },
              { name: 'EMA 21', type: 'line', data: ema21Series, color: '#3b82f6' },
            ] as any}
            type="candlestick"
            height={320}
          />
          <div className="mt-1">
            <ReactApexChart
              options={volumeOptions}
              series={[{ name: 'Volume', data: candles.map(c => ({ x: c.ts, y: c.volume })) }]}
              type="bar"
              height={80}
            />
          </div>
        </div>
      )}

      {/* Indicators Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        <EmaCard ind={ind} price={stock.close_price} />
        <RsiCard rsi7={ind.rsi7} rsi14={ind.rsi14} />
        <MacdCard macd={ind.macd} sig={ind.macd_signal_line} hist={ind.macd_histogram} />
        <SuperTrendCard ind={ind} />
        <BollingerCard ind={ind} price={stock.close_price} />
        <CandlePatternCard ind={ind} />
      </div>
    </div>
  )
}

function PredictionCard({ pred }: { pred: StockDetailType['prediction'] }) {
  const isStrong = pred.signal.includes('STRONG')
  const isBuy = pred.signal.includes('BUY')
  const isSell = pred.signal.includes('SELL')

  const colorCls = isBuy ? 'border-bullish/30 bg-bullish/5' : isSell ? 'border-bearish/30 bg-bearish/5' : 'border-hold/20 bg-hold/5'
  const barCls = isBuy ? 'bg-bullish' : isSell ? 'bg-bearish' : 'bg-hold'

  return (
    <div className={`card border ${colorCls}`}>
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-sm text-slate-300">Signal Analysis</h2>
        <SignalBadge signal={pred.signal} size="md" />
      </div>
      <div className="flex items-end gap-4 mb-4">
        <div>
          <div className="text-xs text-slate-500 mb-1">Composite Score</div>
          <div className={`text-3xl font-bold num ${isBuy ? 'text-bullish' : isSell ? 'text-bearish' : 'text-hold'}`}>
            {pred.score > 0 ? '+' : ''}{pred.score}
          </div>
        </div>
        <div className="flex-1">
          <div className="flex justify-between text-xs text-slate-500 mb-1">
            <span>Confidence</span>
            <span className="num">{pred.confidence}%</span>
          </div>
          <div className="h-2 bg-surface-3 rounded-full overflow-hidden">
            <div className={`h-full rounded-full transition-all ${barCls} ${isStrong ? 'opacity-100' : 'opacity-70'}`}
              style={{ width: `${pred.confidence}%` }} />
          </div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {pred.factors.map((f, i) => (
          <span key={i} className="text-xs bg-surface-3 border border-rim text-slate-400 px-2 py-1 rounded-md">
            {f}
          </span>
        ))}
      </div>
      <p className="text-xs text-slate-600 mt-3">
        * Signal computed from EMA, SuperTrend, RSI, MACD, BB, and volume indicators. Not financial advice.
      </p>
    </div>
  )
}

function EmaCard({ ind, price }: { ind: StockDetailType['indicators']; price: number }) {
  const emas = [
    { label: 'EMA 5', val: ind.ema5 },
    { label: 'EMA 9', val: ind.ema9 },
    { label: 'EMA 21', val: ind.ema21 },
    { label: 'EMA 50', val: ind.ema50 },
    { label: 'EMA 100', val: ind.ema100 },
    { label: 'EMA 200', val: ind.ema200 },
  ]
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">EMA Levels</h3>
        <span className={`text-xs num font-medium ${(ind.ema_strength ?? 0) > 0 ? 'text-bullish' : 'text-bearish'}`}>
          Strength: {(ind.ema_strength ?? 0) > 0 ? '+' : ''}{ind.ema_strength?.toFixed(3)}
        </span>
      </div>
      <div className="space-y-2">
        {emas.map(e => e.val && (
          <div key={e.label} className="flex items-center justify-between text-xs">
            <span className="text-slate-500">{e.label}</span>
            <div className="flex items-center gap-2">
              <span className="num text-slate-300">₹{e.val.toFixed(2)}</span>
              <span className={`num ${price > e.val ? 'text-bullish' : 'text-bearish'} text-[10px]`}>
                {price > e.val ? '▲' : '▼'}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function RsiCard({ rsi7, rsi14 }: { rsi7: number | null; rsi14: number | null }) {
  const zone = (v: number | null) => v == null ? 'NEUTRAL' : v > 70 ? 'OVERBOUGHT' : v < 30 ? 'OVERSOLD' : 'NEUTRAL'
  const zoneCls = (v: number | null) => v == null ? '' : v > 70 ? 'text-bearish' : v < 30 ? 'text-bullish' : 'text-slate-400'

  return (
    <div className="card">
      <h3 className="text-sm font-semibold mb-3">RSI</h3>
      <div className="space-y-3">
        {[{ label: 'RSI 7', val: rsi7 }, { label: 'RSI 14', val: rsi14 }].map(r => (
          <div key={r.label}>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-slate-500">{r.label}</span>
              <span className={`num font-medium ${zoneCls(r.val)}`}>
                {r.val?.toFixed(1)} <span className="text-[10px] opacity-70">{zone(r.val)}</span>
              </span>
            </div>
            <div className="h-1.5 bg-surface-3 rounded-full overflow-hidden">
              <div
                className="h-full rounded-full"
                style={{
                  width: `${r.val ?? 50}%`,
                  background: (r.val ?? 50) > 70 ? '#f43f5e' : (r.val ?? 50) < 30 ? '#00c77a' : '#1d6feb',
                }}
              />
            </div>
          </div>
        ))}
        <div className="flex justify-between text-[10px] text-slate-600 pt-1">
          <span>0 — Oversold</span><span>50</span><span>Overbought — 100</span>
        </div>
      </div>
    </div>
  )
}

function MacdCard({ macd, sig, hist }: { macd: number | null; sig: number | null; hist: number | null }) {
  const isBull = (hist ?? 0) > 0
  return (
    <div className="card">
      <h3 className="text-sm font-semibold mb-3">MACD</h3>
      <div className="space-y-2 text-xs">
        {[
          { l: 'MACD Line', v: macd },
          { l: 'Signal Line', v: sig },
          { l: 'Histogram', v: hist },
        ].map(r => (
          <div key={r.l} className="flex justify-between">
            <span className="text-slate-500">{r.l}</span>
            <span className={`num ${r.l === 'Histogram' ? (isBull ? 'text-bullish' : 'text-bearish') : 'text-slate-300'}`}>
              {r.v != null ? (r.v > 0 ? '+' : '') + r.v.toFixed(4) : '—'}
            </span>
          </div>
        ))}
        <div className={`mt-2 pt-2 border-t border-rim text-xs font-medium ${isBull ? 'text-bullish' : 'text-bearish'}`}>
          {isBull ? '▲ Bullish momentum' : '▼ Bearish momentum'}
        </div>
      </div>
    </div>
  )
}

function SuperTrendCard({ ind }: { ind: StockDetailType['indicators'] }) {
  const bull = ind.supertrend_direction === 1
  return (
    <div className={`card border ${bull ? 'border-bullish/20' : 'border-bearish/20'}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">SuperTrend</h3>
        <SignalBadge signal={ind.supertrend_signal} />
      </div>
      <div className="text-xs space-y-2">
        <div className="flex justify-between">
          <span className="text-slate-500">SuperTrend Value</span>
          <span className="num text-slate-300">₹{ind.supertrend?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">ATR (20)</span>
          <span className="num text-slate-300">{ind.atr20?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">VWAP</span>
          <span className="num text-slate-300">₹{ind.vwap?.toFixed(2)}</span>
        </div>
        <div className="flex justify-between mt-2 pt-2 border-t border-rim">
          <span className="text-slate-500">VT Signal</span>
          <SignalBadge signal={ind.vt_signal} size="xs" />
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">VT Trend</span>
          <SignalBadge signal={ind.vt_trend} size="xs" />
        </div>
      </div>
    </div>
  )
}

function BollingerCard({ ind, price }: { ind: StockDetailType['indicators']; price: number }) {
  const upper = ind.bb_upper ?? 0
  const lower = ind.bb_lower ?? 0
  const basis = ind.bb_basis ?? 0
  const range = upper - lower
  const pos = range > 0 ? ((price - lower) / range) * 100 : 50

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Bollinger Bands</h3>
        <SignalBadge signal={ind.bbs_signal} size="xs" />
      </div>
      <div className="text-xs space-y-1.5 mb-3">
        <div className="flex justify-between"><span className="text-slate-500">Upper</span><span className="num text-bearish">₹{upper.toFixed(2)}</span></div>
        <div className="flex justify-between"><span className="text-slate-500">Middle</span><span className="num text-slate-300">₹{basis.toFixed(2)}</span></div>
        <div className="flex justify-between"><span className="text-slate-500">Lower</span><span className="num text-bullish">₹{lower.toFixed(2)}</span></div>
      </div>
      <div className="relative h-2 bg-surface-3 rounded-full overflow-hidden">
        <div className="absolute inset-y-0 bg-primary/20 rounded-full" style={{ left: '0%', width: '100%' }} />
        <div className="absolute top-0 w-1.5 h-full bg-white rounded-full -translate-x-1/2" style={{ left: `${Math.min(Math.max(pos, 2), 98)}%` }} />
      </div>
      <div className="flex justify-between text-[10px] text-slate-600 mt-1">
        <span>Lower Band</span><span>Position: {pos.toFixed(0)}%</span><span>Upper Band</span>
      </div>
    </div>
  )
}

function CandlePatternCard({ ind }: { ind: StockDetailType['indicators'] }) {
  const fmt = (s: string | null) => (s ?? 'NO_PATTERN').replace(/_/g, ' ')
  const isBullPat = (s: string | null) => s && s !== 'NO_PATTERN' && /BULL|MORNING|WHITE|HAMMER/i.test(s)
  const isBearPat = (s: string | null) => s && s !== 'NO_PATTERN' && /BEAR|EVENING|CROW|HANG/i.test(s)

  return (
    <div className="card">
      <h3 className="text-sm font-semibold mb-3">Candlestick Patterns</h3>
      <div className="space-y-2 text-xs">
        <div className="flex justify-between items-center">
          <span className="text-slate-500">Single Candle</span>
          <span className={`font-medium ${isBullPat(ind.candle_type) ? 'text-bullish' : isBearPat(ind.candle_type) ? 'text-bearish' : 'text-slate-400'}`}>
            {fmt(ind.candle_type)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500">2-Candle Pattern</span>
          <span className={`font-medium ${isBullPat(ind.two_candle_pat) ? 'text-bullish' : isBearPat(ind.two_candle_pat) ? 'text-bearish' : 'text-slate-400'}`}>
            {fmt(ind.two_candle_pat)}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500">3-Candle Pattern</span>
          <span className={`font-medium ${isBullPat(ind.three_candle_pat) ? 'text-bullish' : isBearPat(ind.three_candle_pat) ? 'text-bearish' : 'text-slate-400'}`}>
            {fmt(ind.three_candle_pat)}
          </span>
        </div>
        <div className="flex justify-between items-center mt-2 pt-2 border-t border-rim">
          <span className="text-slate-500">Money Flow (20)</span>
          <span className={`num ${(ind.money20 ?? 0) > 0 ? 'text-bullish' : 'text-bearish'}`}>
            {ind.money20 != null ? ((ind.money20 > 0 ? '+' : '') + ind.money20.toFixed(2)) : '—'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-slate-500">Rel. Volume</span>
          <span className={`num ${(ind.relvolume ?? 0) > 1.5 ? 'text-bullish' : 'text-slate-400'}`}>
            {ind.relvolume?.toFixed(2)}x
          </span>
        </div>
      </div>
    </div>
  )
}
