import sqlite3
import threading
import atexit
from pathlib import Path
from datetime import datetime

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "performance_journal.db"

_local = threading.local()


def _get_conn():
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.conn = conn
    return conn


def init_db():
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            setup TEXT NOT NULL,
            signal TEXT NOT NULL,
            price_at_signal REAL NOT NULL,
            stop_loss REAL NOT NULL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            entry_zone_low REAL,
            entry_zone_high REAL,
            entry_strategy TEXT,
            timing TEXT,
            score REAL,
            prob_tp1 TEXT,
            prob_tp2 TEXT,
            prob_tp3 TEXT,
            prob_sl TEXT,
            avg_days_tp1 REAL,
            avg_days_tp2 REAL,
            avg_days_tp3 REAL,
            market_regime TEXT,
            stock_regime TEXT,
            adx REAL,
            atr REAL,
            screen_date TIMESTAMP NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS trade_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER REFERENCES predictions(id),
            ticker TEXT NOT NULL,
            entry_date TIMESTAMP,
            entry_price REAL,
            exit_date TIMESTAMP,
            exit_price REAL,
            exit_reason TEXT,
            return_pct REAL,
            return_abs REAL,
            days_held INTEGER,
            hit_tp1 INTEGER DEFAULT 0,
            hit_tp2 INTEGER DEFAULT 0,
            hit_tp3 INTEGER DEFAULT 0,
            hit_sl INTEGER DEFAULT 0,
            max_favorable REAL,
            max_adverse REAL,
            status TEXT DEFAULT 'OPEN',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS portfolio_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TIMESTAMP NOT NULL,
            cash REAL NOT NULL,
            positions_value REAL NOT NULL,
            total_value REAL NOT NULL,
            num_positions INTEGER,
            ihsg_value REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_predictions_ticker ON predictions(ticker);
        CREATE INDEX IF NOT EXISTS idx_predictions_status ON predictions(status);
        CREATE INDEX IF NOT EXISTS idx_predictions_screen_date ON predictions(screen_date);
        CREATE INDEX IF NOT EXISTS idx_trade_results_prediction_id ON trade_results(prediction_id);
        CREATE INDEX IF NOT EXISTS idx_trade_results_ticker ON trade_results(ticker);
        CREATE INDEX IF NOT EXISTS idx_trade_results_status ON trade_results(status);
    """)

    current_version = conn.execute(
        "SELECT MAX(version) FROM schema_version"
    ).fetchone()[0]
    if current_version is None:
        try:
            conn.execute("INSERT INTO schema_version (version) VALUES (1)")
        except sqlite3.IntegrityError:
            pass
    conn.commit()


def clear_backtest_data():
    conn = _get_conn()
    conn.execute("DELETE FROM trade_results")
    conn.execute("DELETE FROM predictions")
    conn.commit()


def log_prediction(data):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO predictions (
            ticker, setup, signal, price_at_signal, stop_loss,
            tp1, tp2, tp3,
            entry_zone_low, entry_zone_high, entry_strategy,
            timing, score,
            prob_tp1, prob_tp2, prob_tp3, prob_sl,
            avg_days_tp1, avg_days_tp2, avg_days_tp3,
            market_regime, stock_regime, adx, atr,
            screen_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
    """, (
        data["ticker"], data["setup"], data["signal"],
        data["price_at_signal"], data["stop_loss"],
        data.get("tp1"), data.get("tp2"), data.get("tp3"),
        data.get("entry_zone_low"), data.get("entry_zone_high"),
        data.get("entry_strategy"), data.get("timing"),
        data.get("score"),
        data.get("prob_tp1"), data.get("prob_tp2"),
        data.get("prob_tp3"), data.get("prob_sl"),
        data.get("avg_days_tp1"), data.get("avg_days_tp2"),
        data.get("avg_days_tp3"),
        data.get("market_regime"), data.get("stock_regime"),
        data.get("adx"), data.get("atr"),
        data.get("screen_date", pd.Timestamp.now().isoformat()),
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def log_predictions_batch(predictions):
    if not predictions:
        return []

    conn = _get_conn()
    rows = []
    for data in predictions:
        rows.append((
            data["ticker"], data["setup"], data["signal"],
            data["price_at_signal"], data["stop_loss"],
            data.get("tp1"), data.get("tp2"), data.get("tp3"),
            data.get("entry_zone_low"), data.get("entry_zone_high"),
            data.get("entry_strategy"), data.get("timing"),
            data.get("score"),
            data.get("prob_tp1"), data.get("prob_tp2"),
            data.get("prob_tp3"), data.get("prob_sl"),
            data.get("avg_days_tp1"), data.get("avg_days_tp2"),
            data.get("avg_days_tp3"),
            data.get("market_regime"), data.get("stock_regime"),
            data.get("adx"), data.get("atr"),
            data.get("screen_date", pd.Timestamp.now().isoformat()),
        ))

    conn.executemany("""
        INSERT INTO predictions (
            ticker, setup, signal, price_at_signal, stop_loss,
            tp1, tp2, tp3,
            entry_zone_low, entry_zone_high, entry_strategy,
            timing, score,
            prob_tp1, prob_tp2, prob_tp3, prob_sl,
            avg_days_tp1, avg_days_tp2, avg_days_tp3,
            market_regime, stock_regime, adx, atr,
            screen_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
    """, rows)
    conn.commit()

    last_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    return list(range(last_id - len(rows) + 1, last_id + 1))


def get_pending_predictions():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM predictions WHERE status = 'PENDING' ORDER BY screen_date"
    ).fetchall()
    return [dict(r) for r in rows]


def get_active_predictions():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM predictions WHERE status = 'ACTIVE' ORDER BY screen_date"
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_predictions(filters=None):
    conn = _get_conn()
    query = "SELECT * FROM predictions"
    params = []
    conditions = []

    if filters:
        if "status" in filters:
            conditions.append("status = ?")
            params.append(filters["status"])
        if "ticker" in filters:
            conditions.append("ticker = ?")
            params.append(filters["ticker"])
        if "setup" in filters:
            conditions.append("setup = ?")
            params.append(filters["setup"])
        if "from_date" in filters:
            conditions.append("screen_date >= ?")
            params.append(filters["from_date"])
        if "to_date" in filters:
            conditions.append("screen_date <= ?")
            params.append(filters["to_date"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY screen_date DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def update_prediction_status(prediction_id, status):
    conn = _get_conn()
    conn.execute(
        "UPDATE predictions SET status = ? WHERE id = ?",
        (status, prediction_id)
    )
    conn.commit()


def log_trade_result(data):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO trade_results (
            prediction_id, ticker, entry_date, entry_price,
            exit_date, exit_price, exit_reason,
            return_pct, return_abs, days_held,
            hit_tp1, hit_tp2, hit_tp3, hit_sl,
            max_favorable, max_adverse, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["prediction_id"], data["ticker"],
        data.get("entry_date"), data.get("entry_price"),
        data.get("exit_date"), data.get("exit_price"),
        data.get("exit_reason"),
        data.get("return_pct"), data.get("return_abs"),
        data.get("days_held"),
        1 if data.get("hit_tp1") else 0,
        1 if data.get("hit_tp2") else 0,
        1 if data.get("hit_tp3") else 0,
        1 if data.get("hit_sl") else 0,
        data.get("max_favorable"), data.get("max_adverse"),
        data.get("status", "CLOSED"),
    ))
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def get_trade_results(filters=None):
    conn = _get_conn()
    query = """
        SELECT tr.*, p.setup, p.signal, p.timing, p.score,
               p.market_regime, p.stock_regime, p.adx, p.atr
        FROM trade_results tr
        JOIN predictions p ON tr.prediction_id = p.id
    """
    params = []
    conditions = []

    if filters:
        if "status" in filters:
            conditions.append("tr.status = ?")
            params.append(filters["status"])
        if "ticker" in filters:
            conditions.append("tr.ticker = ?")
            params.append(filters["ticker"])
        if "exit_reason" in filters:
            conditions.append("tr.exit_reason = ?")
            params.append(filters["exit_reason"])
        if "setup" in filters:
            conditions.append("p.setup = ?")
            params.append(filters["setup"])
        if "from_date" in filters:
            conditions.append("tr.entry_date >= ?")
            params.append(filters["from_date"])
        if "to_date" in filters:
            conditions.append("tr.entry_date <= ?")
            params.append(filters["to_date"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY tr.entry_date DESC"
    rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


def log_portfolio_snapshot(data):
    conn = _get_conn()
    conn.execute("""
        INSERT INTO portfolio_snapshots (
            snapshot_date, cash, positions_value, total_value,
            num_positions, ihsg_value
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        data["snapshot_date"], data["cash"],
        data["positions_value"], data["total_value"],
        data.get("num_positions", 0), data.get("ihsg_value"),
    ))
    conn.commit()


def get_portfolio_snapshots():
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM portfolio_snapshots ORDER BY snapshot_date"
    ).fetchall()
    return [dict(r) for r in rows]


def get_journal_summary():
    conn = _get_conn()
    row = conn.execute("""
        SELECT
            COUNT(*) as total_predictions,
            COALESCE(SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END), 0) as pending,
            COALESCE(SUM(CASE WHEN status='ACTIVE' THEN 1 ELSE 0 END), 0) as active,
            COALESCE(SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END), 0) as closed
        FROM predictions
    """).fetchone()

    trades = conn.execute("""
        SELECT
            COUNT(*) as total_trades,
            COALESCE(SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END), 0) as open_trades,
            COALESCE(SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END), 0) as closed_trades
        FROM trade_results
    """).fetchone()

    return {
        "total_predictions": row["total_predictions"],
        "pending": row["pending"],
        "active": row["active"],
        "closed": row["closed"],
        "total_trades": trades["total_trades"],
        "open_trades": trades["open_trades"],
        "closed_trades": trades["closed_trades"],
    }


def close_db():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


atexit.register(close_db)
