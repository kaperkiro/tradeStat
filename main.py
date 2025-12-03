from datetime import datetime, timedelta
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf


class TradeInstance:
    def __init__(self, start, end, interval, startCapital, monthlyInvesting, index):
        self.start = start
        self.end = end
        self.interval = interval
        self.startCapital = startCapital
        self.monthlyInvesting = monthlyInvesting
        self.index = index
        self.endValueTrade = 0
        self.endValueHold = 0
        self.shares_hold = None
        self.priceDataTrade = []
        self.priceDataHold = []
        self.priceSeries = []
        self.buyData = []
        self.sellData = []

    def buyShares(
        self,
        value,
        tickerValue,
    ) -> float:
        return value / tickerValue

    def reset(self):
        self.endValueTrade = 0
        self.endValueHold = 0
        self.shares_hold = None
        self.priceDataTrade.clear()
        self.priceDataHold.clear()
        self.priceSeries.clear()
        self.buyData.clear()
        self.sellData.clear()


def main(TI: TradeInstance):
    cash = TI.startCapital
    shares = 0.0
    currently_holding = False
    td = getHistoData(
        TI.start,
        TI.end,
        TI.index,
        TI.interval,
    )
    validate_month_coverage(td, TI.start, TI.end)
    td = calculateRsi(td)
    if "RSI14" not in td.columns:
        raise ValueError("RSI14 could not be calculated for the provided data.")

    # calculate vale for just holding the stock for that time:
    shares_hold = TI.buyShares(TI.startCapital, td.iloc[0]["Close"])
    TI.shares_hold = shares_hold

    # Initialize strategy to be fully invested at the first bar so it matches buy & hold
    first_ts = td.index.min()  # earliest timestamp
    current_month = first_ts.month
    first_price = td.iloc[0]["Close"]
    shares = TI.buyShares(cash, first_price)
    cash = 0
    currently_holding = True
    TI.buyData.append((first_ts, first_price))

    for ts, hour in td.iterrows():
        price = hour["Close"]
        date = ts.date()
        rsi = hour.get("RSI14")

        # Add monthly contribution once per month (at the first bar of a new month).
        if ts.month != current_month:
            # for the holding strat:
            monthShares = TI.buyShares(TI.monthlyInvesting, price)
            shares_hold += monthShares
            if currently_holding:
                shares += TI.buyShares(TI.monthlyInvesting, price)
            else:
                cash += TI.monthlyInvesting
            current_month = ts.month

        if pd.notna(rsi) and rsi < 45 and not currently_holding:
            currently_holding = True
            equity = cash + shares * price
            shares = TI.buyShares(equity, price)
            cash = 0
            # print(f"bough shares: {shares} at date: {date}, at price: {price}")
            TI.buyData.append((ts, price))
        elif pd.notna(rsi) and rsi > 80 and currently_holding:
            cash = shares * price
            shares = 0
            # print(f"sold shares, at date: {date}, at price: {price}")
            currently_holding = False
            TI.sellData.append((ts, price))

        equity = cash + shares * price
        TI.priceSeries.append((ts, price))
        TI.priceDataTrade.append((ts, equity))
        TI.priceDataHold.append((ts, price * shares_hold))
        TI.endValueHold = price * shares_hold
        TI.endValueTrade = equity

    return


def calculateStartTimeRSI(startDate):
    return datetime(startDate)


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


def graphPriceStock(td, graphIndicators=False):
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


def graphPrice(TI: TradeInstance):
    if not TI.priceDataTrade or not TI.priceDataHold or not TI.priceSeries:
        raise ValueError("No price data available to plot. Run the strategy first.")

    trade_df = pd.DataFrame(TI.priceDataTrade, columns=["Date", "TradeValue"])
    hold_df = pd.DataFrame(TI.priceDataHold, columns=["Date", "HoldValue"])
    price_df = pd.DataFrame(TI.priceSeries, columns=["Date", "Price"])
    buy_df = (
        pd.DataFrame(TI.buyData, columns=["Date", "Price"])
        if TI.buyData
        else pd.DataFrame(columns=["Date", "Price"])
    )
    sell_df = (
        pd.DataFrame(TI.sellData, columns=["Date", "Price"])
        if TI.sellData
        else pd.DataFrame(columns=["Date", "Price"])
    )
    price_series = price_df["Price"]

    y_min = min(trade_df["TradeValue"].min(), hold_df["HoldValue"].min())
    y_max = max(trade_df["TradeValue"].max(), hold_df["HoldValue"].max())
    padding = (y_max - y_min) * 0.05 if y_max != y_min else max(abs(y_max), 1) * 0.05
    y_min -= padding
    y_max += padding

    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, sharex=True, figsize=(12, 10))

    ax1.plot(trade_df["Date"], trade_df["TradeValue"], label="Trading Strategy")
    ax1.set_ylabel("Portfolio Value")
    ax1.grid(True)
    ax1.legend()

    ax2.plot(hold_df["Date"], hold_df["HoldValue"], color="orange", label="Buy & Hold")
    ax2.set_ylabel("Portfolio Value")
    ax2.grid(True)
    ax2.legend()
    ax1.set_ylim(y_min, y_max)
    ax2.set_ylim(y_min, y_max)

    ax3.plot(hold_df["Date"], price_series, color="gray", label="Underlying Price")
    if not buy_df.empty:
        ax3.scatter(
            buy_df["Date"],
            buy_df["Price"],
            color="green",
            marker="^",
            s=60,
            label="Buy",
        )
    if not sell_df.empty:
        ax3.scatter(
            sell_df["Date"],
            sell_df["Price"],
            color="red",
            marker="v",
            s=60,
            label="Sell",
        )
    ax3.set_xlabel("Date")
    ax3.set_ylabel("Stock Price")
    ax3.grid(True)
    ax3.legend()

    fig.suptitle("Trading Strategy vs Buy & Hold")
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show()


def count_months(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def average(values):
    if not values:
        raise ValueError("empty list")
    return sum(values) / len(values)


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


if __name__ == "__main__":
    percent_trade = []
    percent_hold = []

    index_tickers = [
        # US Indexes
        "^GSPC",  # S&P 500
        "^DJI",  # Dow Jones Industrial Average
        "^IXIC",  # Nasdaq Composite
        "^RUT",  # Russell 2000
        # Other Global Indexes
        "^GDAXI",  # DAX (Germany)
        "^FTSE",  # FTSE 100 (UK)
        "^FCHI",  # CAC 40 (France)
        "^N225",  # Nikkei 225 (Japan)
        "^HSI",  # Hang Seng Index (Hong Kong)
    ]
    for ticker in index_tickers:
        print(ticker)
        startCapital = 10000
        monthlyInvesting = 100
        startDate = "2010-01-01"
        endDate = "2025-06-01"
        interval = "1D"
        tradeInstance = TradeInstance(
            startDate, endDate, interval, startCapital, monthlyInvesting, ticker
        )
        main(tradeInstance)
        n_months = count_months(startDate, endDate)
        total_contrib = startCapital + n_months * monthlyInvesting
        percent_trade.append(
            round(((tradeInstance.endValueTrade / total_contrib) * 100), 2)
        )
        percent_hold.append(
            round(((tradeInstance.endValueHold / total_contrib) * 100), 2)
        )
        tradeInstance.reset()

    print(
        f"Average gain for trading strategy: {average(percent_trade)} \nAverage capital gain for holding: {average(percent_hold)}"
    )


"""
tradeInsance = TradeInstance("2000-01-01", "2025-12-01", "1D", 10000, 0, "^IXIC")
    main(tradeInsance)
    graphPrice(tradeInsance)
    print(
        f"Your end capital with tradingstrategy is: {tradeInsance.endValueTrade}, capital gain: {round(((tradeInsance.endValueTrade/10000) * 100), 2)}% \nYour end capital with just holding is: {tradeInsance.endValueHold}, capital gain: {round(((tradeInsance.endValueHold/10000) * 100), 2)}%"
    )
"""
