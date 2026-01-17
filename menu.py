import curses  ## standard on mac, on windows pip install windows-curses
from datetime import datetime
import AIStrategy as AI
import textwrap
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
    "Run Monte-Carlo simulation",
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


def _wrap_lines(text: str, width: int):
    """Return a list of wrapped lines (at least 1), width >= 1."""
    width = max(1, width)
    # keep newlines the user might have
    parts = text.splitlines() or [""]
    out = []
    for p in parts:
        wrapped = textwrap.wrap(
            p,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
        )
        out.extend(wrapped if wrapped else [""])
    return out


def _safe_addstr(stdscr, y: int, x: int, s: str):
    """Add string without throwing if it would go out of bounds."""
    h, w = stdscr.getmaxyx()
    if y < 0 or y >= h:
        return
    if x < 0 or x >= w:
        return
    # clip to remaining width
    stdscr.addnstr(y, x, s, max(0, w - x - 1))


def _draw_form(stdscr, title: str, fields, active_idx: int, message: str = ""):
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    _safe_addstr(stdscr, 0, 0, title)
    _safe_addstr(stdscr, 1, 0, "-" * min(72, w - 1))

    row = 3
    for i, f in enumerate(fields):
        prefix = "> " if i == active_idx else "  "
        line = f"{prefix}{f['label']}: {f['value']}"

        # Wrap to screen width
        wrapped = _wrap_lines(line, width=max(1, w - 1))

        # Draw each wrapped line
        for j, part in enumerate(wrapped):
            _safe_addstr(stdscr, row + j, 0, part)

        # Move row down by however many lines we used
        row += len(wrapped)

    controls = "Controls: ↑/↓ move, E edit/select, Enter run/confirm, Esc cancel"
    _safe_addstr(stdscr, row + 1, 0, controls)

    if message:
        for k, part in enumerate(_wrap_lines(message, width=max(1, w - 1))):
            _safe_addstr(stdscr, row + 3 + k, 0, part)

    stdscr.refresh()


def _edit_text(stdscr, prompt: str, initial: str = "") -> str:
    curses.echo()
    stdscr.clear()

    h, w = stdscr.getmaxyx()
    width = max(1, w - 1)

    # Title
    _safe_addstr(stdscr, 0, 0, prompt)

    # Wrap "Current:" so it doesn't overwrite lines below
    cur_lines = _wrap_lines(f"Current: {initial}", width=width)

    y = 2
    for line in cur_lines:
        if y >= h - 2:
            break
        _safe_addstr(stdscr, y, 0, line)
        y += 1

    # Put "New:" after the wrapped current text
    new_y = y + 1
    if new_y >= h:
        new_y = h - 1

    _safe_addstr(stdscr, new_y, 0, "New: ")
    stdscr.clrtoeol()
    stdscr.refresh()

    # Read input on the same row as "New: "
    # (No practical max: just use a large cap; curses requires a number.)
    s = stdscr.getstr(new_y, 5, 32767).decode("utf-8", errors="ignore").strip()

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
            return -1


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

        elif key in (ord("e"), ord("E")):
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

        elif key in (curses.KEY_ENTER, 10, 13):
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
            return -1


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

        elif key in (ord("e"), ord("E")):
            f = fields[idx]
            f["value"] = _edit_text(
                stdscr, f"Edit {f['label']} (leave blank to keep):", str(f["value"])
            )

        elif key in (curses.KEY_ENTER, 10, 13):
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
            return -1


# ----------------------------
# 3) MACD Bounds Menu
# ----------------------------
def macd_bounds_form(stdscr, defaults=None):
    """
    Returns int or None (cancel):
    macdStrat: int
    Confirm with Enter.
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

        elif key in (curses.KEY_ENTER, 10, 13):
            return fields[idx]["value"]

        elif key in (27, ord("q")):
            return -1


# ----------------------------
# 4) AI prompt Menu
# ----------------------------
def AI_prompt_form(stdscr, defaults=None):
    """
    Returns str or None (cancel):
    prompt: str
    Confirm with Enter.
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

        elif key in (ord("e"), ord("E")):
            f = fields[idx]
            f["value"] = _edit_text(
                stdscr, f"Edit {f['label']} (leave blank to keep):", str(f["value"])
            )

        elif key in (curses.KEY_ENTER, 10, 13):
            return fields[idx]["value"]

        elif key in (27, ord("q")):
            return -1


# ----------------------------
# Convenience wrappers
# ----------------------------
def get_stock_info(defaults=None):
    result = curses.wrapper(stock_info_form, defaults)
    return result


def get_rsi_bounds(defaults=None):
    result = curses.wrapper(rsi_bounds_form, defaults)
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
    while True:
        stock = get_stock_info()
        if stock == -1:
            return -1

        rsi = get_rsi_bounds()
        if rsi == -1:
            continue
        break

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

    while True:
        stock = get_stock_info()
        if stock == -1:
            return stock

        macd = get_macd_bounds()
        if macd == -1:
            continue
        break

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
    while True:
        stock = get_stock_info()
        if stock == -1:
            return -1
        prompt = get_AI_prompt()
        if prompt == -1:
            continue
        break

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


def MonteCarloMenu():
    # ask user for num of iterations
    # select the usual getStockInfo

    pass
