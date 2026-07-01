import yfinance as yf
import os
import pandas as pd
from datetime import datetime, timedelta

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)

# -----------------------------
# 2. TICKER LIST (Sample of Midcap 150)
# -----------------------------
MIDCAP_TICKERS = [
    "ASHOKLEY.NS", "APOLLOTYRE.NS", "AUROPHARMA.NS", "BALKRISIND.NS", "BANDHANBNK.NS",
    "BATAINDIA.NS", "BEL.NS", "BHARATFORG.NS", "CHOLAFIN.NS", "CONCOR.NS",
    "CUMMINSIND.NS", "ESCORTS.NS", "FEDERALBNK.NS", "GODREJPROP.NS", "GUJGASLTD.NS",
    "HAL.NS", "HINDPETRO.NS", "IDFCFIRSTB.NS", "IGL.NS", "INDIAMART.NS",
    "IPCALAB.NS", "JSWENERGY.NS", "JUBLFOOD.NS", "LICHSGFIN.NS", "L&TFH.NS",
    "MAXHEALTH.NS", "MFSL.NS", "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS",
    "OBEROIRLTY.NS", "PAGEIND.NS", "PEL.NS", "PFC.NS", "PIDILITIND.NS",
    "POLYCAB.NS", "RECLTD.NS", "SRF.NS", "SYNGENE.NS", "TATACOMM.NS",
    "TATAELXSI.NS", "TRENT.NS", "TVSMOTOR.NS", "VOLTAS.NS", "ZEEL.NS"
]

def fetch_midcaps():
    print(f"Fetching data for {len(MIDCAP_TICKERS)} Midcap stocks...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*5) # 5 years
    
    for ticker in MIDCAP_TICKERS:
        try:
            print(f"Downloading {ticker}...")
            df = yf.download(ticker, start=start_date, end=end_date)
            if not df.empty:
                path = os.path.join(RAW_DIR, f"{ticker}.csv")
                df.to_csv(path)
        except Exception as e:
            print(f"Failed {ticker}: {e}")

if __name__ == "__main__":
    fetch_midcaps()
