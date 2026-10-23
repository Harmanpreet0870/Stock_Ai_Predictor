from fastapi import APIRouter, Query
from typing import Optional
from database import get_db

router = APIRouter(prefix="/api/patterns", tags=["Patterns"])


@router.get("")
def list_patterns(
    symbol: Optional[str] = Query(None),
    sentiment: Optional[str] = Query(None, enum=["bullish", "bearish"]),
    pattern_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=10, le=200),
    page: int = Query(1, ge=1),
):
    with get_db() as conn:
        cur = conn.cursor()

        conditions = ["1=1"]
        params: list = []

        if symbol:
            conditions.append("symbol = ?")
            params.append(symbol.upper())
        if sentiment:
            conditions.append("sentiment = ?")
            params.append(sentiment)
        if pattern_type:
            conditions.append("pattern_type = ?")
            params.append(pattern_type)

        where = " AND ".join(conditions)

        cur.execute(f"SELECT COUNT(*) FROM pattern_tb WHERE {where}", params)
        total = cur.fetchone()[0]

        offset = (page - 1) * limit
        cur.execute(
            f"""
            SELECT symbol, pattern_type, signal, sentiment,
                   entry, stop_loss, target, risk_reward, score, trade_date
            FROM pattern_tb
            WHERE {where}
            ORDER BY trade_date DESC
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        )
        rows = cur.fetchall()

    data = []
    for r in rows:
        entry = round(r[4], 2) if r[4] is not None else 0
        sl = round(r[5], 2) if r[5] is not None else 0
        tgt = round(r[6], 2) if r[6] is not None else 0
        rr = round(r[7], 2) if r[7] is not None else 0
        score = round(r[8] * 100, 1) if r[8] is not None else None
        raw_date = r[9] or ""

        # trade_date may be YYYYMMDD or YYYY-MM-DD
        if raw_date and len(raw_date) == 8 and raw_date.isdigit():
            fmt_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
        else:
            fmt_date = raw_date

        risk_pct = round(abs(entry - sl) / entry * 100, 2) if entry else 0

        data.append(
            {
                "symbol": r[0],
                "pattern_type": r[1],
                "signal": r[2],
                "sentiment": r[3],
                "entry": entry,
                "stop_loss": sl,
                "target": tgt,
                "risk_reward": rr,
                "score": score,
                "risk_pct": risk_pct,
                "trade_date": fmt_date,
            }
        )

    # Unique pattern types for filter dropdown
    cur2 = None
    with get_db() as conn:
        cur2 = conn.cursor()
        cur2.execute("SELECT DISTINCT pattern_type FROM pattern_tb ORDER BY pattern_type")
        pattern_types = [r[0] for r in cur2.fetchall()]

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "pages": (total + limit - 1) // limit,
        "pattern_types": pattern_types,
        "data": data,
    }
