from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf


def main(start, end, interval, startCapital, index):
    daysInPos = 0
    lastDate = None
    tradeValue = startCapital
    holdValue = startCapital
    shares = 0
    currently_holding = False
    td = getHistoData(start, end, index, interval)
    td = calculateRsi(td)
    if "RSI14" not in td.columns:
        raise ValueError("RSI14 could not be calculated for the provided data.")

    for i in range(len(td)):
        hour = td.iloc[i]
        price = hour["Close"]
        ts = hour.name  # index timestamp carried by the Series
        date = ts.date()
        rsi = hour.get("RSI14")

        if currently_holding:
            tradeValue = shares * price
        # print(rsi)
        if pd.notna(rsi) and rsi < 30 and not currently_holding:
            currently_holding = True
            shares = buyShares(tradeValue, price)
            print(f"bough shares: {shares} at date: {date}, at price: {price}")
        elif pd.notna(rsi) and rsi > 70 and currently_holding:
            print(f"sold shares, at date: {date}, at price: {price}")
            currently_holding = False

    # calculate vale for just holding the stock for that time:
    shares_hold = buyShares(holdValue, td.iloc[0]["Close"])
    holdValue = shares_hold * td.iloc[len(td) - 1]["Close"]

    return (tradeValue, holdValue)


def buyShares(
    value,
    tickerValue,
) -> float:
    return value / tickerValue


def calculateStartTimeRSI(startDate):
    datetime(startDate)


def getHistoData(startDate, endDate, ticker, interval):
    ticker = yf.Ticker(ticker)
    data = ticker.history(start=startDate, end=endDate, interval=interval)
    return data


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


def graphPrice(td, graphIndicators=False):
    fig, ax1 = plt.subplots()
    # --- First line (price) ---
    ax1.plot(td.index, td["Close"], label="Close Price")
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Price")

    if graphIndicators:
        # --- Second line (RSI 0-100) ---
        ax2 = ax1.twinx()  # creates a second y-axis sharing the same x-axis
        ax2.plot(td.index, td["RSI14"], color="orange", label="RSI14")
        ax2.set_ylabel("RSI (0-100)")
        ax2.set_ylim(0, 100)  # force RSI scale

        plt.title("Price + RSI")

    plt.title("Price")
    plt.grid(True)
    plt.show()


if __name__ == "__main__":
    tradeValue, holdValue = main("2015-01-01", "2025-12-01", "1D", 10000, "^IXIC")
    print(
        f"Your end capital with tradingstrategy is: {tradeValue}, capital gain: {round(((tradeValue/10000) * 100), 2)}% \nYour end capital with just holding is: {holdValue}, capital gain: {round(((holdValue/10000) * 100), 2)}%"
    )
