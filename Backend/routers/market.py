import time
from fastapi import APIRouter, Query
from database import get_db

router = APIRouter(prefix="/api/market", tags=["Market"])

_cache: dict = {}
_CACHE_TTL = 300  # 5 minutes


def _fmt_date(ts: str) -> str:
    return f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}" if ts and len(ts) == 8 else ts


@router.get("/overview")
def market_overview():
    cached = _cache.get("overview")
    if cached and time.time() - cached["ts"] < _CACHE_TTL:
        return cached["data"]

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT MAX(tsdate) FROM master_indicator_tb")
        row = cur.fetchone()
        latest = row[0] if row else None
        if not latest:
            return {"error": "No data available"}

        # Single pass over the latest-date rows
        cur.execute(
            """
            SELECT
                COUNT(*)                                                     AS total,
                SUM(CASE WHEN perc_change > 0   THEN 1 ELSE 0 END)          AS advances,
                SUM(CASE WHEN perc_change < 0   THEN 1 ELSE 0 END)          AS declines,
                SUM(CASE WHEN signal LIKE 'BUY%'  THEN 1 ELSE 0 END)        AS buy_signals,
                SUM(CASE WHEN signal LIKE 'SELL%' THEN 1 ELSE 0 END)        AS sell_signals,
                SUM(CASE WHEN direction = 1     THEN 1 ELSE 0 END)          AS st_bullish
            FROM master_indicator_tb
            WHERE tsdate = ?
            """,
            (latest,),
        )
        r = cur.fetchone()

    total, advances, declines = int(r[0] or 0), int(r[1] or 0), int(r[2] or 0)
    buy_signals, sell_signals, st_bullish = int(r[3] or 0), int(r[4] or 0), int(r[5] or 0)

    payload = {
        "trading_date": _fmt_date(latest),
        "total_symbols": total,
        "advances": advances,
        "declines": declines,
        "unchanged": max(total - advances - declines, 0),
        "advance_decline_ratio": round(advances / max(declines, 1), 2),
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "supertrend_bullish": st_bullish,
    }
    _cache["overview"] = {"ts": time.time(), "data": payload}
    return payload


@router.get("/movers")
def market_movers(
    type: str = Query("gainers", enum=["gainers", "losers", "volume", "buysignals"]),
    limit: int = Query(10, ge=5, le=50),
):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(tsdate) FROM master_indicator_tb")
        latest = cur.fetchone()[0]

        if type == "gainers":
            order, where = "perc_change DESC", "AND perc_change > 0"
        elif type == "losers":
            order, where = "perc_change ASC", "AND perc_change < 0"
        elif type == "volume":
            order, where = "relvolume DESC", "AND relvolume IS NOT NULL AND relvolume > 0"
        else:
            order, where = "ema_strength DESC", "AND signal LIKE 'BUY%' AND direction = 1"

        cur.execute(
            f"""
            SELECT symbol, close_price, perc_change, ttl_trd_qnty,
                   signal, ema_strength, rsi14, direction, relvolume, atr20
            FROM master_indicator_tb
            WHERE tsdate = ? {where}
            ORDER BY {order}
            LIMIT ?
            """,
            (latest, limit),
        )
        rows = cur.fetchall()

    data = []
    for r in rows:
        data.append(
            {
                "symbol": r[0],
                "close_price": round(r[1], 2) if r[1] is not None else 0,
                "perc_change": round(r[2], 2) if r[2] is not None else 0,
                "volume": int(r[3]) if r[3] is not None else 0,
                "signal": r[4] or "HOLD",
                "ema_strength": round(r[5], 3) if r[5] is not None else 0,
                "rsi14": round(r[6], 1) if r[6] is not None else 50,
                "supertrend_direction": r[7] or 0,
                "rel_volume": round(r[8], 2) if r[8] is not None else 0,
                "atr20": round(r[9], 2) if r[9] is not None else 0,
            }
        )

    return {"type": type, "date": _fmt_date(latest), "data": data}


@router.get("/dates")
def trading_dates(limit: int = Query(20, ge=5, le=100)):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT tsdate FROM master_wdate_tb
            WHERE bhavdownload_flag = 1
            ORDER BY tsdate DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return [_fmt_date(r[0]) for r in rows]
