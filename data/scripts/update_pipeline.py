import yfinance as yf
import os
import subprocess
import sys
from datetime import datetime
from universe import TICKERS

"""
WEALTH sense - Data Pipeline Updater

INSTRUCTIONS FOR AUTOMATING DAILY UPDATES:

1. Prerequisite: You need the 'yfinance' and 'pandas' libraries installed.
    > pip install yfinance pandas

2. Running this script manually: 
   Simply execute `python update_pipeline.py`. It will download
   daily history for the tickers defined in `TICKERS`
   and overwrite their respective CSV files in the `data/raw/` directory.
   
3. Running the AI Model:
   After updating the raw CSVs, this script will attempt to execute your 
   feature and training scripts under `data/scripts/`
   to generate fresh predictions and probabilities which are saved to 
   `data/processed/latest_recommendations.json`.

4. Automation (Windows Task Scheduler):
   - Open Windows "Task Scheduler".
   - Click "Create Basic Task...".
   - Name it "WEALTH sense Daily Data Fetch".
   - Trigger: Daily at a specific time (e.g., 6:00 PM after market close).
   - Action: "Start a program".
   - Program/script: Browse to your Python executable (e.g., C:\\Python310\\python.exe).
   - Add arguments: The absolute path to this script (e.g., C:\\...\\WealthSense\\data\\scripts\\update_pipeline.py).
   - "Start in": The absolute path to the 'WealthSense' folder.
"""

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
PRED_MODEL_SCRIPT = os.path.join(BASE_DIR, "data", "scripts", "process_all_stocks.py")
TRAIN_MODEL_SCRIPT = os.path.join(BASE_DIR, "data", "scripts", "train_model.py")

def run_update():
    print(f"[{datetime.now()}] Starting Data Pipeline Update...")
    
    if not os.path.exists(RAW_DIR):
        os.makedirs(RAW_DIR)
        
    failed_tickers = []
    for ticker in TICKERS:
        try:
            print(f"Fetching data for {ticker}...")
            stock = yf.Ticker(ticker)
            # Fetch 10 years of daily historical data
            hist = stock.history(period="10y")
            
            if not hist.empty:
                # Format to match the previous structure
                hist.reset_index(inplace=True)
                hist['Date'] = hist['Date'].dt.tz_localize(None) 
                
                # Create a Multi-index header structure similar to original files if needed, 
                # or save plain CSV (app.py uses skiprows=[1,2] currently which expects multi-level headers.
                # To keep it simple, we just rewrite the file normally and update app.py if needed,
                # but for this script we will save it in standard pandas format.
                
                save_path = os.path.join(RAW_DIR, f"{ticker}.csv")
                
                # Mock a header to match the `skiprows=[1,2]` logic currently in app.py
                # This ensures the new file doesn't break the existing read mechanism
                with open(save_path, 'w') as f:
                    f.write("Price,Adj Close,Close,High,Low,Open,Volume\n")
                    f.write(f"Ticker,{ticker},{ticker},{ticker},{ticker},{ticker},{ticker}\n")
                    f.write("Date,,,,,,\n")
                    for index, row in hist.iterrows():
                        f.write(f"{row['Date']},{row['Close']},{row['Close']},{row['High']},{row['Low']},{row['Open']},{row['Volume']}\n")
                        
                print(f"  -> Saved {save_path}")
            else:
                print(f"  -> No data found for {ticker}")
                failed_tickers.append(ticker)
        except Exception as e:
            print(f"  -> Error fetching {ticker}: {e}")
            failed_tickers.append(ticker)
            
    # Step 2: Trigger the ML prediction pipeline
    print("\nTriggering the Recommendation Engine...")
    if failed_tickers:
        raise RuntimeError(f"Market data update failed for: {', '.join(failed_tickers)}")
    for script in (PRED_MODEL_SCRIPT, TRAIN_MODEL_SCRIPT):
        if not os.path.isfile(script):
            raise FileNotFoundError(f"Required pipeline script missing: {script}")
        subprocess.run([sys.executable, script], cwd=BASE_DIR, check=True)
    print("Recommendation Engine Complete.")
        
    print(f"\n[{datetime.now()}] Data Pipeline Update Completed Successfully.")


if __name__ == "__main__":
    run_update()
