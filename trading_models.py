class StrategyBase:
    name = "UnnamedStrategy"

    def on_bar(self, cash, shares, ts, row):
        """
        Called on every candle/bar.

        Must return:
        - "BUY"
        - "SELL"
        - None   (hold)
        """
        raise NotImplementedError


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


class AITradingStrat:
    num = 3

    def __init__(self, SB: StrategyBase):
        self.SB = SB


class TradeInstance:
    def __init__(self, ticker, start, end, interval, startCapital, monthlyInvesting):
        # Store with both legacy and current attribute names to avoid breakage.
        self.start = start
        self.end = end
        self.startDate = start
        self.endDate = end
        self.ticker = ticker
        self.index = ticker  # legacy naming used in some older code paths
        self.interval = interval
        self.startCapital = startCapital
        self.monthlyInvesting = monthlyInvesting

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
