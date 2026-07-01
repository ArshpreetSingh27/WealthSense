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
import subprocess

# -----------------------------
# 1. CONFIGURATION
# -----------------------------
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
SIGNALS_FILE = os.path.join(BASE_DIR, "data", "latest_trading_signals.json")
PORTFOLIO_FILE = os.path.join(BASE_DIR, "data", "paper_portfolio.json")

def get_latest_prices():
    """
    Reads the latest close prices from the raw CSV data.
    """
    prices = {}
    for file in os.listdir(RAW_DIR):
        if file.endswith(".csv"):
            ticker = file.replace(".NS.csv", "").replace(".csv", "")
            try:
                df = pd.read_csv(os.path.join(RAW_DIR, file))
                # Handle different formats if necessary
                if 'Close' in df.columns:
                    prices[ticker] = float(df['Close'].iloc[-1])
            except Exception as e:
                print(f"Error reading {file}: {e}")
    return prices

def sync_data():
    """
    Calls data fetching scripts to ensure latest prices are available.
    """
    print("[1/5] Syncing market data...")
    # Add your actual data fetch commands here
    subprocess.run(["python", os.path.join(BASE_DIR, "data/scripts/fetch_benchmarks.py")], check=True)
    subprocess.run(["python", os.path.join(BASE_DIR, "data/scripts/update_pipeline.py")], check=True)
    print("Data sync complete.")

def main():
    print(f"\n--- DAILY SHADOW TRADING PIPELINE ({datetime.now().strftime('%Y-%m-%d')}) ---")
    
    # 1. Sync Data
    sync_data()
    current_prices = get_latest_prices()
    if not current_prices:
        print("[ERROR] No price data found. Check data/raw/ directory.")
        return

    # 2. Initialize Paper Trader
    pt = PaperTrader(portfolio_path=PORTFOLIO_FILE)
    
    # 3. Execute Pending Trades (T+1 logic)
    # These are signals generated yesterday
    print("[2/5] Executing pending trades from yesterday's signals...")
    pt.execute_pending_trades(current_prices)
    
    # 4. Update Portfolio (Mark-to-market & Exits)
    print("[3/5] Updating portfolio valuation and monitoring stops...")
    exits = pt.update_and_monitor(current_prices)
    if exits:
        print(f"Closed positions: {', '.join(exits)}")

    # 5. Generate New Signals for Tomorrow
    print("[4/5] Generating new signals for tomorrow's execution...")
    try:
        # We run the signal generator script
        script_path = os.path.join(BASE_DIR, "data", "scripts", "generate_daily_signals.py")
        subprocess.run(["python", script_path], check=True)
        
        # Load the newly generated signals and queue them in PaperTrader
        with open(SIGNALS_FILE, "r") as f:
            signal_data = json.load(f)
            new_signals = signal_data.get("signals", [])
            pt.queue_signals(new_signals)
    except Exception as e:
        print(f"[ERROR] Signal generation failed: {e}")

    # 6. Run Drift Analysis
    print("[5/5] Running Alpha Drift analysis...")
    run_drift_analysis(PORTFOLIO_FILE)
    
    print("--- PIPELINE COMPLETE ---\n")

if __name__ == "__main__":
    main()
