import time
from fastapi import APIRouter, Query
from database import get_db

router = APIRouter(prefix="/api/sectors", tags=["Sectors"])

_cache: dict = {}
_CACHE_TTL = 300  # 5 minutes


def _display_name(raw: str) -> str:
    return raw.replace("_", " ").title()


@router.get("")
def list_sectors():
    cached = _cache.get("sectors")
    if cached and time.time() - cached["ts"] < _CACHE_TTL:
        return cached["data"]

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT MAX(tsdate) FROM master_indicator_tb")
        latest = cur.fetchone()[0]

        # 1) All symbols on latest date — one fast scan
        cur.execute(
            "SELECT symbol, perc_change, signal FROM master_indicator_tb WHERE tsdate = ?",
            (latest,),
        )
        sym_stats: dict[str, tuple] = {r[0]: (r[1], r[2]) for r in cur.fetchall()}

        # 2) Sector → symbol mapping
        cur.execute(
            """
            SELECT ms.sid, sr.symbol
            FROM mapped_sharesector_tb mss
            JOIN shareregistry_tb sr ON sr.rid = mss.rid
            JOIN master_sector_tb ms ON ms.sid = mss.sid
            WHERE ms.level = 2
              AND mss.status = 'active'
              AND sr.status = 'active'
            """
        )
        sector_symbols: dict[int, list] = {}
        for sid, sym in cur.fetchall():
            sector_symbols.setdefault(sid, []).append(sym)

        # 3) All level-2 sectors
        cur.execute(
            "SELECT sid, sector_name, level, parent_id FROM master_sector_tb WHERE level = 2 ORDER BY sector_name"
        )
        sectors = cur.fetchall()

    # 4) Aggregate in Python — no extra DB round-trips
    result = []
    for sid, name, level, parent_id in sectors:
        symbols = sector_symbols.get(sid, [])
        if not symbols:
            continue
        advances = declines = buy_count = 0
        changes: list[float] = []
        for sym in symbols:
            stat = sym_stats.get(sym)
            if stat:
                chg, sig = stat
                if chg is not None:
                    if chg > 0:
                        advances += 1
                    elif chg < 0:
                        declines += 1
                    changes.append(chg)
                if sig and "BUY" in sig:
                    buy_count += 1
        avg_change = round(sum(changes) / len(changes), 2) if changes else 0
        result.append(
            {
                "id": sid,
                "name": name,
                "display_name": _display_name(name),
                "level": level,
                "stock_count": len(symbols),
                "advances": advances,
                "declines": declines,
                "avg_change": avg_change,
                "buy_count": buy_count,
            }
        )

    payload = {"date": f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}", "data": result}
    _cache["sectors"] = {"ts": time.time(), "data": payload}
    return payload


@router.get("/{sector_id}/stocks")
def sector_stocks(sector_id: int, limit: int = Query(100, ge=10, le=200)):
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT sector_name FROM master_sector_tb WHERE sid = ?", (sector_id,)
        )
        sec = cur.fetchone()
        if not sec:
            return {"error": "Sector not found"}
        sector_name = _display_name(sec[0])

        cur.execute("SELECT MAX(tsdate) FROM master_indicator_tb")
        latest = cur.fetchone()[0]

        cur.execute(
            """
            SELECT sr.symbol, mi.close_price, mi.perc_change, mi.signal,
                   mi.ema_strength, mi.rsi14, mi.direction, mi.relvolume,
                   mi.bbs_signal, mi.vt_signal, mi.candle_type
            FROM mapped_sharesector_tb mss
            JOIN shareregistry_tb sr ON sr.rid = mss.rid
            JOIN master_indicator_tb mi
                 ON mi.symbol = sr.symbol AND mi.tsdate = ?
            WHERE mss.sid = ?
              AND mss.status = 'active'
              AND sr.status = 'active'
            ORDER BY mi.perc_change DESC
            LIMIT ?
            """,
            (latest, sector_id, limit),
        )
        rows = cur.fetchall()

    stocks = []
    for r in rows:
        stocks.append(
            {
                "symbol": r[0],
                "close_price": round(r[1], 2) if r[1] is not None else 0,
                "perc_change": round(r[2], 2) if r[2] is not None else 0,
                "signal": r[3] or "HOLD",
                "ema_strength": round(r[4], 3) if r[4] is not None else 0,
                "rsi14": round(r[5], 1) if r[5] is not None else 50,
                "supertrend_direction": r[6] or 0,
                "rel_volume": round(r[7], 2) if r[7] is not None else 0,
                "bbs_signal": r[8] or "NEUTRAL",
                "vt_signal": r[9] or "HOLD",
                "candle_type": r[10] or "—",
            }
        )

    return {
        "sector_id": sector_id,
        "sector_name": sector_name,
        "date": f"{latest[:4]}-{latest[4:6]}-{latest[6:8]}",
        "stocks": stocks,
    }
