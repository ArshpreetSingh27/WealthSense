import yfinance as yf
import pandas as pd
import os
from datetime import datetime
import json
import random

"""
Master Predictor - Intraday Data Pipeline Updater
"""

TICKERS = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS", "BHARTIARTL.NS", "BPCL.NS",
    "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DIVISLAB.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "LTIM.NS", "M&M.NS", "MARUTI.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TATACONSUM.NS", "TATAMOTORS.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "SHRIRAMFIN.NS"
]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw_intraday")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
PRED_MODEL_SCRIPT = os.path.join(BASE_DIR, "data", "scripts", "process_intraday_stocks.py") 
TRAIN_SCRIPT = os.path.join(BASE_DIR, "data", "scripts", "train_intraday_model.py")

def run_update():
    print(f"[{datetime.now()}] Starting Intraday Data Pipeline Update...")
    
    if not os.path.exists(RAW_DIR):
        os.makedirs(RAW_DIR)
        
    for ticker in TICKERS:
        try:
            print(f"Fetching intraday data for {ticker}...")
            stock = yf.Ticker(ticker)
            # Fetch 5 days of 5-minute interval data
            hist = stock.history(period="5d", interval="5m")
            
            if not hist.empty:
                hist.reset_index(inplace=True)
                # Keep original timezone info for intraday if needed, but for simplicity:
                hist['Datetime'] = hist['Datetime'].dt.strftime('%Y-%m-%d %H:%M:%S')
                
                save_path = os.path.join(RAW_DIR, f"{ticker}.csv")
                
                # Save as standard CSV for intraday
                hist.to_csv(save_path, index=False)
                print(f"  -> Saved {save_path}")
            else:
                print(f"  -> No data found for {ticker}")
        except Exception as e:
            print(f"  -> Error fetching {ticker}: {e}")
            
    # Step 2: Trigger the ML prediction pipeline
    print("\nTriggering the Intraday Recommendation Engine...")
    if os.path.exists(PRED_MODEL_SCRIPT):
        os.system(f"python \"{PRED_MODEL_SCRIPT}\"")
        
        # Step 3: Train model and output json
        if os.path.exists(TRAIN_SCRIPT):
            os.system(f"python \"{TRAIN_SCRIPT}\"")
            
        print("Intraday Recommendation Engine Complete.")
    else:
        print(f"Model script not found at {PRED_MODEL_SCRIPT}.")
        
    print(f"\n[{datetime.now()}] Intraday Data Pipeline Update Completed Successfully.")

if __name__ == "__main__":
    run_update()
