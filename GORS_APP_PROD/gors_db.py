import sqlite3
from pathlib import Path
from datetime import datetime
import shutil

APP_DIR = Path.home() / "GORS"
DATA_DIR = APP_DIR / "data"
BACKUP_DIR = APP_DIR / "backups"
DB_PATH = DATA_DIR / "gors.db"


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def connect():
    ensure_dirs()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    """Create only the canonical production tables.

    Architecture rule:
      * SQLite stores verified facts and history.
      * Python owns strategy/decision calculations.
      * Kite snapshots are the actual portfolio truth.
      * UI is only the display/control layer.

    Legacy tables from older GORS versions are intentionally not used or
    recreated here. Existing legacy tables are left untouched so an upgrade
    cannot destroy historical data.
    """
    ensure_dirs()
    with connect() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS decision_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_date TEXT NOT NULL,
            decision TEXT NOT NULL,
            risk_state TEXT NOT NULL,
            top1 TEXT,
            top2 TEXT,
            top3 TEXT,
            note TEXT,
            created_at TEXT NOT NULL,
            UNIQUE(decision_date)
        );
        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_date TEXT NOT NULL,
            decision TEXT NOT NULL,
            note TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kite_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_time TEXT NOT NULL,
            source TEXT NOT NULL,
            file_name TEXT,
            cash REAL NOT NULL DEFAULT 0,
            portfolio_value REAL NOT NULL DEFAULT 0,
            row_count INTEGER NOT NULL DEFAULT 0,
            checksum TEXT,
            raw_csv BLOB,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS kite_holdings (
            snapshot_id INTEGER NOT NULL,
            etf TEXT NOT NULL,
            quantity REAL NOT NULL,
            average_price REAL,
            last_price REAL NOT NULL,
            value REAL NOT NULL,
            pnl REAL,
            isin TEXT,
            PRIMARY KEY(snapshot_id, etf),
            FOREIGN KEY(snapshot_id) REFERENCES kite_snapshots(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS integrity_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_time TEXT NOT NULL,
            severity TEXT NOT NULL,
            check_name TEXT NOT NULL,
            message TEXT NOT NULL
        );
        """)

        # Safe in-place schema migration for existing production DBs.
        # Never drop tables or delete historical rows.
        cols = {r[1] for r in con.execute("PRAGMA table_info(kite_snapshots)").fetchall()}
        if "raw_csv" not in cols:
            con.execute("ALTER TABLE kite_snapshots ADD COLUMN raw_csv BLOB")


def migrate_v12_if_needed():
    """One-time migration of safe historical records from the old V12 DB.

    Holdings/transactions from older GORS versions are deliberately not
    migrated into the production truth model. Current holdings must come
    from Kite snapshots, not a second internal portfolio ledger.
    """
    ensure_dirs()
    with connect() as con:
        count = con.execute("SELECT COUNT(*) AS n FROM decision_history").fetchone()["n"]
    if count:
        return "Permanent DB already initialized."
    candidates = [
        Path.home() / "Downloads" / "GORS_App_V12" / "gors_v12.db",
        Path.home() / "Downloads" / "gors_v12.db",
    ]
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
                new.execute(
                    "INSERT INTO journal(entry_date,decision,note,created_at) VALUES (?,?,?,?)",
                    tuple(r)
                )
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
    """Append an immutable Kite portfolio snapshot.

    A new row is created for every import; existing snapshots are never
    updated or replaced. The original CSV bytes are retained in SQLite so
    the imported broker fact can be audited/recovered later.
    """
    with connect() as con:
        cur = con.execute(
            """INSERT INTO kite_snapshots
            (snapshot_time,source,file_name,cash,portfolio_value,row_count,checksum,raw_csv,created_at)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (snapshot_time, source, file_name, float(cash), float(portfolio_value),
             int(row_count), checksum, sqlite3.Binary(raw_csv) if raw_csv is not None else None,
             datetime.now().isoformat(timespec="seconds")),
        )
        sid = cur.lastrowid
        for r in rows:
            con.execute(
                """INSERT INTO kite_holdings
                (snapshot_id,etf,quantity,average_price,last_price,value,pnl,isin)
                VALUES (?,?,?,?,?,?,?,?)""",
                (sid, r["etf"], float(r["quantity"]), r.get("average_price"),
                 r.get("last_price"), float(r["value"]), r.get("pnl"), r.get("isin")),
            )
    return sid


def update_kite_cash(snapshot_id, cash):
    with connect() as con:
        con.execute(
            "UPDATE kite_snapshots SET cash=? WHERE id=?",
            (float(cash), int(snapshot_id))
        )

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
    """Create a consistent SQLite backup, including WAL contents.

    A raw copy of gors.db is unsafe while SQLite is using WAL mode. The
    sqlite3 backup API produces a transactionally consistent backup without
    disturbing the live database.
    """
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
        dest.close()
        source.close()
    return target


def backup_database_if_needed():
    """Create at most one automatic DB backup per calendar day."""
    ensure_dirs()
    today = datetime.now().strftime('%Y%m%d')
    existing = sorted(BACKUP_DIR.glob(f"gors_{today}_*.db"))
    if existing:
        return existing[-1]
    return backup_database()


def db_info():
    ensure_dirs()
    size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    return str(DB_PATH),size
