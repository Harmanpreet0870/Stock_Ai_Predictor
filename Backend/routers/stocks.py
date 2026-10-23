from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from database import get_db

router = APIRouter(prefix="/api/stocks", tags=["Stocks"])


def _fmt_date(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if ts and len(ts) == 8 else ts


def _ts_to_ms(ts: str) -> int:
    """Convert YYYYMMDD to Unix ms for ApexCharts."""
    try:
        return int(datetime.strptime(ts, "%Y%m%d").timestamp() * 1000)
    except Exception:
        return 0


def _compute_prediction(row) -> dict:
    score = 0.0
    factors: list[str] = []

    direction = row["direction"] or 0
    if direction == 1:
        score += 2.5
        factors.append("SuperTrend Bullish")
    elif direction == -1:
        score -= 2.5
        factors.append("SuperTrend Bearish")

    ema_str = row["ema_strength"] or 0.0
    if ema_str > 1.0:
        score += 2.0
        factors.append("Strong EMA Alignment")
    elif ema_str > 0:
        score += 1.0
        factors.append("Moderate EMA Bullish")
    elif ema_str < -1.0:
        score -= 2.0
        factors.append("Weak EMA Alignment")
    elif ema_str < 0:
        score -= 1.0
        factors.append("Moderate EMA Bearish")

    rsi = row["rsi14"] or 50.0
    if rsi > 60:
        score += 1.0
        factors.append(f"RSI Bullish ({rsi:.0f})")
    elif rsi < 40:
        score -= 1.0
        factors.append(f"RSI Bearish ({rsi:.0f})")

    macd_hist = row["macd_histogram"] or 0.0
    macd_val = row["macd"] or 0.0
    macd_sig = row["macd_signal"] or 0.0
    if macd_val > macd_sig and macd_hist > 0:
        score += 1.5
        factors.append("MACD Bullish Crossover")
    elif macd_val < macd_sig and macd_hist < 0:
        score -= 1.5
        factors.append("MACD Bearish Crossover")

    bbs = (row["bbs_signal"] or "NEUTRAL").upper()
    if bbs == "BULL":
        score += 1.0
        factors.append("BB Bull Zone")
    elif bbs == "BEAR":
        score -= 1.0
        factors.append("BB Bear Zone")

    vt = (row["vt_signal"] or "HOLD").upper()
    if "BUY" in vt:
        score += 1.0
        factors.append("Volatility Trail Buy")
    elif "SELL" in vt:
        score -= 1.0
        factors.append("Volatility Trail Sell")

    three_pat = (row["three_candle_pat"] or "NO_PATTERN").upper()
    two_pat = (row["two_candle_pat"] or "NO_PATTERN").upper()
    bullish_kw = ("MORNING", "WHITE", "BULL", "HAMMER", "ENGULF")
    bearish_kw = ("EVENING", "CROW", "BEAR", "DOJI_BEAR", "HANG")
    for pat in (three_pat, two_pat):
        if pat != "NO_PATTERN":
            if any(k in pat for k in bullish_kw):
                score += 0.5
                factors.append(f"Pattern: {pat.replace('_', ' ').title()}")
            elif any(k in pat for k in bearish_kw):
                score -= 0.5
                factors.append(f"Pattern: {pat.replace('_', ' ').title()}")

    relvol = row["relvolume"] or 0.0
    if relvol > 1.5:
        if score > 0:
            score += 0.5
            factors.append("High Volume Confirmation")
        elif score < 0:
            score -= 0.5
            factors.append("High Volume Breakdown")

    max_score = 10.5
    if score >= 3.5:
        signal = "STRONG BUY" if score >= 6.5 else "BUY"
    elif score <= -3.5:
        signal = "STRONG SELL" if score <= -6.5 else "SELL"
    else:
        signal = "HOLD"

    confidence = min(abs(score) / max_score * 100, 100)
    return {
        "signal": signal,
        "score": round(score, 2),
        "confidence": round(confidence, 1),
        "factors": factors[:5],
    }


@router.get("/search")
def search_stocks(q: str = Query(..., min_length=1), limit: int = Query(10, ge=1, le=30)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT symbol FROM shareregistry_tb
            WHERE symbol LIKE ? AND status = 'active'
            ORDER BY symbol
            LIMIT ?
            """,
            (f"{q.upper()}%", limit),
        )
        rows = cur.fetchall()
        if len(rows) < limit:
            cur.execute(
                """
                SELECT symbol FROM shareregistry_tb
                WHERE symbol LIKE ? AND status = 'active'
                  AND symbol NOT LIKE ?
                ORDER BY symbol
                LIMIT ?
                """,
                (f"%{q.upper()}%", f"{q.upper()}%", limit - len(rows)),
            )
            rows += cur.fetchall()
    return [{"symbol": r[0]} for r in rows]


@router.get("/{symbol}")
def stock_detail(symbol: str):
    symbol = symbol.upper()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM master_indicator_tb
            WHERE symbol = ?
            ORDER BY tsdate DESC
            LIMIT 1
            """,
            (symbol,),
        )
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Symbol '{symbol}' not found")

    prediction = _compute_prediction(row)

    def _r(v, d=2):
        return round(v, d) if v is not None else None

    return {
        "symbol": row["symbol"],
        "latest_date": _fmt_date(row["tsdate"]),
        "open_price": _r(row["open_price"]),
        "high_price": _r(row["high_price"]),
        "low_price": _r(row["low_price"]),
        "close_price": _r(row["close_price"]),
        "perc_change": _r(row["perc_change"]),
        "ttl_trd_qnty": int(row["ttl_trd_qnty"]) if row["ttl_trd_qnty"] else 0,
        "deliv_per": _r(row["deliv_per"]),
        "indicators": {
            "ema5": _r(row["ema5"]),
            "ema9": _r(row["ema9"]),
            "ema21": _r(row["ema21"]),
            "ema50": _r(row["ema50"]),
            "ema100": _r(row["ema100"]),
            "ema200": _r(row["ema200"]),
            "ema_strength": _r(row["ema_strength"], 4),
            "supertrend": _r(row["supertrend"]),
            "supertrend_direction": row["direction"],
            "supertrend_signal": row["signal"],
            "rsi7": _r(row["rsi7"], 1),
            "rsi14": _r(row["rsi14"], 1),
            "macd": _r(row["macd"], 4),
            "macd_signal_line": _r(row["macd_signal"], 4),
            "macd_histogram": _r(row["macd_histogram"], 4),
            "bb_upper": _r(row["bb_upper"]),
            "bb_basis": _r(row["bb_basis"]),
            "bb_lower": _r(row["bb_lower"]),
            "bbs_signal": row["bbs_signal"],
            "vt_signal": row["vt_signal"],
            "vt_trend": row["vt_trend"],
            "candle_type": row["candle_type"],
            "two_candle_pat": row["two_candle_pat"],
            "three_candle_pat": row["three_candle_pat"],
            "relvolume": _r(row["relvolume"], 2),
            "money20": _r(row["money20"]),
            "atr20": _r(row["atr20"]),
            "vwap": _r(row["vwap"]),
        },
        "prediction": prediction,
    }


@router.get("/{symbol}/history")
def stock_history(symbol: str, days: int = Query(120, ge=20, le=300)):
    symbol = symbol.upper()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tsdate, open_price, high_price, low_price, close_price, ttl_trd_qnty,
                   ema9, ema21, supertrend, direction
            FROM master_indicator_tb
            WHERE symbol = ?
            ORDER BY tsdate ASC
            LIMIT ?
            """,
            (symbol, days),
        )
        rows = cur.fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No history for '{symbol}'")

    candles = []
    for r in rows:
        candles.append(
            {
                "ts": _ts_to_ms(r[0]),
                "date": _fmt_date(r[0]),
                "open": round(r[1], 2) if r[1] else 0,
                "high": round(r[2], 2) if r[2] else 0,
                "low": round(r[3], 2) if r[3] else 0,
                "close": round(r[4], 2) if r[4] else 0,
                "volume": int(r[5]) if r[5] else 0,
                "ema9": round(r[6], 2) if r[6] else None,
                "ema21": round(r[7], 2) if r[7] else None,
                "supertrend": round(r[8], 2) if r[8] else None,
                "st_dir": r[9],
            }
        )
    return candles
