"""Stored historical data. Import MT5 exports (tab/comma CSV) or any OHLCV CSV."""
import io
import pandas as pd
from sqlalchemy import select, delete, func
from ..db import Session, Bar

def parse_csv(raw: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(raw), sep=None, engine="python")
    df.columns = [c.strip("<>").strip().lower() for c in df.columns]  # MT5 export: <DATE> <TIME> ...
    if "date" in df and "time" in df: ts = pd.to_datetime(df["date"].astype(str) + " " + df["time"].astype(str))
    elif "datetime" in df: ts = pd.to_datetime(df["datetime"])
    elif "time" in df:
        ts = pd.to_datetime(df["time"], unit="s") if pd.api.types.is_numeric_dtype(df["time"]) else pd.to_datetime(df["time"])
    else: raise ValueError("CSV needs a time column (date+time, datetime, or time)")
    vol = next((c for c in ("tickvol", "tick_volume", "volume", "vol") if c in df), None)
    out = pd.DataFrame({"time": ts.astype("datetime64[s]").astype("int64"),
                        "open": df["open"], "high": df["high"], "low": df["low"], "close": df["close"],
                        "volume": df[vol] if vol else 0.0,
                        "spread": df["spread"] if "spread" in df else 0.0})
    out = out.dropna().drop_duplicates("time").sort_values("time")
    bad = (out.high < out[["open", "close", "low"]].max(axis=1)) | (out.low > out[["open", "close", "high"]].min(axis=1))
    if bad.any(): raise ValueError(f"{int(bad.sum())} rows have inconsistent OHLC; refusing to import")
    return out

def store(symbol: str, tf: str, df: pd.DataFrame) -> int:
    rows = [dict(symbol=symbol, timeframe=tf, **r) for r in df.to_dict("records")]
    lo, hi = int(df.time.min()), int(df.time.max())
    with Session() as s, s.begin():
        # replace the covered time range (a range delete avoids SQLite's bound-variable limit on big IN lists)
        s.execute(delete(Bar).where(Bar.symbol == symbol, Bar.timeframe == tf, Bar.time.between(lo, hi)))
        for i in range(0, len(rows), 5000): s.bulk_insert_mappings(Bar, rows[i:i + 5000])
    return len(rows)

def _load_raw(symbol: str, tf: str, count: int = 1000) -> list[dict]:
    with Session() as s:
        q = select(Bar).where(Bar.symbol == symbol, Bar.timeframe == tf).order_by(Bar.time.desc()).limit(count)
        rows = list(reversed(s.scalars(q).all()))
    return [dict(time=b.time, open=b.open, high=b.high, low=b.low, close=b.close, volume=b.volume, spread=b.spread or 0.0) for b in rows]

def available() -> list[dict]:
    with Session() as s:
        q = select(Bar.symbol, Bar.timeframe, func.count(), func.min(Bar.time), func.max(Bar.time)).group_by(Bar.symbol, Bar.timeframe)
        return [dict(symbol=a, timeframe=b, bars=c, start=d, end=e) for a, b, c, d, e in s.execute(q)]

RES = {"M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}

def resample(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Aggregate M5 bars into a longer timeframe (bucket start labels; empty buckets dropped)."""
    d = df.copy(); d.index = pd.to_datetime(d.time, unit="s")
    out = d.resample(RES[tf], label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna(subset=["open"])
    sp = d.spread.where(d.spread > 0).resample(RES[tf], label="left", closed="left").mean().reindex(out.index).fillna(0.0) if "spread" in d else 0.0
    out["spread"] = sp; out["time"] = out.index.astype("datetime64[s]").astype("int64")
    return out.reset_index(drop=True)[["time", "open", "high", "low", "close", "volume", "spread"]]

def load(symbol: str, tf: str, count: int = 1000) -> list[dict]:
    rows = _load_raw(symbol, tf, count)
    if rows or tf not in RES: return rows
    m5 = _load_raw(symbol, "M5", 10**7)
    return resample(pd.DataFrame(m5), tf).tail(count).to_dict("records") if m5 else []
