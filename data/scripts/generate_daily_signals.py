import os
import pandas as pd
import numpy as np
import joblib
import json
import sys
from datetime import datetime

# Add root to sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.append(BASE_DIR)

from risk_manager import RiskManager
from sector_mapping import get_sector
from universe import active_raw_files

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
BENCH_DIR = os.path.join(BASE_DIR, "data", "raw_benchmarks")
MODEL_DIR = os.path.join(BASE_DIR, "data", "models")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "latest_trading_signals.json")

# -----------------------------
# 2. LOAD MODELS
# -----------------------------
lgb_model = joblib.load(os.path.join(MODEL_DIR, "lgb_neutral.pkl"))
ridge_model = joblib.load(os.path.join(MODEL_DIR, "ridge_neutral.pkl"))
features = joblib.load(os.path.join(MODEL_DIR, "neutral_features.pkl"))

# -----------------------------
# 3. HELPER (Shared with engineer script)
# -----------------------------
def load_safe_csv(path):
    with open(path, 'r') as f: first_line = f.readline()
    if 'Price' in first_line: df = pd.read_csv(path, skiprows=[1, 2])
    else: df = pd.read_csv(path)
    if 'Price' in df.columns: df.rename(columns={'Price': 'Date'}, inplace=True)
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df = df.dropna(subset=['Date'])
        df.set_index('Date', inplace=True)
    for col in ['Close', 'High', 'Low', 'Open', 'Volume']:
        if col in df.columns: df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.sort_index()

# -----------------------------
# 4. GENERATE SIGNALS
# -----------------------------
nifty = load_safe_csv(os.path.join(BENCH_DIR, "NSEI.csv"))
bank_nifty = load_safe_csv(os.path.join(BENCH_DIR, "NSEBANK.csv"))
market_date = min(nifty.index.max(), bank_nifty.index.max())
if (pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None) - market_date).days > 7:
    raise RuntimeError(f"Benchmark data is stale: latest common date {market_date.date()}")

nifty["Nifty_Return"] = nifty["Close"].pct_change()
nifty["Nifty_Vol"] = nifty["Nifty_Return"].rolling(20).std()
nifty["Nifty_SMA_200"] = nifty["Close"].rolling(200).mean()
nifty["Nifty_Regime"] = np.where(nifty["Close"] > nifty["Nifty_SMA_200"], 1, -1)
bank_nifty["BankNifty_Return"] = bank_nifty["Close"].pct_change()

all_predictions = []
failed_stocks = []

print("Generating live signals...")
for file in active_raw_files():
    
    stock_name = file.replace(".NS.csv", "").replace(".csv", "")
    try:
        df = load_safe_csv(os.path.join(RAW_DIR, file))
        if len(df) < 250:
            raise ValueError("Insufficient market history")
        if (pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None) - df.index.max()).days > 7:
            raise ValueError(f"Stale market data: {df.index.max().date()}")
        if df.index.max().date() != market_date.date():
            raise ValueError(f"Stock date {df.index.max().date()} differs from benchmark date {market_date.date()}")
        
        # Latest features only
        last_row = df.tail(1).copy()
        
        # Merge benchmarks
        last_row["Nifty_Return"] = nifty["Nifty_Return"].iloc[-1]
        last_row["Nifty_Vol"] = nifty["Nifty_Vol"].iloc[-1]
        last_row["Nifty_Regime"] = nifty["Nifty_Regime"].iloc[-1]
        last_row["BankNifty_Return"] = bank_nifty["BankNifty_Return"].iloc[-1]
        
        # Re-calculate needed technicals for the last row
        last_row["Return"] = df["Close"].pct_change().iloc[-1]
        last_row["Vol_20"] = df["Close"].pct_change().rolling(20).std().iloc[-1]
        
        # New Alpha Features
        last_row["Return_Z"] = (last_row["Return"] - df["Close"].pct_change().rolling(20).mean().iloc[-1]) / last_row["Vol_20"]
        last_row["Trend_Intensity"] = last_row["Close"] / df["Close"].rolling(50).mean().iloc[-1]
        
        # Beta (simplified for last row)
        last_row["Beta_Nifty"] = 1.0 # Placeholder
        last_row["RS_BankNifty"] = last_row["Return"] - last_row["BankNifty_Return"]
        last_row["Sector_RS"] = last_row["Return"] - nifty["Nifty_Return"].iloc[-1] # Simple proxy
        last_row["Momentum_Score"] = df["Close"].pct_change().rolling(20).mean().iloc[-1] / last_row["Vol_20"]
        last_row["ATR_Ratio"] = (df["High"] - df["Low"]).rolling(14).mean().iloc[-1] / last_row["Close"].iloc[-1]
        last_row["Idiosyncratic_Return"] = last_row["Return"] - (last_row["Beta_Nifty"] * last_row["Nifty_Return"])
        last_row["Alpha_Divergence"] = last_row["Idiosyncratic_Return"] * (1 / last_row["Vol_20"])
        last_row["Z_Score_20"] = (last_row["Close"] - df["Close"].rolling(20).mean().iloc[-1]) / df["Close"].rolling(20).std().iloc[-1]
        
        # Sector Assignment
        last_row["Sector"] = get_sector(stock_name)
        last_row["ADV_30"] = df["Volume"].rolling(30).mean().iloc[-1]
        
        # Ensemble Prediction
        X = last_row[features]
        # Use Neutral models
        lgb_n = joblib.load(os.path.join(MODEL_DIR, "lgb_neutral.pkl"))
        ridge_n = joblib.load(os.path.join(MODEL_DIR, "ridge_neutral.pkl"))
        
        p1 = lgb_n.predict(X)[0]
        p2 = ridge_n.predict(X)[0]
        pred_return = (p1 + p2) / 2
        
        all_predictions.append({
            "ticker": stock_name,
            "sector": last_row["Sector"].iloc[0],
            "pred_return": float(pred_return),
            "atr_ratio": float(last_row["ATR_Ratio"].iloc[0]),
            "vol_20": float(last_row["Vol_20"].iloc[0]),
            "price": float(last_row["Close"].iloc[0]),
            "adv_30": float(last_row["ADV_30"].iloc[0])
        })
    except Exception as e:
        print(f"Error processing {stock_name}: {e}")
        failed_stocks.append(stock_name)

if failed_stocks:
    raise RuntimeError(f"No signals published; failed stocks: {', '.join(failed_stocks)}")
if len(all_predictions) < 20:
    raise RuntimeError("No signals published; fewer than 20 stocks were processed.")

# Rank and Output
all_predictions.sort(key=lambda x: x["pred_return"], reverse=True)

# 1. Initial Portfolio Construction (Top 10 Long, Bottom 10 Short)
top_10 = all_predictions[:10]
bot_10 = all_predictions[-10:]

def prepare_raw_signals(stocks, direction):
    # Equal risk contribution (1/ATR)
    sum_inv_vol = sum(1/s["atr_ratio"] for s in stocks)
    for s in stocks:
        s["weight"] = (1/s["atr_ratio"] / sum_inv_vol) * 0.5 * (1 if direction == "LONG" else -1)
        s["signal"] = direction
    return stocks

raw_signals = prepare_raw_signals(top_10, "LONG") + prepare_raw_signals(bot_10, "SHORT")

# 2. Apply Institutional Risk Manager
rm = RiskManager(capital=1000000)
paper_portfolio_file = os.path.join(BASE_DIR, "data", "paper_portfolio.json")
current_drawdown = 0.0
if os.path.exists(paper_portfolio_file):
    with open(paper_portfolio_file, encoding="utf-8") as portfolio_file:
        paper_portfolio = json.load(portfolio_file)
    current_drawdown = rm.current_drawdown(paper_portfolio.get("equity_history", []))
final_signals = rm.apply_constraints(raw_signals, current_drawdown=current_drawdown)

with open(OUTPUT_FILE, "w") as f:
    json.dump({
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "market_date": market_date.strftime("%Y-%m-%d"),
        "signals": final_signals,
        "market_regime": "BULL" if nifty["Nifty_Regime"].iloc[-1] == 1 else "BEAR",
        "risk_metrics": rm.get_risk_metrics(final_signals)
    }, f, indent=4)

print(f"[SUCCESS] Trading signals generated at {OUTPUT_FILE}")
