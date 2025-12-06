import pandas as pd
from datetime import datetime, timedelta


# functions for calculating technical indicators


def calculate_macd(df, fast=12, slow=26, signal=9):
    """
    Adds MACD, Signal and Histogram columns to df based on Close prices.
    Works for any interval (1d, 1h, etc.); periods are in bars.
    """
    df = df.copy()
    df.sort_index(inplace=True)

    close = df["Close"]

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()

    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    df["MACD"] = macd_line
    df["MACD_signal"] = signal_line
    df["MACD_hist"] = histogram

    return df


def calculateRsi(td, days=14):
    """
    Calculate a 14-day RSI using Wilder smoothing on daily closes.
    If intraday data is provided, it is resampled to daily first and
    the daily RSI is forward-filled back to the intraday index.
    """
    if td.empty:
        return td
    if not isinstance(td.index, pd.DatetimeIndex):
        raise ValueError("RSI calculation needs a DatetimeIndex")

    td = td.copy()
    td.sort_index(inplace=True)

    # Roll up to daily closes to mirror Yahoo's RSI basis.
    daily_closes = td["Close"].resample("1D").last().dropna()
    if daily_closes.empty:
        return td

    delta = daily_closes.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    alpha = 1 / days  # Wilder smoothing
    avg_gain = gain.ewm(alpha=alpha, adjust=False, min_periods=days).mean()
    avg_loss = loss.ewm(alpha=alpha, adjust=False, min_periods=days).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)

    daily_rsi = 100 - (100 / (1 + rs))

    # Align daily RSI back to the original intraday index; forward-fill within each day.
    norm_index = td.index.normalize()
    rsi_per_bar = daily_rsi.reindex(norm_index, method="ffill")
    td["RSI14"] = rsi_per_bar.to_numpy()

    return td


def validate_month_coverage(td, start_str, end_str):
    """
    Ensures that every calendar month between start (inclusive)
    and (end - 1 day) is present in the data.
    If any month is missing, raise an error.
    """
    if td.empty:
        raise ValueError("No price data returned at all.")

    start = datetime.strptime(start_str, "%Y-%m-%d")
    # yfinance end is exclusive -> last actual date is end - 1 day
    end = datetime.strptime(end_str, "%Y-%m-%d") - timedelta(days=1)

    # All expected calendar months between start and (end - 1 day)
    expected_months = set()
    y, m = start.year, start.month
    while (y < end.year) or (y == end.year and m <= end.month):
        expected_months.add((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    # Actual months in returned price data
    actual_months = {(ts.year, ts.month) for ts in td.index}

    # Find missing months
    missing = expected_months - actual_months
    if missing:
        raise ValueError(f"Missing price data for months: {sorted(missing)}")
