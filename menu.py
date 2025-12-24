import curses  ## standard on mac, on windows pip install windows-curses
from datetime import datetime
import AIStrategy as AI
from trading_models import (
    StrategyBase,
    RSITradeStrat,
    MACDTradeStrat,
    AITradingStrat,
    TradeInstance,
)


OPTIONS = [
    "Run RSI trading strategy",
    "Run MACD trading strategy",
    "(new)Create your own trading strategy with AI",
    "Let AI control your portfolio (coming soon)",
    "Quit",
]


def run_menu():
    return curses.wrapper(menu)


def menu(stdscr):

    curses.curs_set(0)  # hide cursor
    stdscr.nodelay(False)  # wait for keypress
    stdscr.keypad(True)  # enable arrow keys

    idx = 0
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, "Select an option (↑/↓, Enter):\n")

        for i, opt in enumerate(OPTIONS):
            prefix = "➤ " if i == idx else "  "
            stdscr.addstr(2 + i, 0, f"{prefix}{opt}")

        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(OPTIONS)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(OPTIONS)
        elif key in (curses.KEY_ENTER, 10, 13):  # Enter
            return idx
        elif key in (27, ord("q")):  # Esc or q
            return len(OPTIONS) - 1


import curses
from datetime import datetime

INTERVALS = ["1d", "1h", "30m", "15m", "5m", "3m", "2m", "1m"]


# ----------------------------
# Small helpers (shared)
# ----------------------------
def _safe_int(s, default=None):
    try:
        return int(str(s).strip())
    except Exception:
        return default


def _validate_date(s: str) -> bool:
    try:
        datetime.strptime(s.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _draw_form(stdscr, title: str, fields, active_idx: int, message: str = ""):
    stdscr.clear()
    stdscr.addstr(0, 0, title + "\n")
    stdscr.addstr(1, 0, "-" * 72)

    row = 3
    for i, f in enumerate(fields):
        prefix = "> " if i == active_idx else "  "
        stdscr.addstr(row, 0, f"{prefix}{f['label']}: {f['value']}")
        row += 1

    stdscr.addstr(
        row + 1, 0, "Controls: ↑/↓ move, Enter edit/select, R run/confirm, Esc cancel"
    )
    if message:
        stdscr.addstr(row + 3, 0, message)
    stdscr.refresh()


def _edit_text(stdscr, prompt: str, initial: str = "") -> str:
    curses.echo()
    stdscr.clear()
    stdscr.addstr(0, 0, prompt)
    stdscr.addstr(2, 0, f"Current: {initial}")
    stdscr.addstr(4, 0, "New: ")
    stdscr.refresh()
    s = stdscr.getstr(4, 5, 1000).decode("utf-8").strip()
    curses.noecho()
    return s if s else initial


def _select_from_list(stdscr, title: str, options, start_idx: int = 0):
    stdscr.keypad(True)
    idx = start_idx
    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, title + " (↑/↓, Enter, Esc)\n")
        stdscr.addstr(1, 0, "-" * 50)

        for i, opt in enumerate(options):
            prefix = "> " if i == idx else "  "
            stdscr.addstr(3 + i, 0, f"{prefix}{opt}")

        stdscr.refresh()
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(options)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(options)
        elif key in (curses.KEY_ENTER, 10, 13):
            return options[idx]
        elif key in (27, ord("q")):
            return None


# ----------------------------
# 1) Reusable Stock Info Menu
# ----------------------------
def stock_info_form(stdscr, defaults=None):
    """
    Returns dict or None (cancel):
      {
        "ticker": str,
        "interval": str,
        "start": str (YYYY-MM-DD),
        "end": str (YYYY-MM-DD),
        "capital": int,
        "monthly": int
      }
    Confirm with R/r.
    """
    defaults = defaults or {}
    fields = [
        {
            "key": "ticker",
            "label": "Ticker",
            "type": "text",
            "value": defaults.get("ticker", "SPY"),
        },
        {
            "key": "interval",
            "label": "Candle interval",
            "type": "select",
            "value": defaults.get("interval", "1d"),
        },
        {
            "key": "start",
            "label": "Start date (YYYY-MM-DD)",
            "type": "date",
            "value": defaults.get("start", "2000-01-01"),
        },
        {
            "key": "end",
            "label": "End date (YYYY-MM-DD)",
            "type": "date",
            "value": defaults.get("end", "2025-01-01"),
        },
        {
            "key": "capital",
            "label": "Starting capital",
            "type": "int",
            "value": str(defaults.get("capital", "0")),
        },
        {
            "key": "monthly",
            "label": "Monthly investing",
            "type": "int",
            "value": str(defaults.get("monthly", "1000")),
        },
    ]

    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    idx = 0
    msg = ""

    while True:
        _draw_form(stdscr, "Stock Setup", fields, idx, msg)
        msg = ""
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(fields)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(fields)

        elif key in (curses.KEY_ENTER, 10, 13):
            f = fields[idx]
            if f["type"] == "select":
                start_idx = (
                    INTERVALS.index(f["value"]) if f["value"] in INTERVALS else 0
                )
                chosen = _select_from_list(
                    stdscr, "Select interval", INTERVALS, start_idx
                )
                if chosen is not None:
                    f["value"] = chosen
            else:
                f["value"] = _edit_text(
                    stdscr, f"Edit {f['label']} (leave blank to keep):", str(f["value"])
                )

        elif key in (ord("r"), ord("R")):
            data = {f["key"]: str(f["value"]).strip() for f in fields}

            if not data["ticker"]:
                msg = "Ticker cannot be empty."
                continue
            if not _validate_date(data["start"]) or not _validate_date(data["end"]):
                msg = "Dates must be YYYY-MM-DD."
                continue
            capital = _safe_int(data["capital"])
            monthly = _safe_int(data["monthly"])
            if capital is None or monthly is None or capital < 0 or monthly < 0:
                msg = "Capital/monthly must be integers >= 0."
                continue
            interval = data["interval"]
            if interval not in INTERVALS:
                msg = f"Interval must be one of: {', '.join(INTERVALS)}"
                continue

            return {
                "ticker": data["ticker"].upper(),
                "interval": interval,
                "start": data["start"],
                "end": data["end"],
                "capital": capital,
                "monthly": monthly,
            }

        elif key in (27, ord("q")):
            return None


# ----------------------------
# 2) RSI Bounds Menu
# ----------------------------
def rsi_bounds_form(stdscr, defaults=None):
    """
    Returns dict or None (cancel):
      { "lower": int, "upper": int }
    Confirm with R/r.
    """
    defaults = defaults or {}
    fields = [
        {
            "key": "lower",
            "label": "Buy RSI (lower)",
            "type": "int",
            "value": str(defaults.get("lower", "30")),
        },
        {
            "key": "upper",
            "label": "Sell RSI (upper)",
            "type": "int",
            "value": str(defaults.get("upper", "70")),
        },
    ]

    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    idx = 0
    msg = ""

    while True:
        _draw_form(stdscr, "RSI Bounds Setup", fields, idx, msg)
        msg = ""
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(fields)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(fields)

        elif key in (curses.KEY_ENTER, 10, 13):
            f = fields[idx]
            f["value"] = _edit_text(
                stdscr, f"Edit {f['label']} (leave blank to keep):", str(f["value"])
            )

        elif key in (ord("r"), ord("R")):
            data = {f["key"]: f["value"] for f in fields}
            lower = _safe_int(data["lower"])
            upper = _safe_int(data["upper"])

            if lower is None or upper is None:
                msg = "RSI bounds must be integers."
                continue
            if not (0 <= lower <= 100 and 0 <= upper <= 100 and lower < upper):
                msg = "Invalid RSI bounds. Example: lower=30, upper=70 (lower < upper)."
                continue

            return {"lower": lower, "upper": upper}

        elif key in (27, ord("q")):
            return None


# ----------------------------
# 3) MACD Bounds Menu
# ----------------------------
def macd_bounds_form(stdscr, defaults=None):
    """
    Returns int or None (cancel):
    macdStrat: int
    Confirm with R/r.
    """
    defaults = defaults or {}
    fields = [
        {
            "key": "Strat_1",
            "label": "Crossing of MACD and the signal line",
            "type": "int",
            "value": int("1"),
        },
        {
            "key": "Strat_2",
            "label": "Crossing the zero line",
            "type": "int",
            "value": int("2"),
        },
    ]

    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    idx = 0
    msg = ""

    while True:
        _draw_form(stdscr, "MACD strategy setup", fields, idx, msg)
        msg = ""
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(fields)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(fields)

        elif key in (ord("r"), ord("R")):
            return fields[idx]["value"]

        elif key in (27, ord("q")):
            return None


# ----------------------------
# 4) AI prompt Menu
# ----------------------------
def AI_prompt_form(stdscr, defaults=None):
    """
    Returns str or None (cancel):
    prompt: str
    Confirm with R/r.
    """
    defaults = defaults or {}
    fields = [
        {
            "key": "autoPrompt",
            "label": "Prompt: ",
            "type": "int",
            "value": "Create a strategy that buys when low and sells when high.",
        },
    ]

    curses.curs_set(0)
    stdscr.nodelay(False)
    stdscr.keypad(True)

    idx = 0
    msg = ""

    while True:
        _draw_form(stdscr, "AI strategy setup", fields, idx, msg)
        msg = ""
        key = stdscr.getch()

        if key in (curses.KEY_UP, ord("k")):
            idx = (idx - 1) % len(fields)
        elif key in (curses.KEY_DOWN, ord("j")):
            idx = (idx + 1) % len(fields)

        elif key in (curses.KEY_ENTER, 10, 13):
            f = fields[idx]
            f["value"] = _edit_text(
                stdscr, f"Edit {f['label']} (leave blank to keep):", str(f["value"])
            )

        elif key in (ord("r"), ord("R")):
            return fields[idx]["value"]

        elif key in (27, ord("q")):
            return None


# ----------------------------
# Convenience wrappers
# ----------------------------
def get_stock_info(defaults=None):
    result = curses.wrapper(stock_info_form, defaults)
    print()  # nice cursor placement after curses
    return result


def get_rsi_bounds(defaults=None):
    result = curses.wrapper(rsi_bounds_form, defaults)
    print()
    return result


def get_macd_bounds(defaults=None):
    result = curses.wrapper(macd_bounds_form, defaults)
    return result


def get_AI_prompt(defaults=None):
    result = curses.wrapper(AI_prompt_form, defaults)
    return result


# ----------------------------
# Example: your RSIStratMenu
# ----------------------------
def RSIStratMenu():
    stock = get_stock_info()
    if stock is None:
        return None

    rsi = get_rsi_bounds()
    if rsi is None:
        return None

    TI = TradeInstance(
        stock["ticker"],
        stock["start"],
        stock["end"],
        stock["interval"],
        stock["capital"],
        stock["monthly"],
    )
    RTS = RSITradeStrat(rsi["lower"], rsi["upper"])
    return [TI, RTS]


def macdMenu():
    stock = get_stock_info()
    if stock is None:
        return None

    macd = get_macd_bounds()
    if macd is None:
        return None

    TI = TradeInstance(
        stock["ticker"],
        stock["start"],
        stock["end"],
        stock["interval"],
        stock["capital"],
        stock["monthly"],
    )
    MS = MACDTradeStrat(macd)

    return [TI, MS]


def AIprompt():
    stock = get_stock_info()
    if stock is None:
        return None
    prompt = get_AI_prompt()
    if prompt is None:
        return None

    TI = TradeInstance(
        stock["ticker"],
        stock["start"],
        stock["end"],
        stock["interval"],
        stock["capital"],
        stock["monthly"],
    )

    code = AI.generateTradingStrat(prompt)
    strategy: StrategyBase = AI.load_strategy_from_code(code)
    AS = AITradingStrat(strategy)

    return [TI, AS]
