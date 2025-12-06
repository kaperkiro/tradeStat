import matplotlib.pyplot as plt
import pandas as pd
from main import TradeInstance


# functions for graphing of prices, trends etc


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
