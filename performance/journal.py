import sqlite3
import os
import threading
import atexit
from pathlib import Path
from datetime import datetime

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "performance_journal.db"

DATABASE_URL = os.environ.get("DATABASE_URL", "")

IS_POSTGRES = bool(DATABASE_URL)

_local = threading.local()


def get_db_backend():
    return "PostgreSQL" if IS_POSTGRES else "SQLite"


def _get_conn():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            if IS_POSTGRES:
                conn.execute("SELECT 1")
            else:
                conn.execute("SELECT 1")
            return conn
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            _local.conn = None

    if IS_POSTGRES:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
    else:
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")

    _local.conn = conn
    return conn


def _ph():
    return "%s" if IS_POSTGRES else "?"


def _fetchone_id(cursor):
    if IS_POSTGRES:
        return cursor.fetchone()[0]
    else:
        return cursor.lastrowid


def init_db():
    conn = _get_conn()
    cur = conn.cursor()

    if IS_POSTGRES:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                ticker TEXT NOT NULL,
                setup TEXT NOT NULL,
                signal TEXT NOT NULL,
                price_at_signal DOUBLE PRECISION NOT NULL,
                stop_loss DOUBLE PRECISION NOT NULL,
                tp1 DOUBLE PRECISION,
                tp2 DOUBLE PRECISION,
                tp3 DOUBLE PRECISION,
                entry_zone_low DOUBLE PRECISION,
                entry_zone_high DOUBLE PRECISION,
                entry_strategy TEXT,
                timing TEXT,
                score DOUBLE PRECISION,
                prob_tp1 TEXT,
                prob_tp2 TEXT,
                prob_tp3 TEXT,
                prob_sl TEXT,
                avg_days_tp1 DOUBLE PRECISION,
                avg_days_tp2 DOUBLE PRECISION,
                avg_days_tp3 DOUBLE PRECISION,
                market_regime TEXT,
                stock_regime TEXT,
                adx DOUBLE PRECISION,
                atr DOUBLE PRECISION,
                screen_date TIMESTAMP NOT NULL,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS trade_results (
                id SERIAL PRIMARY KEY,
                prediction_id INTEGER REFERENCES predictions(id),
                ticker TEXT NOT NULL,
                entry_date TIMESTAMP,
                entry_price DOUBLE PRECISION,
                exit_date TIMESTAMP,
                exit_price DOUBLE PRECISION,
                exit_reason TEXT,
                return_pct DOUBLE PRECISION,
                return_abs DOUBLE PRECISION,
                days_held INTEGER,
                hit_tp1 INTEGER DEFAULT 0,
                hit_tp2 INTEGER DEFAULT 0,
                hit_tp3 INTEGER DEFAULT 0,
                hit_sl INTEGER DEFAULT 0,
                max_favorable DOUBLE PRECISION,
                max_adverse DOUBLE PRECISION,
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id SERIAL PRIMARY KEY,
                snapshot_date TIMESTAMP NOT NULL,
                cash DOUBLE PRECISION NOT NULL,
                positions_value DOUBLE PRECISION NOT NULL,
                total_value DOUBLE PRECISION NOT NULL,
                num_positions INTEGER,
                ihsg_value DOUBLE PRECISION,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    else:
        cur.executescript("""
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
        """)

    indexes = [
        ("idx_predictions_ticker", "predictions", "ticker"),
        ("idx_predictions_status", "predictions", "status"),
        ("idx_predictions_screen_date", "predictions", "screen_date"),
        ("idx_trade_results_prediction_id", "trade_results", "prediction_id"),
        ("idx_trade_results_ticker", "trade_results", "ticker"),
        ("idx_trade_results_status", "trade_results", "status"),
    ]
    for idx_name, table, col in indexes:
        cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table} ({col})")

    cur.execute("SELECT MAX(version) FROM schema_version")
    current_version = cur.fetchone()[0]
    if current_version is None:
        try:
            cur.execute("INSERT INTO schema_version (version) VALUES (1)")
        except Exception:
            conn.rollback()
    conn.commit()


def clear_backtest_data():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM trade_results")
    cur.execute("DELETE FROM predictions")
    conn.commit()


def log_prediction(data):
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"""
        INSERT INTO predictions (
            ticker, setup, signal, price_at_signal, stop_loss,
            tp1, tp2, tp3,
            entry_zone_low, entry_zone_high, entry_strategy,
            timing, score,
            prob_tp1, prob_tp2, prob_tp3, prob_sl,
            avg_days_tp1, avg_days_tp2, avg_days_tp3,
            market_regime, stock_regime, adx, atr,
            screen_date, status
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'PENDING')
        {"RETURNING id" if IS_POSTGRES else ""}
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
    if IS_POSTGRES:
        return cur.fetchone()[0]
    return cur.lastrowid


def log_predictions_batch(predictions):
    if not predictions:
        return []

    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    ids = []

    for data in predictions:
        cur.execute(f"""
            INSERT INTO predictions (
                ticker, setup, signal, price_at_signal, stop_loss,
                tp1, tp2, tp3,
                entry_zone_low, entry_zone_high, entry_strategy,
                timing, score,
                prob_tp1, prob_tp2, prob_tp3, prob_sl,
                avg_days_tp1, avg_days_tp2, avg_days_tp3,
                market_regime, stock_regime, adx, atr,
                screen_date, status
            ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'PENDING')
            {"RETURNING id" if IS_POSTGRES else ""}
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
        if IS_POSTGRES:
            ids.append(cur.fetchone()[0])
        else:
            ids.append(cur.lastrowid)

    conn.commit()
    return ids


def get_pending_predictions():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM predictions WHERE status = 'PENDING' ORDER BY screen_date"
    )
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def get_active_predictions():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM predictions WHERE status = 'ACTIVE' ORDER BY screen_date"
    )
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def get_all_predictions(filters=None):
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    query = "SELECT * FROM predictions"
    params = []
    conditions = []

    if filters:
        if "status" in filters:
            conditions.append(f"status = {ph}")
            params.append(filters["status"])
        if "ticker" in filters:
            conditions.append(f"ticker = {ph}")
            params.append(filters["ticker"])
        if "setup" in filters:
            conditions.append(f"setup = {ph}")
            params.append(filters["setup"])
        if "from_date" in filters:
            conditions.append(f"screen_date >= {ph}")
            params.append(filters["from_date"])
        if "to_date" in filters:
            conditions.append(f"screen_date <= {ph}")
            params.append(filters["to_date"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY screen_date DESC"
    cur.execute(query, params)
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def update_prediction_status(prediction_id, status):
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(
        f"UPDATE predictions SET status = {ph} WHERE id = {ph}",
        (status, prediction_id)
    )
    conn.commit()


def log_trade_result(data):
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"""
        INSERT INTO trade_results (
            prediction_id, ticker, entry_date, entry_price,
            exit_date, exit_price, exit_reason,
            return_pct, return_abs, days_held,
            hit_tp1, hit_tp2, hit_tp3, hit_sl,
            max_favorable, max_adverse, status
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        {"RETURNING id" if IS_POSTGRES else ""}
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
    if IS_POSTGRES:
        return cur.fetchone()[0]
    return cur.lastrowid


def get_trade_results(filters=None):
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
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
            conditions.append(f"tr.status = {ph}")
            params.append(filters["status"])
        if "ticker" in filters:
            conditions.append(f"tr.ticker = {ph}")
            params.append(filters["ticker"])
        if "exit_reason" in filters:
            conditions.append(f"tr.exit_reason = {ph}")
            params.append(filters["exit_reason"])
        if "setup" in filters:
            conditions.append(f"p.setup = {ph}")
            params.append(filters["setup"])
        if "from_date" in filters:
            conditions.append(f"tr.entry_date >= {ph}")
            params.append(filters["from_date"])
        if "to_date" in filters:
            conditions.append(f"tr.entry_date <= {ph}")
            params.append(filters["to_date"])

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY tr.entry_date DESC"
    cur.execute(query, params)
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def log_portfolio_snapshot(data):
    conn = _get_conn()
    cur = conn.cursor()
    ph = _ph()
    cur.execute(f"""
        INSERT INTO portfolio_snapshots (
            snapshot_date, cash, positions_value, total_value,
            num_positions, ihsg_value
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
    """, (
        data["snapshot_date"], data["cash"],
        data["positions_value"], data["total_value"],
        data.get("num_positions", 0), data.get("ihsg_value"),
    ))
    conn.commit()


def get_portfolio_snapshots():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM portfolio_snapshots ORDER BY snapshot_date")
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    return [dict(r) for r in cur.fetchall()]


def get_journal_summary():
    conn = _get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) as total_predictions,
            COALESCE(SUM(CASE WHEN status='PENDING' THEN 1 ELSE 0 END), 0) as pending,
            COALESCE(SUM(CASE WHEN status='ACTIVE' THEN 1 ELSE 0 END), 0) as active,
            COALESCE(SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END), 0) as closed
        FROM predictions
    """)
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        row = dict(zip(cols, cur.fetchone()))
    else:
        row = dict(cur.fetchone())

    cur.execute("""
        SELECT
            COUNT(*) as total_trades,
            COALESCE(SUM(CASE WHEN status='OPEN' THEN 1 ELSE 0 END), 0) as open_trades,
            COALESCE(SUM(CASE WHEN status='CLOSED' THEN 1 ELSE 0 END), 0) as closed_trades
        FROM trade_results
    """)
    if IS_POSTGRES:
        cols = [desc[0] for desc in cur.description]
        trades = dict(zip(cols, cur.fetchone()))
    else:
        trades = dict(cur.fetchone())

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
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


atexit.register(close_db)
