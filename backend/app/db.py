import os
from sqlalchemy import create_engine, String, Float, BigInteger, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from . import config

if config.DB_URL.startswith("sqlite:///"):
    os.makedirs(os.path.dirname(config.DB_URL.replace("sqlite:///", "")) or ".", exist_ok=True)
engine = create_engine(config.DB_URL, future=True)
Session = sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class Bar(Base):  # stored historical data (MT5 export / CSV)
    __tablename__ = "bars"
    __table_args__ = (UniqueConstraint("symbol", "timeframe", "time"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    timeframe: Mapped[str] = mapped_column(String(4), index=True)
    time: Mapped[int] = mapped_column(BigInteger, index=True)  # unix seconds UTC
    open: Mapped[float]; high: Mapped[float]; low: Mapped[float]; close: Mapped[float]
    volume: Mapped[float] = mapped_column(Float, default=0)
    spread: Mapped[float] = mapped_column(Float, default=0)  # points, from MT5 export <SPREAD>

class Trade(Base):  # used from Phase 2
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    ticket: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    symbol: Mapped[str] = mapped_column(String(32))
    direction: Mapped[str] = mapped_column(String(4))
    volume: Mapped[float]
    entry_price: Mapped[float | None] = mapped_column(nullable=True)
    exit_price: Mapped[float | None] = mapped_column(nullable=True)
    entry_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    exit_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    profit: Mapped[float | None] = mapped_column(nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="manual")  # manual | strategy
    confidence: Mapped[float | None] = mapped_column(nullable=True)
    latency_infer_ms: Mapped[float | None] = mapped_column(nullable=True)
    latency_exec_ms: Mapped[float | None] = mapped_column(nullable=True)

class Setting(Base):  # user configuration (key = 'section.name' or 'risk')
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String)

def init_db():
    from sqlalchemy import inspect, text
    Base.metadata.create_all(engine)
    if "spread" not in [c["name"] for c in inspect(engine).get_columns("bars")]:   # migrate older databases
        with engine.begin() as cn: cn.execute(text("ALTER TABLE bars ADD COLUMN spread FLOAT DEFAULT 0"))
