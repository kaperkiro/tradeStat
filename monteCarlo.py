import numpy as np  # numerical routines
import pandas as pd  # data frames and time series
import yfinance as yf  # price downloader


def load_prices_and_log_ret(ticker: str, start="2000-01-01"):
    """Download OHLCV history and compute daily log returns."""
    df = yf.download(
        ticker, start, interval="1D", auto_adjust=False, progress=False
    )  # fetch history
    close = df["Close"]  # take the close column
    print(df)  # quick peek at the downloaded frame
    # yfinance may return a single-column DataFrame when columns are multi-indexed.
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]  # squeeze to Series
    close = close.dropna()  # remove missing closes
    log_ret = np.log(close / close.shift(1)).dropna()  # daily log returns
    return close, log_ret  # return price series and returns


def label_vol_regimes(log_ret, vol_window, n_regimes):
    """Bucket rolling volatility into quantile-based regimes."""
    roll_vol = log_ret.rolling(vol_window).std()  # rolling std dev as volatility

    valid = roll_vol.dropna()  # drop warm-up NaNs
    aligned_ret = log_ret.loc[valid.index]  # align returns to same dates

    # pdcut split volatility into equal buckets, in our case 3,
    # 0(low volatility), 1(medium vol) and 2(high vol)
    regime = pd.qcut(valid, q=n_regimes, labels=False)  # quantile-based labels
    out = pd.DataFrame(
        {"r": aligned_ret, "vol": valid, "regime": regime.astype(int)}
    )  # combined frame
    return out  # returns + vol + regime label


def estimate_transition_matrix(regimes: pd.Series, n_regimes: int):
    """Build a Markov transition matrix from observed regime changes."""
    counts = np.zeros((n_regimes, n_regimes), dtype=float)  # raw counts matrix
    r = regimes.to_numpy()  # numpy array for speed

    for t in range(1, len(r)):
        counts[r[t - 1], r[t]] += 1  # count transitions i->j

    row_sums = counts.sum(axis=1, keepdims=True)  # outgoing totals
    P = np.divide(
        counts, row_sums, out=np.zeros_like(counts), where=row_sums > 0
    )  # normalize to probabilities

    # if no regimes found, fallback to 1
    for i in range(n_regimes):
        if P[i].sum() == 0:  # guard for empty rows
            P[i, i] = 1.0  # stay in place
    return P  # transition matrix


def build_regime_return_pools(df_reg: pd.DataFrame, n_regimes: int):
    """Collect historical returns for each regime into separate pools."""
    pools = {}  # dict regime -> array of returns
    for k in range(n_regimes):
        pools[k] = df_reg[df_reg["regime"] == k]["r"].to_numpy()  # slice each regime
    return pools  # sampled later


def simulate_regime_path(P: np.ndarray, n_steps: int, start_regime: int, seed=0):
    """Simulate a regime path using the transition matrix."""
    rng = np.random.default_rng(seed)  # deterministic RNG
    n_regimes = P.shape[0]  # number of regimes

    path = np.empty(n_steps, dtype=int)  # output array
    s = start_regime  # start state

    for t in range(n_steps):
        path[t] = s  # record current regime
        s = rng.choice(n_regimes, p=P[s])  # move to next according to row probs

    return path  # sequence of regimes


def sample_returns_regime_blocks(
    regime_path: np.ndarray, pools: dict, block_size=40, seed=0
):
    """Bootstrap returns in blocks, respecting the simulated regime path."""
    rng = np.random.default_rng(seed)  # deterministic RNG
    n_steps = len(regime_path)  # total steps
    out = np.empty(n_steps, dtype=float)  # output return series

    t = 0  # current index
    while t < n_steps:
        reg = int(regime_path[t])  # regime for this block
        pool = pools[reg]  # historical returns for that regime

        start = rng.integers(0, len(pool) - block_size)  # random block start
        block = pool[start : start + block_size]  # take a contiguous block

        take = min(block_size, n_steps - t)  # don't overflow output
        out[t : t + take] = block[:take]  # copy block into output
        t += take  # advance

    return out  # bootstrapped returns


def returns_to_prices(log_returns: np.ndarray, S0: float):
    """Convert log returns back to a price path starting at S0."""
    return S0 * np.exp(np.cumsum(log_returns))  # cumulative product in log space


def close_to_ohlc(close: np.ndarray, start_date="2000-01-01"):
    """Expand close prices to synthetic OHLCV with business-day index."""
    idx = pd.bdate_range(start_date, periods=len(close))  # business-day dates
    s = pd.Series(close, index=idx)  # close series

    df = pd.DataFrame(index=idx)  # output frame
    df["Close"] = s  # close column
    df["Open"] = s.shift(1).fillna(s.iloc[0])  # open is prior close

    move = (df["Close"] - df["Open"]).abs()  # intraday move size
    cushion = 0.3 * move  # widen high/low a bit

    df["High"] = np.maximum(df["Open"], df["Close"]) + cushion  # synthetic high
    df["Low"] = np.minimum(df["Open"], df["Close"]) - cushion  # synthetic low
    df["Volume"] = 0  # placeholder volume
    return df[["Open", "High", "Low", "Close", "Volume"]]  # ordered columns


def simulate_regime_block_bootstrap_ohlc(
    ticker: str,
    years: int = 25,
    history_start: str = "2020-01-01",
    vol_window: int = 63,
    n_regimes: int = 3,
    block_size: int = 40,
    seed: int = 0,
    start_date: str = "2025-12-18",
):
    close_hist, log_ret = load_prices_and_log_ret(
        ticker, start=history_start
    )  # get history + log returns

    df_reg = label_vol_regimes(
        log_ret, vol_window=vol_window, n_regimes=n_regimes
    )  # tag regimes
    P = estimate_transition_matrix(
        df_reg["regime"], n_regimes=n_regimes
    )  # regime transition probabilities
    pools = build_regime_return_pools(
        df_reg, n_regimes=n_regimes
    )  # returns bucketed by regime

    n_steps = 252 * years  # number of trading days to simulate
    start_regime = int(df_reg["regime"].iloc[-1])  # start from last observed regime

    regime_path = simulate_regime_path(
        P,
        n_steps=n_steps,
        start_regime=start_regime,
        seed=seed,  # simulate regime sequence
    )

    sim_r = sample_returns_regime_blocks(
        regime_path,
        pools,
        block_size=block_size,
        seed=seed + 1,  # bootstrap returns respecting regimes
    )

    S0 = float(close_hist.iloc[-1])  # last historical close as starting price
    sim_close = returns_to_prices(sim_r, S0=S0)  # convert simulated returns to prices

    td = close_to_ohlc(sim_close, start_date=start_date)  # expand to OHLCV
    return td  # simulated price DataFrame


print(simulate_regime_block_bootstrap_ohlc("AMD"))  # run once when executed directly
