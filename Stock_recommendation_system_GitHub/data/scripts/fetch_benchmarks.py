import yfinance as yf
import os
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_benchmarks")
os.makedirs(RAW_DIR, exist_ok=True)

BENCHMARKS = ["^NSEI", "^NSEBANK", "NIFTY_MID_150.NS"]

def fetch_benchmarks():
    print(f"[{datetime.now()}] Fetching benchmark data...")
    for ticker in BENCHMARKS:
        try:
            print(f"Fetching {ticker}...")
            data = yf.download(ticker, period="10y", interval="1d")
            if not data.empty:
                # Flatten multi-index columns if they exist
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = [col[0] for col in data.columns]
                
                output_path = os.path.join(RAW_DIR, f"{ticker.replace('^', '')}.csv")
                data.to_csv(output_path)
                print(f"Saved to {output_path}")
            else:
                print(f"No data for {ticker}")
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")

if __name__ == "__main__":
    fetch_benchmarks()
