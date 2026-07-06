import time
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import (
    CACHE_DIR, CACHE_MAX_AGE_HOURS, BATCH_SIZE,
    DOWNLOAD_PERIOD, DOWNLOAD_INTERVAL, JKSE_TICKER
)

logger = logging.getLogger(__name__)

logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)

CACHE_DIR.mkdir(exist_ok=True)


def cache_is_valid(cache_path, max_age_hours=CACHE_MAX_AGE_HOURS):
    if not cache_path.exists():
        return False
    modified_time = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
    age = datetime.now(tz=timezone.utc) - modified_time
    return age < timedelta(hours=max_age_hours)


def _get_cache_path(ticker, start=None, end=None, ext="parquet"):
    if start and end:
        key = f"{ticker}_{start}_{end}"
    else:
        key = ticker
    return CACHE_DIR / f"{key}.{ext}"


def _migrate_pickle_to_parquet(pkl_path):
    if pkl_path.exists():
        try:
            df = pd.read_pickle(pkl_path)
            parquet_path = pkl_path.with_suffix(".parquet")
            df.to_parquet(parquet_path)
            pkl_path.unlink()
        except Exception as e:
            logger.debug(f"Could not migrate {pkl_path.name}: {e}")


def save_ticker_cache(ticker, df, start=None, end=None):
    parquet_path = _get_cache_path(ticker, start, end, "parquet")
    pkl_path = _get_cache_path(ticker, start, end, "pkl")
    _migrate_pickle_to_parquet(pkl_path)

    try:
        df.to_parquet(parquet_path)
    except Exception:
        df.to_pickle(pkl_path, protocol=4)


def load_ticker_cache(ticker, start=None, end=None):
    parquet_path = _get_cache_path(ticker, start, end, "parquet")
    pkl_path = _get_cache_path(ticker, start, end, "pkl")

    _migrate_pickle_to_parquet(pkl_path)

    if cache_is_valid(parquet_path, CACHE_MAX_AGE_HOURS):
        try:
            return pd.read_parquet(parquet_path)
        except Exception:
            return None

    if cache_is_valid(pkl_path, CACHE_MAX_AGE_HOURS):
        try:
            return pd.read_pickle(pkl_path)
        except Exception:
            return None

    if start and end:
        cached_df = _find_matching_cache(ticker, start, end)
        if cached_df is not None:
            return cached_df

    return None


def load_ticker_cache_incremental(ticker, start=None, end=None):
    """Cache valid → use directly. Cache expired → append new data."""
    cached_df = load_ticker_cache(ticker, start, end)
    if cached_df is not None:
        return cached_df

    parquet_path = _get_cache_path(ticker, start, end, "parquet")
    old_df = None
    if parquet_path.exists():
        try:
            old_df = pd.read_parquet(parquet_path)
        except Exception:
            pass

    if old_df is not None and len(old_df) >= 50:
        last_date = old_df.index.max()
        new_start = (last_date + timedelta(days=1)).strftime("%Y-%m-%d")
        new_end = datetime.now().strftime("%Y-%m-%d")

        if new_start <= new_end:
            new_df = download_single_ticker(ticker, start=new_start, end=new_end)
            if new_df is not None and len(new_df) > 0:
                merged = pd.concat([old_df, new_df])
                merged = merged[~merged.index.duplicated(keep='last')]
                merged = merged.sort_index()
                save_ticker_cache(ticker, merged, start, end)
                return merged

        return old_df

    return download_single_ticker(ticker, start, end)


def _find_matching_cache(ticker, start, end):
    try:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end)
    except Exception:
        return None

    base_name = f"{ticker}_"
    best_df = None
    best_coverage = 0
    tolerance = pd.Timedelta(days=7)

    for f in CACHE_DIR.glob(f"{base_name}*.parquet"):
        if f.name.startswith(ticker) and f.name != f"{ticker}.parquet":
            try:
                df = pd.read_parquet(f)
                if len(df) < 50:
                    continue
                cache_start = df.index.min()
                cache_end = df.index.max()
                if cache_start <= start_ts + pd.Timedelta(days=365) and cache_end >= end_ts - pd.Timedelta(days=90):
                    coverage = len(df)
                    if coverage > best_coverage:
                        best_coverage = coverage
                        best_df = df
            except Exception:
                continue
    return best_df


def normalize_yfinance_df(df, ticker=None):
    if df is None:
        if ticker:
            print(f"    [{ticker}] Skipped: no data returned")
        return None
    if not isinstance(df, pd.DataFrame):
        if ticker:
            print(f"    [{ticker}] Skipped: invalid data type")
        return None
    if df.empty:
        if ticker:
            print(f"    [{ticker}] Skipped: empty DataFrame")
        return None

    if isinstance(df.columns, pd.MultiIndex):
        level_0 = df.columns.get_level_values(0)
        level_1 = df.columns.get_level_values(1)
        if "Close" in level_0:
            df.columns = level_0
        elif "Close" in level_1:
            df.columns = level_1
        else:
            if ticker:
                print(f"    [{ticker}] Skipped: no Close column in MultiIndex")
            return None

    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    if not all(col in df.columns for col in required_cols):
        if ticker:
            print(f"    [{ticker}] Skipped: missing OHLCV columns")
        return None

    keep_cols = required_cols.copy()
    if "Adj Close" in df.columns:
        keep_cols.append("Adj Close")

    df = df[keep_cols].copy()
    df = df.dropna(how="all")

    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    if len(df) < 50:
        if ticker:
            print(f"    [{ticker}] Skipped: only {len(df)} rows (< 50)")
        return None

    return df


def download_single_ticker(ticker, start=None, end=None):
    try:
        dl_kwargs = {
            "interval": DOWNLOAD_INTERVAL,
            "auto_adjust": False,
            "progress": False,
            "threads": False,
            "timeout": 60,
        }
        if start and end:
            dl_kwargs["start"] = start
            dl_kwargs["end"] = end
        else:
            dl_kwargs["period"] = DOWNLOAD_PERIOD

        df = yf.download(ticker, **dl_kwargs)
        df = normalize_yfinance_df(df, ticker)
        if df is not None:
            save_ticker_cache(ticker, df, start, end)
            return df
        return None
    except Exception as e:
        logger.debug(f"Download failed for {ticker}: {e}")
        return None


def download_tickers_batch(tickers, start=None, end=None):
    print(f"  Downloading batch: {len(tickers)} tickers")
    downloaded_data = {}
    failed_tickers = []

    try:
        dl_kwargs = {
            "tickers": tickers,
            "interval": DOWNLOAD_INTERVAL,
            "auto_adjust": False,
            "progress": False,
            "threads": True,
            "group_by": "ticker",
        }
        if start and end:
            dl_kwargs["start"] = start
            dl_kwargs["end"] = end
        else:
            dl_kwargs["period"] = DOWNLOAD_PERIOD

        batch_df = yf.download(**dl_kwargs)

        if batch_df is None or batch_df.empty:
            failed_tickers = tickers
        else:
            for ticker in tickers:
                try:
                    df = None
                    if isinstance(batch_df.columns, pd.MultiIndex):
                        level_0 = batch_df.columns.get_level_values(0)
                        level_1 = batch_df.columns.get_level_values(1)
                        if ticker in level_0:
                            df = batch_df[ticker].copy()
                        elif ticker in level_1:
                            df = batch_df.xs(ticker, axis=1, level=1).copy()
                        else:
                            failed_tickers.append(ticker)
                            continue
                    else:
                        if len(tickers) == 1:
                            df = batch_df.copy()
                        else:
                            failed_tickers.append(ticker)
                            continue

                    df = normalize_yfinance_df(df, ticker)
                    if df is not None:
                        save_ticker_cache(ticker, df, start, end)
                        downloaded_data[ticker] = df
                    else:
                        failed_tickers.append(ticker)
                except Exception:
                    failed_tickers.append(ticker)
    except Exception:
        failed_tickers = tickers

    if failed_tickers:
        print(f"  Fallback single download: {len(failed_tickers)} tickers")
        still_failed = []
        for ticker in failed_tickers:
            df = download_single_ticker(ticker, start, end)
            if df is not None:
                downloaded_data[ticker] = df
                print(f"    [{ticker}] OK (fallback)")
            else:
                still_failed.append(ticker)
            time.sleep(0.2)
        if still_failed:
            print(f"  Failed ({len(still_failed)}): {still_failed}")

    return downloaded_data


def get_all_market_data(tickers, start=None, end=None):
    market_data = {}
    tickers_incremental = []
    tickers_full = []

    print("Checking cache...")
    for ticker in tickers:
        cached_df = load_ticker_cache(ticker, start, end)
        if cached_df is not None and len(cached_df) >= 50:
            market_data[ticker] = cached_df
        else:
            parquet_path = _get_cache_path(ticker, start, end, "parquet")
            if parquet_path.exists():
                tickers_incremental.append(ticker)
            else:
                tickers_full.append(ticker)

    print(f"  Cache hit: {len(market_data)}, Incremental: {len(tickers_incremental)}, Full download: {len(tickers_full)}")

    if tickers_incremental:
        print(f"  Incremental update: {len(tickers_incremental)} tickers...")
        for ticker in tickers_incremental:
            df = load_ticker_cache_incremental(ticker, start, end)
            if df is not None and len(df) >= 50:
                market_data[ticker] = df
            time.sleep(0.1)

    if tickers_full:
        print(f"  Full download: {len(tickers_full)} tickers...")
        for i in range(0, len(tickers_full), BATCH_SIZE):
            batch = tickers_full[i:i + BATCH_SIZE]
            downloaded = download_tickers_batch(batch, start, end)
            market_data.update(downloaded)
            time.sleep(1)

    return market_data


def get_jkse_data(force_download=False, start=None, end=None):
    parquet_path = _get_cache_path(JKSE_TICKER, start, end, "parquet")
    pkl_path = CACHE_DIR / "JKSE.pkl"

    _migrate_pickle_to_parquet(pkl_path)

    if not force_download:
        if cache_is_valid(parquet_path, CACHE_MAX_AGE_HOURS):
            try:
                df = pd.read_parquet(parquet_path)
                if df is not None and len(df) >= 50:
                    return df
            except Exception:
                pass
        if cache_is_valid(pkl_path, CACHE_MAX_AGE_HOURS):
            try:
                df = pd.read_pickle(pkl_path)
                if df is not None and len(df) >= 50:
                    return df
            except Exception:
                pass

        if start and end:
            cached_df = _find_matching_cache(JKSE_TICKER, start, end)
            if cached_df is not None:
                return cached_df

    try:
        dl_kwargs = {
            "interval": DOWNLOAD_INTERVAL,
            "auto_adjust": False,
            "progress": False,
            "threads": False,
        }
        if start and end:
            dl_kwargs["start"] = start
            dl_kwargs["end"] = end
        else:
            dl_kwargs["period"] = DOWNLOAD_PERIOD

        df = yf.download(JKSE_TICKER, **dl_kwargs)
        df = normalize_yfinance_df(df)
        if df is not None:
            try:
                df.to_parquet(parquet_path)
            except Exception:
                df.to_pickle(pkl_path, protocol=4)
        return df
    except Exception as e:
        logger.warning(f"Failed to download JKSE data: {e}")
        return None


def get_fundamental_data(tickers, cache_dir=None):
    """Fetch and cache fundamental data for all tickers using parallel requests."""
    if cache_dir is None:
        cache_dir = CACHE_DIR
    else:
        cache_dir = Path(cache_dir)
    cache_dir.mkdir(exist_ok=True)
    cache_path = cache_dir / "fundamental_data.parquet"

    if cache_path.exists():
        cache_age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if cache_age_hours < 168:
            try:
                df = pd.read_parquet(cache_path)
                if len(df) >= len(tickers) * 0.5:
                    print(f"  Fundamental cache hit: {len(df)} tickers")
                    return df
            except Exception:
                pass

    print(f"  Fetching fundamental data for {len(tickers)} tickers (parallel)...", flush=True)
    fundamental_data = {}
    failed = []

    def fetch_single(ticker):
        try:
            t = yf.Ticker(ticker)
            info = t.info
            return ticker, {
                'pe_ratio': info.get('trailingPE'),
                'forward_pe': info.get('forwardPE'),
                'pb_ratio': info.get('priceToBook'),
                'roe': info.get('returnOnEquity'),
                'revenue_growth': info.get('revenueGrowth'),
                'earnings_growth': info.get('earningsGrowth'),
                'dividend_yield': info.get('dividendYield'),
                'market_cap': info.get('marketCap'),
                'ps_ratio': info.get('priceToSalesTrailing12Months'),
                'book_value': info.get('bookValue'),
            }
        except Exception:
            return ticker, None

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single, t): t for t in tickers}
        completed = 0
        for future in as_completed(futures):
            completed += 1
            if completed % 100 == 0:
                print(f"    {completed}/{len(tickers)} fetched...", flush=True)
            ticker, data = future.result()
            if data is not None:
                fundamental_data[ticker] = data
            else:
                failed.append(ticker)

    df = pd.DataFrame(fundamental_data).T
    df.index.name = 'ticker'

    import numpy as np
    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df[col] = df[col].replace([np.inf, -np.inf], np.nan)
        if df[col].isna().sum() > 0:
            median_val = df[col].median()
            if pd.notna(median_val):
                df[col] = df[col].fillna(median_val)
            else:
                df[col] = df[col].fillna(0)

    df.to_parquet(cache_path)
    print(f"  Saved {len(df)} tickers fundamental data ({len(failed)} failed)")
    return df
