from fastapi import APIRouter, Query
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/screener", tags=["Screener"])


@router.get("")
def screener(
    signal: Optional[str] = Query(None, enum=["BUY", "SELL", "HOLD"]),
    supertrend: Optional[int] = Query(None, enum=[-1, 1]),
    min_rsi: Optional[float] = Query(None, ge=0, le=100),
    max_rsi: Optional[float] = Query(None, ge=0, le=100),
    min_change: Optional[float] = Query(None),
    max_change: Optional[float] = Query(None),
    min_relvolume: Optional[float] = Query(None, ge=0),
    bbs: Optional[str] = Query(None, enum=["BULL", "BEAR", "NEUTRAL"]),
    vt: Optional[str] = Query(None, enum=["BUY", "SELL", "HOLD"]),
    sort_by: str = Query("perc_change", enum=["perc_change", "rsi14", "ema_strength", "relvolume", "close_price"]),
    sort_order: str = Query("desc", enum=["asc", "desc"]),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=10, le=100),
):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(tsdate) FROM master_indicator_tb")
        latest = cur.fetchone()[0]

        conditions = ["tsdate = ?"]
        params: list = [latest]

        if signal:
            # signal values: BUY_NEW, SELL_NEW, HOLD — use LIKE for BUY/SELL
            if signal in ("BUY", "SELL"):
                conditions.append("signal LIKE ?")
                params.append(f"{signal}%")
            else:
                conditions.append("signal = ?")
                params.append(signal)
        if supertrend is not None:
            conditions.append("direction = ?")
            params.append(supertrend)
        if min_rsi is not None:
            conditions.append("rsi14 >= ?")
            params.append(min_rsi)
        if max_rsi is not None:
            conditions.append("rsi14 <= ?")
            params.append(max_rsi)
        if min_change is not None:
            conditions.append("perc_change >= ?")
            params.append(min_change)
        if max_change is not None:
            conditions.append("perc_change <= ?")
            params.append(max_change)
        if min_relvolume is not None:
            conditions.append("relvolume >= ?")
            params.append(min_relvolume)
        if bbs:
            conditions.append("bbs_signal = ?")
            params.append(bbs)
        if vt:
            if vt in ("BUY", "SELL"):
                conditions.append("vt_signal LIKE ?")
                params.append(f"%{vt}%")
            else:
                conditions.append("vt_signal = ?")
                params.append(vt)

        where = " AND ".join(conditions)
        order = f"{sort_by} {'DESC' if sort_order == 'desc' else 'ASC'}"

        cur.execute(f"SELECT COUNT(*) FROM master_indicator_tb WHERE {where}", params)
        total = cur.fetchone()[0]

        offset = (page - 1) * limit
        cur.execute(
            f"""
            SELECT symbol, close_price, perc_change, signal, rsi14,
                   ema_strength, direction, relvolume, macd_histogram,
                   candle_type, two_candle_pat, three_candle_pat,
                   bbs_signal, vt_signal, atr20, deliv_per
            FROM master_indicator_tb
            WHERE {where}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

    data = []
    for r in rows:
        data.append(
            {
                "symbol": r[0],
                "close_price": round(r[1], 2) if r[1] is not None else 0,
                "perc_change": round(r[2], 2) if r[2] is not None else 0,
                "signal": r[3] or "HOLD",
                "rsi14": round(r[4], 1) if r[4] is not None else 50,
                "ema_strength": round(r[5], 3) if r[5] is not None else 0,
                "supertrend_direction": r[6] or 0,
                "rel_volume": round(r[7], 2) if r[7] is not None else 0,
                "macd_histogram": round(r[8], 4) if r[8] is not None else 0,
                "candle_type": r[9] or "—",
                "two_candle_pat": r[10] or "NO_PATTERN",
                "three_candle_pat": r[11] or "NO_PATTERN",
                "bbs_signal": r[12] or "NEUTRAL",
                "vt_signal": r[13] or "HOLD",
                "atr20": round(r[14], 2) if r[14] is not None else 0,
                "deliv_per": round(r[15], 1) if r[15] is not None else 0,
            }
        )

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "date": f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}" if latest else "",
        "data": data,
    }
