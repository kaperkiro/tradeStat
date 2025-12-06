def is_bullish_macd_cross(macd, signal, prev_macd, prev_signal):
    """
    Returns True if the current bar produces a fresh bullish MACD crossover.

    Conditions:
    - Previous bar: MACD <= Signal
    - Current bar:  MACD > Signal
    """
    if prev_macd is None or prev_signal is None:
        return False  # cannot detect crossover on first bar

    return prev_macd <= prev_signal and macd > signal


def is_bearish_macd_cross(macd, signal, prev_macd, prev_signal):
    """
    Returns True if the current bar produces a fresh bearish MACD crossover.

    Conditions:
    - Previous bar: MACD >= Signal
    - Current bar:  MACD < Signal
    """
    if prev_macd is None or prev_signal is None:
        return False  # cannot detect crossover on first bar

    return prev_macd >= prev_signal and macd < signal


def is_bullish_macd_zero_combo(macd, prev_macd, hist, prev_hist):
    """
    Returns True if we get a bullish setup using:
    - MACD above zero (bullish trend filter)
    - Histogram fresh cross above zero (momentum trigger)
    """
    # Need previous values to detect a fresh cross
    if any(v is None for v in (macd, prev_macd, hist, prev_hist)):
        return False

    # Trend filter: MACD must be on the bullish side of zero *now*
    bullish_trend = macd > 0

    # Momentum trigger: histogram crosses up through zero on this bar
    bullish_hist_cross = prev_hist <= 0 and hist > 0

    return bullish_trend and bullish_hist_cross


def is_bearish_macd_zero_combo(macd, prev_macd, hist, prev_hist):
    """
    Returns True if we get a bearish setup using:
    - MACD below zero (bearish trend filter)
    - Histogram fresh cross below zero (momentum trigger)
    """
    if any(v is None for v in (macd, prev_macd, hist, prev_hist)):
        return False

    # Trend filter: MACD must be on the bearish side of zero *now*
    bearish_trend = macd < 0

    # Momentum trigger: histogram crosses down through zero on this bar
    bearish_hist_cross = prev_hist >= 0 and hist < 0

    return bearish_trend and bearish_hist_cross
