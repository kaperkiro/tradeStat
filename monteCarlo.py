import numpy as np
import pandas as pd
import yfinance as yf


def load_prices_and_log_ret(ticker: str, start="2000-01-01"):
    df = yf.download(ticker, start, interval="1d", auto_adjust=False, progress=False)
    close = (
        df["Adj Close"].dropna() if "Adj Close" in df.columns else df["Close"].dropna()
    )
    log_ret = np.log(close / close.shift(1)).dropna()
    return df, log_ret
