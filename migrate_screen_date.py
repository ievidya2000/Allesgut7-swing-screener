"""Migration script: normalize all screen_date values to consistent pd.Timestamp.

Cleans:
1. SQLite performance_journal.db - predictions.screen_date
2. Parquet training_data.parquet - screen_date column
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime

DB_PATH = Path("performance_journal.db")
PARQUET_PATH = Path("screener_v2/rl/training_data.parquet")


def normalize_val(x):
    """Convert any screen_date value to ISO string for SQLite storage."""
    if x is None:
        return datetime.now().isoformat()
    if isinstance(x, pd.Timestamp):
        return x.isoformat()
    try:
        ts = pd.Timestamp(x)
        if pd.isna(ts):
            return datetime.now().isoformat()
        return ts.isoformat()
    except Exception:
        return datetime.now().isoformat()


def migrate_sqlite():
    if not DB_PATH.exists():
        print(f"  DB not found: {DB_PATH}, skipping")
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT id, screen_date FROM predictions").fetchall()
    print(f"  Found {len(rows)} predictions to check")

    fixed = 0
    for row in rows:
        raw = row["screen_date"]
        normalized = normalize_val(raw)
        if normalized != raw:
            conn.execute(
                "UPDATE predictions SET screen_date = ? WHERE id = ?",
                (normalized, row["id"])
            )
            fixed += 1

    conn.commit()

    rows2 = conn.execute("SELECT id, entry_date, exit_date FROM trade_results").fetchall()
    print(f"  Found {len(rows2)} trade_results to check")

    fixed2 = 0
    for row in rows2:
        for col in ["entry_date", "exit_date"]:
            raw = row[col]
            if raw is None:
                continue
            normalized = normalize_val(raw)
            if normalized != raw:
                conn.execute(
                    f"UPDATE trade_results SET {col} = ? WHERE id = ?",
                    (normalized, row["id"])
                )
                fixed2 += 1

    conn.commit()
    conn.close()
    print(f"  Fixed {fixed} predictions, {fixed2} trade_results dates")


def migrate_parquet():
    if not PARQUET_PATH.exists():
        print(f"  Parquet not found: {PARQUET_PATH}, skipping")
        return

    df = pd.read_parquet(PARQUET_PATH)
    print(f"  Loaded {len(df)} rows from parquet")

    if "screen_date" not in df.columns:
        print("  No screen_date column, skipping")
        return

    original_types = df["screen_date"].apply(type).value_counts()
    print(f"  Original types: {original_types.to_dict()}")

    df["screen_date"] = pd.to_datetime(df["screen_date"], errors="coerce")

    nat_count = df["screen_date"].isna().sum()
    if nat_count > 0:
        print(f"  WARNING: {nat_count} NaT values found, dropping rows")
        df = df.dropna(subset=["screen_date"]).reset_index(drop=True)

    backup_path = PARQUET_PATH.with_suffix(".parquet.bak")
    pd.read_parquet(PARQUET_PATH).to_parquet(backup_path, index=False)
    print(f"  Backup saved: {backup_path}")

    df.to_parquet(PARQUET_PATH, index=False)
    print(f"  Saved cleaned parquet: {len(df)} rows")


def validate():
    print("\n  === VALIDATION ===")

    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        rows = conn.execute("SELECT screen_date FROM predictions LIMIT 5").fetchall()
        print(f"  Sample DB screen_date values:")
        for r in rows:
            print(f"    {r[0]}")
        conn.close()

    if PARQUET_PATH.exists():
        df = pd.read_parquet(PARQUET_PATH)
        if "screen_date" in df.columns:
            print(f"  Parquet screen_date dtype: {df['screen_date'].dtype}")
            print(f"  Parquet screen_date range: {df['screen_date'].min()} → {df['screen_date'].max()}")
            print(f"  Parquet rows: {len(df)}")


if __name__ == "__main__":
    print("=" * 50)
    print("  screen_date Migration Script")
    print("=" * 50)

    print("\n[1/2] Migrating SQLite...")
    migrate_sqlite()

    print("\n[2/2] Migrating Parquet...")
    migrate_parquet()

    validate()

    print("\n" + "=" * 50)
    print("  Migration complete!")
    print("=" * 50)
