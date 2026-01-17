from openai import OpenAI
from dotenv import load_dotenv
import os
from pathlib import Path
from trading_models import StrategyBase
import subprocess
import sys
import loading as load


def get_installed_packages() -> str:
    """
    Returns installed packages in the current Python environment.
    Equivalent to `pip freeze`.

    Output format:
    {
        "numpy": "1.26.4",
        "pandas": "2.2.1",
        ...
    }
    """
    result = subprocess.run(
        [sys.executable, "-m", "pip", "freeze"],
        capture_output=True,
        text=True,
        check=True,
    )

    packages = {}
    for line in result.stdout.splitlines():
        if "==" in line:
            name, version = line.split("==", 1)
            packages[name] = version

    return str(packages)


# save a trading strat to file
def save_strategy(code: str, name: str):
    downloads = Path.home() / "Downloads" / "generated_strategies"
    downloads.mkdir(parents=True, exist_ok=True)

    file = downloads / f"{name}.py"
    file.write_text(code, encoding="utf-8")

    return file


load_dotenv()
openAI_key = os.getenv("API_KEY")


# generates a python file that is later run in the simulation enviroment
def generateTradingStrat(prompt: str) -> str:
    client = OpenAI(api_key=openAI_key)
    pkgs = get_installed_packages()

    # start spinner
    load_event, load_thread = load.start_spinnerAI()

    try:
        instr_outline = f"""
            You are generating a Python strategy plugin to be executed via exec() inside an existing backtesting program.

            ABSOLUTE OUTPUT RULES:
            - Output ONLY valid Python source code (no markdown, no backticks, no explanations, no extra text).
            - Do NOT import anything.
            - Do NOT read/write files.
            - Do NOT access network.
            - Do NOT reference any modules except StrategyBase which is already provided in the execution scope.
            - Do NOT execute code at top-level except definitions (no running tests, no prints).

            REQUIRED API (must match exactly):
            - Define a function: build_strategy()
            - build_strategy() must return an instance of a class that inherits from StrategyBase.
            - The returned class MUST implement:
                - on_bar(self, cash, shares, ts, row) -> "BUY" | "SELL" | None

            AVAILABLE DATA EACH BAR:
            - row is like a pandas Series (dict-like). Use ONLY row.get("<column>") to access values.
            - Price columns: "Open", "High", "Low", "Close", "Volume" (may exist)
            - indicators that are provided are: RSI14, MACD, MACD_signal, MACD_hist
            - ts is a pandas Timestamp-like object (you may use ts.month, ts.day, etc.)

            If you have any shares you are currently invested, By selling you sell all the shares.
            You may use cash and shares ONLY to gate signals (e.g. only BUY if ctx.cash > 0).

            SIGNAL SEMANTICS:
            - Return "BUY" when you want the engine to allocate all equity into the asset.
            - Return "SELL" when you want the engine to sell all shares into cash.
            - Return None to hold (do nothing).

            ROBUSTNESS REQUIREMENTS:
            - If there is technical data that doesn't exist, calculate it during runtime from existing data
            - Never assume an indicator exists unless you check for None.
            - Do not mutate row.
            - Keep state ONLY inside self.* variables (e.g., for cross detection you may store previous values).
            - These are the available libraries, do not use any other that need to be downloaded:
            {pkgs}

            CODE STRUCTURE REQUIREMENTS:
            - The file must define ONLY build_strategy() and any helper classes/functions needed for it.
            - The strategy should be deterministic and based ONLY on (ctx, ts, row, internal state).
            Code skeleton in which the StrategyBase is to be used:
            def tradeAIStrategy(TI: TradeInstance, SB: StrategyBase, td):
            cash = TI.startCapital
            shares = 0.0

            td = td.copy() if td is not None else None
            td = td.sort_index()

            first_ts = td.index.min()
            current_month = first_ts.month

            for ts, interval in td.iterrows():
                price = interval["Close"]

                # Add monthly contribution once per month (at the first bar of a new month).
                if ts.month != current_month and TI.monthlyInvesting != 0:
                    cash += TI.monthlyInvesting
                    current_month = ts.month

                action = SB.on_bar(cash, shares, ts, interval)
                if action is not None:
                    if action == "BUY":
                        equity = cash + shares * price
                        shares = TI.buyShares(equity, price)
                        cash = 0
                        TI.buyData.append((ts, price))
                    elif action == "SELL":
                        cash += shares * price
                        shares = 0
                        TI.sellData.append((ts, price))
                equity = cash + shares * price
                TI.priceDataTrade.append((ts, equity))
                TI.endValueTrade = equity
            return

            Now implement the strategy described below.
            """

        full_prompt = instr_outline + "\nUSER STRATEGY DESCRIPTION:\n" + prompt

        resp = client.responses.create(
            model="gpt-5-nano",
            input=full_prompt,
        )
    finally:
        # stop spinner
        load.stop_spinner(load_event, load_thread)

    # Combine all text output (responses API returns objects, not dicts)
    # Prefer the aggregate output_text helper if present.
    if getattr(resp, "output_text", None):
        return resp.output_text

    code_parts = []
    for output in getattr(resp, "output", []) or []:
        # Most models return output.content -> list of text chunks
        for chunk in getattr(output, "content", []) or []:
            if getattr(chunk, "type", None) == "output_text" and getattr(
                chunk, "text", None
            ):
                code_parts.append(chunk.text)
            elif getattr(chunk, "type", None) == "text" and getattr(
                chunk, "text", None
            ):
                code_parts.append(chunk.text)
        if getattr(output, "text", None):
            code_parts.append(output.text)

    code = "".join(code_parts)

    return code


def load_strategy_from_code(code: str):
    scope = {
        "StrategyBase": StrategyBase,
    }
    exec(code, scope)

    if "build_strategy" not in scope:
        raise ValueError("Strategy code must define build_strategy()")

    strategy = scope["build_strategy"]()

    if not isinstance(strategy, StrategyBase):
        raise TypeError("build_strategy() must return a StrategyBase instance")

    save_strategy(code, "test1")

    return strategy


def daily_prompt(
    price,
    rsi,
    macd,
    signal,
    hist,
) -> str:
    client = OpenAI(api_key=openAI_key)

    # start spinner
    load_event, load_thread = load.start_spinnerAI()
    prompt = """
        You are a rule-based trading decision engine. You must decide one action for THIS candle only using ONLY the technical inputs provided below.
        Do not use news, fundamentals, macro, sentiment, or any outside knowledge. Do not assume any missing information. If a value is missing or NaN, choose HOLD.

        Your output MUST be exactly one of these tokens (uppercase) and nothing else:
        BUY
        SELL
        HOLD

        Goal: trade with trend confirmation and avoid overtrading.
        - Prefer BUY when momentum turns bullish and is confirmed.
        - Prefer SELL when momentum turns bearish and is confirmed.
        - Otherwise HOLD.

        Technical inputs for the current candle:
        Close: {close}
        MACD: {macd}
        MACD_signal: {signal}
        MACD_hist: {hist}
        RSI14: {rsi}

        decide what strategy to use to maximize the profit. The strategy are mostly for longer term swing trades. But can also be shorter if you fint it more suitable
        
        Important:
        - You are NOT given position state (whether we already hold shares). Still output the best action based on the rules.
        - Output ONLY: BUY, SELL, or HOLD.
    """

    resp = client.responses.create(
        model="gpt-5-nano",
        input=prompt,
    )

    return resp
