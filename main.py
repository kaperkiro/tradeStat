from datetime import datetime
import pandas as pd
import yfinance as yf
import indicators
import graphs
import macd_functions as mf


class RSITradeStrat:
    num = 1

    def __init__(self, lowerBound, upperBound):
        self.lowerBound = lowerBound
        self.upperBound = upperBound


class MACDTradeStrat:
    num = 2

    # macdStrat 1: Crossing of MACD and the signal line
    # macdStrat 2: Crossing the zero line
    # macdStrat 3: Overbought and oversold levels
    # macdStrat 4: Divergence in price and MACD

    def __init__(self, macdStrat):
        self.macdStrat = macdStrat


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


def main(TI: TradeInstance, tradingStrat):
    td = getHistoData(
        TI.start,
        TI.end,
        TI.index,
        TI.interval,
    )
    indicators.validate_month_coverage(td, TI.start, TI.end)

    buyAndHoldStrategy(TI, td)

    if tradingStrat.num == 1:
        td = indicators.calculateRsi(td)
        tradeRsiStrategy(TI, tradingStrat, td)
    elif tradingStrat.num == 2:
        td = indicators.calculate_macd(td)
        tradeMACDStrategy(TI, tradingStrat, td)

    return


def tradeMACDStrategy(TI, tradingStrat, td):
    cash = TI.startCapital
    shares = 0.0
    td = td.copy() if td is not None else None
    td = td.sort_index()

    first_ts = td.index.min()
    current_month = first_ts.month

    first_price = td.iloc[0]["Close"]
    shares = TI.buyShares(cash, first_price)
    cash = 0
    TI.buyData.append((first_ts, first_price))

    prev_macd = None
    prev_signal = None
    prev_hist = None

    print(f"running macd strategy{tradingStrat.macdStrat}")

    for ts, hour in td.iterrows():
        price = hour["Close"]
        macd = hour.get("MACD")
        signal = hour.get("MACD_signal")
        hist = hour.get("MACD_hist")

        # Add monthly contribution once per month (at the first bar of a new month).
        if ts.month != current_month and TI.monthlyInvesting != 0:
            cash += TI.monthlyInvesting
            current_month = ts.month

        if tradingStrat.macdStrat == 1:
            if mf.is_bullish_macd_cross(macd, signal, prev_macd, prev_signal):
                equity = cash + shares * price
                shares = TI.buyShares(equity, price)

                cash = 0
                TI.buyData.append((ts, price))
            elif mf.is_bearish_macd_cross(macd, signal, prev_macd, prev_signal):
                cash += shares * price
                shares = 0
                TI.sellData.append((ts, price))

        elif tradingStrat.macdStrat == 2:
            if mf.is_bullish_macd_zero_combo(macd, prev_macd, hist, prev_hist):
                equity = cash + shares * price
                shares = TI.buyShares(equity, price)

                cash = 0
                TI.buyData.append((ts, price))
            elif mf.is_bearish_macd_zero_combo(macd, prev_macd, hist, prev_hist):
                cash += shares * price
                shares = 0
                TI.sellData.append((ts, price))
        elif tradingStrat.macdStrat == 3:
            pass
        elif tradingStrat.macdStrat == 4:
            pass
        equity = cash + shares * price
        TI.priceDataTrade.append((ts, equity))
        TI.endValueTrade = equity

        # update prev indicators for next iteration
        prev_macd = macd
        prev_signal = signal
        prev_hist = hist

    return


def buyAndHoldStrategy(TI, td):
    """
    Buy and hold with monthly contributions. Populates priceSeries, priceDataHold, and endValueHold.
    """
    if td.empty:
        raise ValueError("No price data returned for buy & hold strategy.")

    td = td.sort_index()
    first_ts = td.index.min()
    current_month = first_ts.month
    first_price = td.iloc[0]["Close"]

    shares_hold = TI.buyShares(TI.startCapital, first_price)
    TI.shares_hold = shares_hold

    for ts, row in td.iterrows():
        price = row["Close"]
        if ts.month != current_month and TI.monthlyInvesting != 0:
            shares_hold += TI.buyShares(TI.monthlyInvesting, price)
            current_month = ts.month

        TI.priceSeries.append((ts, price))
        TI.priceDataHold.append((ts, price * shares_hold))
        TI.endValueHold = price * shares_hold


def tradeRsiStrategy(TI, tradingStrat, td=None):
    cash = TI.startCapital
    shares = 0.0
    td = td.copy() if td is not None else None
    td = td.sort_index()
    first_ts = td.index.min()
    current_month = first_ts.month
    first_price = td.iloc[0]["Close"]
    shares = TI.buyShares(cash, first_price)
    cash = 0
    TI.buyData.append((first_ts, first_price))

    # Only add priceSeries here if the hold strategy hasn't populated it yet.
    add_price_series = not TI.priceSeries

    for ts, hour in td.iterrows():
        price = hour["Close"]
        rsi = hour.get("RSI14")

        # Add monthly contribution once per month (at the first bar of a new month).
        if ts.month != current_month and TI.monthlyInvesting != 0:
            cash += TI.monthlyInvesting
            current_month = ts.month

        if pd.notna(rsi) and rsi < tradingStrat.lowerBound and cash > 0:
            equity = cash + shares * price
            shares = TI.buyShares(equity, price)
            cash = 0
            TI.buyData.append((ts, price))
        elif pd.notna(rsi) and rsi > tradingStrat.upperBound and shares > 0:
            cash += shares * price
            shares = 0
            TI.sellData.append((ts, price))

        equity = cash + shares * price
        if add_price_series:
            TI.priceSeries.append((ts, price))
        TI.priceDataTrade.append((ts, equity))
        TI.endValueTrade = equity
    return


def getHistoData(startDate, endDate, ticker, interval):
    """
    Fetch price history.
    """

    ticker_obj = yf.Ticker(ticker)
    return ticker_obj.history(start=startDate, end=endDate, interval=interval)


def count_months(start_str, end_str):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def average(values):
    if not values:
        raise ValueError("empty list")
    return sum(values) / len(values)


if __name__ == "__main__":
    percent_trade = []
    percent_hold = []

    index_tickers = [
        "^WIG20",
    ]

    for ticker in index_tickers:
        print(ticker)
        startCapital = 0
        monthlyInvesting = 100
        startDate = "2025-10-10"
        endDate = "2025-12-16"
        interval = "1h"
        tradeInstance = TradeInstance(
            startDate, endDate, interval, startCapital, monthlyInvesting, ticker
        )
        tradeStrat = RSITradeStrat(40, 80)
        main(tradeInstance, tradeStrat)
        n_months = count_months(startDate, endDate)
        total_contrib = startCapital + n_months * monthlyInvesting
        percent_trade.append(
            round(((tradeInstance.endValueTrade / total_contrib) * 100), 2)
        )
        percent_hold.append(
            round(((tradeInstance.endValueHold / total_contrib) * 100), 2)
        )
        graphs.graphPrice(tradeInstance)
        tradeInstance.reset()

    print(
        f"Average gain for trading strategy: {average(percent_trade)} \nAverage capital gain for holding: {average(percent_hold)}"
    )


TICKERS = [  # US Indexes
    "AMD",
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
