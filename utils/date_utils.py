import pandas as pd


def normalize_screen_date(x):
    """Normalize any screen_date value to pd.Timestamp.

    Returns pd.Timestamp for valid inputs, pd.NaT for invalid/None.
    """
    if x is None:
        return pd.NaT
    if isinstance(x, pd.Timestamp):
        return x
    if isinstance(x, pd.NaT.__class__):
        return pd.NaT
    try:
        ts = pd.Timestamp(x)
        if ts is pd.NaT:
            return pd.NaT
        return ts
    except Exception:
        return pd.NaT


def safe_screen_date_str(x, fmt="%Y-%m-%d"):
    """Convert screen_date to formatted string safely for UI display."""
    ts = normalize_screen_date(x)
    if pd.isna(ts):
        return "N/A"
    return ts.strftime(fmt)
