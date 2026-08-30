import os
import sqlite3
from pathlib import Path
from datetime import datetime
import shutil

APP_DIR = Path.home() / "GORS"
DATA_DIR = APP_DIR / "data"
BACKUP_DIR = APP_DIR / "backups"
DB_PATH = DATA_DIR / "gors.db"


def _database_url():
    """Return the production PostgreSQL URL when configured.

    Streamlit Cloud should provide DATABASE_URL through Streamlit Secrets.
    Local development remains SQLite when the secret is absent.
    """
    value = os.getenv("DATABASE_URL")
    if value:
        return value
    try:
        import streamlit as st
        value = st.secrets.get("DATABASE_URL")
        if value:
            return str(value)
    except Exception:
        pass
    return None


USE_POSTGRES = bool(_database_url())
_REFRESH_BANNER_RENDERED = False


def _last_data_updated():
    """Return the latest automated Yahoo refresh timestamp, if available."""
    try:
        with connect() as con:
            row = con.execute(
                "SELECT created_at FROM decision_history WHERE note LIKE ? ORDER BY created_at DESC LIMIT 1",
                ("Automated Yahoo Finance refresh%",),
            ).fetchone()
        if row:
            return row["created_at"] if isinstance(row, dict) else row[0]
    except Exception:
        pass
    return None


def _refresh_banner_html():
    updated = _last_data_updated()
    if updated:
        try:
            dt = datetime.fromisoformat(str(updated))
            stamp = dt.strftime("%d-%b-%Y %I:%M %p")
        except Exception:
            stamp = str(updated)
        return (
            "<div style='background:#062e24;border:1px solid #16835b;"
            "border-radius:10px;padding:9px 14px;margin:0 0 14px;"
            "color:#d1fae5;font-weight:800;font-size:.92rem'>"
            f"🟢 Last Data Updated: {stamp} IST"
            "</div>"
        )
    return (
        "<div style='background:#422006;border:1px solid #b45309;"
        "border-radius:10px;padding:9px 14px;margin:0 0 14px;"
        "color:#fef3c7;font-weight:800;font-size:.92rem'>"
        "🟡 Last Data Updated: No automated refresh recorded yet"
        "</div>"
    )


def _rewrite_db_labels(value):
    """Keep production UI terminology aligned with the configured backend."""
    if not USE_POSTGRES or not isinstance(value, str):
        return value
    replacements = {
        "SQLite → verified facts + history": "Neon PostgreSQL → verified facts + history",
        "<small>SQLite</small>": "<small>Persistent DB</small>",
        "latest verified Kite snapshot from SQLite": "latest verified Kite snapshot from the persistent database",
        "Latest Kite snapshot automatically loaded from SQLite": "Latest Kite snapshot automatically loaded from the persistent database",
        "Created consistent SQLite backup after Kite snapshot": "Recorded database persistence after Kite snapshot",
        "**SQLite = persistent memory and verified snapshots**": "**Neon PostgreSQL = persistent memory and verified snapshots**",
    }
    for old, new in replacements.items():
        value = value.replace(old, new)
    return value


# The existing dashboard predates the persistent-backend switch and contains
# a few hard-coded SQLite labels. Rewrite only those presentation strings when
# production is actually using Neon; local SQLite development is unchanged.
try:
    import streamlit as _st

    _original_markdown = _st.markdown
    _original_caption = _st.caption
    _original_info = _st.info
    _original_success = _st.success

    def _db_markdown(body, *args, **kwargs):
        global _REFRESH_BANNER_RENDERED
        body = _rewrite_db_labels(body)
        if not _REFRESH_BANNER_RENDERED:
            body = _refresh_banner_html() + body
            _REFRESH_BANNER_RENDERED = True
        return _original_markdown(body, *args, **kwargs)

    def _db_caption(body, *args, **kwargs):
        return _original_caption(_rewrite_db_labels(body), *args, **kwargs)

    def _db_info(body, *args, **kwargs):
        return _original_info(_rewrite_db_labels(body), *args, **kwargs)

    def _db_success(body, *args, **kwargs):
        return _original_success(_rewrite_db_labels(body), *args, **kwargs)

    _st.markdown = _db_markdown
    _st.caption = _db_caption
    _st.info = _db_info
    _st.success = _db_success
except Exception:
    pass


class _PostgresConnection:
    """Small compatibility wrapper so the existing DB API works on Postgres."""
    def __init__(self, url):
        import psycopg
        from psycopg.rows import dict_row
        self._con = psycopg.connect(url, row_factory=dict_row)

    def __enter__(self):
        self._con.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._con.__exit__(exc_type, exc, tb)

    @staticmethod
    def _sql(sql):
        return sql.replace("?", "%s")

    def execute(self, sql, params=None):
        return self._con.execute(self._sql(sql), params)

    def executescript(self, sql):
        for statement in sql.split(";"):
            statement = statement.strip()
            if statement:
                self._con.execute(statement)

    def close(self):
        self._con.close()


def ensure_dirs():
    if not USE_POSTGRES:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def connect():
    if USE_POSTGRES:
        return _PostgresConnection(_database_url())
    ensure_dirs()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    """Create the canonical production tables on the configured backend."""
    ensure_dirs()
    if USE_POSTGRES:
        ddl = """
        CREATE TABLE IF NOT EXISTS decision_history (
            id BIGSERIAL PRIMARY KEY,
            decision_date TEXT NOT NULL UNIQUE,
            decision TEXT NOT NULL,
            risk_state TEXT NOT NULL,
            top1 TEXT, top2 TEXT, top3 TEXT,
            note TEXT,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS journal (
            id BIGSERIAL PRIMARY KEY,
            entry_date TEXT NOT NULL,
            decision TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kite_snapshots (
            id BIGSERIAL PRIMARY KEY,
            snapshot_time TEXT NOT NULL,
            source TEXT NOT NULL,
            file_name TEXT,
            cash DOUBLE PRECISION NOT NULL DEFAULT 0,
            portfolio_value DOUBLE PRECISION NOT NULL DEFAULT 0,
            row_count INTEGER NOT NULL DEFAULT 0,
            checksum TEXT,
            raw_csv BYTEA,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kite_holdings (
            snapshot_id BIGINT NOT NULL REFERENCES kite_snapshots(id) ON DELETE CASCADE,
            etf TEXT NOT NULL,
            quantity DOUBLE PRECISION NOT NULL,
            average_price DOUBLE PRECISION,
            last_price DOUBLE PRECISION NOT NULL,
            value DOUBLE PRECISION NOT NULL,
            pnl DOUBLE PRECISION,
            isin TEXT,
            PRIMARY KEY(snapshot_id, etf)
        );
        CREATE TABLE IF NOT EXISTS integrity_events (
            id BIGSERIAL PRIMARY KEY,
            event_time TEXT NOT NULL,
            severity TEXT NOT NULL,
            check_name TEXT NOT NULL,
            message TEXT NOT NULL
        );
        """
        with connect() as con:
            con.executescript(ddl)
        return

    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS decision_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_date TEXT NOT NULL UNIQUE,
            decision TEXT NOT NULL,
            risk_state TEXT NOT NULL,
            top1 TEXT, top2 TEXT, top3 TEXT,
            note TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL, decision TEXT NOT NULL,
            note TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kite_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_time TEXT NOT NULL, source TEXT NOT NULL,
            file_name TEXT, cash REAL NOT NULL DEFAULT 0,
            portfolio_value REAL NOT NULL DEFAULT 0,
            row_count INTEGER NOT NULL DEFAULT 0, checksum TEXT,
            raw_csv BLOB, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kite_holdings (
            snapshot_id INTEGER NOT NULL, etf TEXT NOT NULL,
            quantity REAL NOT NULL, average_price REAL,
            last_price REAL NOT NULL, value REAL NOT NULL,
            pnl REAL, isin TEXT,
            PRIMARY KEY(snapshot_id, etf),
            FOREIGN KEY(snapshot_id) REFERENCES kite_snapshots(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS integrity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT NOT NULL, severity TEXT NOT NULL,
            check_name TEXT NOT NULL, message TEXT NOT NULL
        );
        """)
        cols = {r[1] for r in con.execute("PRAGMA table_info(kite_snapshots)").fetchall()}
        if "raw_csv" not in cols:
            con.execute("ALTER TABLE kite_snapshots ADD COLUMN raw_csv BLOB")


def migrate_v12_if_needed():
    if USE_POSTGRES:
        return "PostgreSQL production DB active. Local V12 migration is not required."
    ensure_dirs()
    with connect() as con:
        count = con.execute("SELECT COUNT(*) AS n FROM decision_history").fetchone()["n"]
    if count:
        return "Permanent DB already initialized."
    candidates = [Path.home() / "Downloads" / "GORS_App_V12" / "gors_v12.db", Path.home() / "Downloads" / "gors_v12.db"]
    source = next((p for p in candidates if p.exists()), None)
    if not source:
        return "No V12 database found. Started with a clean permanent DB."
    backup = BACKUP_DIR / f"pre_prod_migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy2(source, backup)
    migrated = 0
    with sqlite3.connect(source) as old, connect() as new:
        old.row_factory = sqlite3.Row
        try:
            rows = old.execute("SELECT entry_date,decision,note,created_at FROM journal").fetchall()
            for r in rows:
                new.execute("INSERT INTO journal(entry_date,decision,note,created_at) VALUES (?,?,?,?)", tuple(r))
                migrated += 1
        except sqlite3.Error:
            pass
    return f"Migrated {migrated} journal entries. Backup created at {backup}"


def save_decision(decision_date, decision, risk_state, top3, note=""):
    top3 = list(top3)[:3] + [None] * 3
    with connect() as con:
        con.execute("""INSERT INTO decision_history
        (decision_date,decision,risk_state,top1,top2,top3,note,created_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(decision_date) DO UPDATE SET decision=excluded.decision,
        risk_state=excluded.risk_state,top1=excluded.top1,top2=excluded.top2,
        top3=excluded.top3,note=excluded.note,created_at=excluded.created_at""",
        (decision_date, decision, risk_state, top3[0], top3[1], top3[2], note, datetime.now().isoformat(timespec="seconds")))


def get_decisions(limit=100):
    with connect() as con:
        rows = con.execute("SELECT decision_date,decision,risk_state,top1,top2,top3,note,created_at FROM decision_history ORDER BY decision_date DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def add_journal(entry_date, decision, note):
    with connect() as con:
        con.execute("INSERT INTO journal(entry_date,decision,note,created_at) VALUES (?,?,?,?)", (entry_date,decision,note,datetime.now().isoformat(timespec="seconds")))


def get_journal(limit=100):
    with connect() as con:
        rows = con.execute("SELECT id,entry_date,decision,note,created_at FROM journal ORDER BY entry_date DESC,id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def save_kite_snapshot(snapshot_time, source, file_name, cash, portfolio_value, row_count, checksum, rows, raw_csv=None):
    with connect() as con:
        if USE_POSTGRES:
            cur = con.execute(
                """INSERT INTO kite_snapshots
                (snapshot_time,source,file_name,cash,portfolio_value,row_count,checksum,raw_csv,created_at)
                VALUES (?,?,?,?,?,?,?,?,?) RETURNING id""",
                (snapshot_time, source, file_name, float(cash), float(portfolio_value), int(row_count), checksum,
                 raw_csv, datetime.now().isoformat(timespec="seconds")),
            )
            sid = cur.fetchone()["id"]
        else:
            cur = con.execute(
                """INSERT INTO kite_snapshots
                (snapshot_time,source,file_name,cash,portfolio_value,row_count,checksum,raw_csv,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (snapshot_time, source, file_name, float(cash), float(portfolio_value), int(row_count), checksum,
                 sqlite3.Binary(raw_csv) if raw_csv is not None else None,
                 datetime.now().isoformat(timespec="seconds")),
            )
            sid = cur.lastrowid
        for r in rows:
            con.execute(
                """INSERT INTO kite_holdings
                (snapshot_id,etf,quantity,average_price,last_price,value,pnl,isin)
                VALUES (?,?,?,?,?,?,?,?)""",
                (sid, r["etf"], float(r["quantity"]), r.get("average_price"), r.get("last_price"),
                 float(r["value"]), r.get("pnl"), r.get("isin")),
            )
    return sid


def update_kite_cash(snapshot_id, cash):
    with connect() as con:
        con.execute("UPDATE kite_snapshots SET cash=? WHERE id=?", (float(cash), int(snapshot_id)))


def latest_kite_snapshot():
    with connect() as con:
        s = con.execute("SELECT * FROM kite_snapshots ORDER BY id DESC LIMIT 1").fetchone()
        if not s:
            return None, []
        rows = con.execute("SELECT etf,quantity,average_price,last_price,value,pnl,isin FROM kite_holdings WHERE snapshot_id=? ORDER BY etf", (s["id"],)).fetchall()
    return dict(s), [dict(r) for r in rows]


def record_integrity(severity, check_name, message):
    with connect() as con:
        con.execute("INSERT INTO integrity_events(event_time,severity,check_name,message) VALUES (?,?,?,?)", (datetime.now().isoformat(timespec="seconds"),severity,check_name,message))


def get_integrity_events(limit=100):
    with connect() as con:
        rows = con.execute("SELECT event_time,severity,check_name,message FROM integrity_events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def backup_database():
    """Back up local SQLite; Neon provides durable production persistence."""
    if USE_POSTGRES:
        return None
    ensure_dirs()
    if not DB_PATH.exists():
        return None
    target = BACKUP_DIR / f"gors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    source = sqlite3.connect(DB_PATH)
    dest = sqlite3.connect(target)
    try:
        source.backup(dest)
        dest.commit()
    finally:
        dest.close(); source.close()
    return target


def backup_database_if_needed():
    if USE_POSTGRES:
        return None
    ensure_dirs()
    today = datetime.now().strftime('%Y%m%d')
    existing = sorted(BACKUP_DIR.glob(f"gors_{today}_*.db"))
    if existing:
        return existing[-1]
    return backup_database()


def db_info():
    if USE_POSTGRES:
        return "PostgreSQL (Neon production)", 0
    ensure_dirs()
    size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    return str(DB_PATH), size
