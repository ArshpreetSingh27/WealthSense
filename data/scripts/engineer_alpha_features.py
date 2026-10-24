import os
import pandas as pd
import numpy as np
from datetime import datetime
from sector_mapping import get_sector
from event_pipeline import EventPipeline
from sentiment_engine import SentimentEngine

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
BENCH_DIR = os.path.join(BASE_DIR, "data", "raw_benchmarks")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
os.makedirs(PROCESSED_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD BENCHMARK
# -----------------------------
def load_safe_csv(path):
    if not os.path.exists(path): return None
    try:
        df = pd.read_csv(path, skiprows=[1, 2])
        if 'Price' in df.columns: df.rename(columns={'Price': 'Date'}, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date']).set_index('Date')
        for col in ['Close', 'High', 'Low', 'Open', 'Volume']:
            if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.sort_index()
    except: return None

midcap_bench = load_safe_csv(os.path.join(BENCH_DIR, "MIDCAP.csv"))
midcap_bench["Bench_Return"] = midcap_bench["Close"].pct_change()

# -----------------------------
# 3. EVENT-DRIVEN ALPHA
# -----------------------------
all_dfs = []

for file in os.listdir(RAW_DIR):
    if not file.endswith(".csv"): continue
    stock_name = file.replace(".NS.csv", "").replace(".csv", "")
    try:
        df = load_safe_csv(os.path.join(RAW_DIR, file))
        if df is None or len(df) < 252: continue
        
        df = df.join(midcap_bench[["Bench_Return"]], how="inner")
        
        # A. BASIC FEATURES
        df["Return"] = df["Close"].pct_change()
        df["Vol_20"] = df["Return"].rolling(20).std()
        df["ADV_30"] = (df["Volume"] * df["Close"]).rolling(30).mean()
        
        # B. EVENT: PEAD DRIFT (Post-Earnings/Event Drift Proxy)
        df["Gap_Return"] = (df["Open"] - df["Close"].shift(1)) / df["Close"].shift(1)
        df["Volume_Shock"] = df["Volume"] / (df["Volume"].rolling(20).mean() + 1e-6)
        df["Price_Spread"] = (df["High"] - df["Low"]) / (df["Close"] + 1e-6)
        
        df["Vol_Shock_3d"] = df["Volume_Shock"].rolling(3).mean()
        df["PEAD_Signal"] = (df["Gap_Return"] > 0.015) & (df["Vol_Shock_3d"] > 2.0) & (df["Close"] > df["Open"])
        
        # C. EVENT: INSTITUTIONAL FOOTPRINT (Block Deal Proxy)
        df["Block_Deal_Signal"] = (df["Volume_Shock"] > 6.0) & (df["Price_Spread"] < 0.025)
        df["Block_Deal_Signal"] = df["Block_Deal_Signal"].astype(int)
        
        # E. VOLATILITY SQUEEZE (BB Width)
        df["MA_20"] = df["Close"].rolling(20).mean()
        df["BB_Width"] = (df["Close"].rolling(20).std() * 4) / (df["MA_20"] + 1e-6)
        
        # F. ADV & Risk
        df["ADV_30"] = (df["Volume"] * df["Close"]).rolling(30).mean()
        df["ATR_Ratio"] = (df["High"] - df["Low"]).rolling(14).mean() / (df["Close"] + 1e-6)
        df["Persistence_Score"] = df["Close"].pct_change(5) - df["Bench_Return"].rolling(5).sum()
        
        # G. INFORMATION ALPHA (New)
        ep = EventPipeline()
        se = SentimentEngine()
        df = ep.enrich_features(df)
        df = se.simulate_historical_sentiment(df)
        
        df["Sector"] = get_sector(stock_name)
        df["Stock"] = stock_name
        
        # Target: 7-day Forward Neutral Return (To capture the meat of the drift)
        df["Target_Return"] = (df["Close"].shift(-7) - df["Close"]) / df["Close"]
        
        df = df.dropna()
        all_dfs.append(df)
    except Exception as e:
        print(f"Error {stock_name}: {e}")

if all_dfs:
    final_df = pd.concat(all_dfs)
    
    # NEUTRALIZATION
    final_df["Bench_Avg_Target"] = final_df.groupby("Date")["Target_Return"].transform("mean")
    final_df["Target_Neutral"] = final_df["Target_Return"] - final_df["Bench_Avg_Target"]
    
    output_path = os.path.join(PROCESSED_DIR, "event_alpha_features.csv")
    final_df.to_csv(output_path)
    print(f"[SUCCESS] Event Alpha features saved.")
else:
    print("[ERROR] No data.")
