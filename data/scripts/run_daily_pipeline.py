import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(BASE_DIR)

from paper_trader import PaperTrader
from drift_monitor import run_drift_analysis
from universe import active_raw_files
import subprocess
import math
from load_and_plot import load_stock
from realtime import get_live_price

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
SIGNALS_FILE = os.path.join(BASE_DIR, "data", "latest_trading_signals.json")
PORTFOLIO_FILE = os.path.join(BASE_DIR, "data", "paper_portfolio.json")
BACKTEST_FILE = os.path.join(BASE_DIR, "data", "processed", "event_wf_results.csv")

def get_market_date():
    dates = []
    for name in ("NSEI.csv", "NSEBANK.csv"):
        path = os.path.join(BASE_DIR, "data", "raw_benchmarks", name)
        benchmark = pd.read_csv(path, usecols=["Date"])
        dates.append(pd.to_datetime(benchmark["Date"].iloc[-1]).date())
    if dates[0] != dates[1]:
        raise RuntimeError(f"Benchmark dates disagree: {dates}")
    if (pd.Timestamp.now(tz="Asia/Kolkata").date() - dates[0]).days > 7:
        raise RuntimeError(f"Benchmark prices are stale: {dates[0]}")
    return dates[0].isoformat()


def get_latest_prices(market_date, held_tickers=()):
    """
    Reads the latest close prices from the raw CSV data.
    """
    prices = {}
    for file in active_raw_files():
        ticker = file.removesuffix(".NS.csv")
        df = load_stock(os.path.join(RAW_DIR, file))
        if df.empty or df["Date"].iloc[-1].date().isoformat() != market_date:
            raise RuntimeError(f"No current price for {ticker} on {market_date}")
        price = float(df["Close"].iloc[-1])
        if not math.isfinite(price) or price <= 0:
            raise RuntimeError(f"Invalid market price for {ticker}")
        prices[ticker] = price
    for ticker in held_tickers:
        if ticker in prices:
            continue
        live = get_live_price(ticker, period="7d")
        if not live["dates"] or live["dates"][-1] != market_date:
            raise RuntimeError(f"No current price for held position {ticker} on {market_date}")
        prices[ticker] = float(live["current_price"])
    return prices

def sync_data():
    """
    Calls data fetching scripts to ensure latest prices are available.
    """
    print("[1/5] Syncing market data...")
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "data", "scripts", "fetch_benchmarks.py")], cwd=BASE_DIR, check=True)
    subprocess.run([sys.executable, os.path.join(BASE_DIR, "data", "scripts", "update_pipeline.py")], cwd=BASE_DIR, check=True)
    print("Data sync complete.")

def main():
    print(f"\n--- DAILY SHADOW TRADING PIPELINE ({datetime.now().strftime('%Y-%m-%d')}) ---")
    
    # 1. Sync Data
    sync_data()
    market_date = get_market_date()
    pt = PaperTrader(portfolio_path=PORTFOLIO_FILE)
    current_prices = get_latest_prices(market_date, pt.data["positions"])
    
    # 3. Execute Pending Trades (T+1 logic)
    # These are signals generated yesterday
    print("[2/5] Executing pending trades from yesterday's signals...")
    pt.execute_pending_trades(current_prices, market_date)
    
    # 4. Update Portfolio (Mark-to-market & Exits)
    print("[3/5] Updating portfolio valuation and monitoring stops...")
    exits = pt.update_and_monitor(current_prices)
    if exits:
        print(f"Closed positions: {', '.join(exits)}")

    # 5. Generate New Signals for Tomorrow
    print("[4/5] Generating new signals for tomorrow's execution...")
    script_path = os.path.join(BASE_DIR, "data", "scripts", "generate_daily_signals.py")
    subprocess.run([sys.executable, script_path], cwd=BASE_DIR, check=True)
    with open(SIGNALS_FILE, "r") as f:
        signal_data = json.load(f)
    if signal_data.get("market_date") != market_date:
        raise RuntimeError("Generated signals do not match the current market date")
    pt.queue_signals(signal_data["signals"], market_date)

    # 6. Run Drift Analysis
    print("[5/5] Running Alpha Drift analysis...")
    run_drift_analysis(PORTFOLIO_FILE, BACKTEST_FILE)
    
    print("--- PIPELINE COMPLETE ---\n")

if __name__ == "__main__":
    main()
