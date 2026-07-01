import os
import pandas as pd
import numpy as np

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

RAW_DIR = os.path.join(BASE_DIR, "data", "raw_intraday")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)

# -----------------------------
# 2. LOOP THROUGH ALL STOCK FILES
# -----------------------------
all_dfs = []

for file in os.listdir(RAW_DIR):
    if not file.endswith(".csv"):
        continue

    stock_name = file.replace(".NS.csv", "").replace(".csv", "")
    csv_path = os.path.join(RAW_DIR, file)

    print(f"Processing {stock_name} intraday...")

    try:
        df = pd.read_csv(csv_path)
    except:
        continue

    if len(df) < 100:
        print(f"Skipping {stock_name} due to insufficient data.")
        continue

    # Sort by datetime
    df['Datetime'] = pd.to_datetime(df['Datetime'])
    df = df.sort_values("Datetime")

    # -----------------------------
    # 3. FEATURE ENGINEERING
    # -----------------------------
    df["Return"] = df["Close"].pct_change()
    
    # RSI (shorter window for intraday)
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Volatility
    df['Volatility'] = df['Return'].rolling(20).std()

    # SMA Ratios
    df["SMA_20_Ratio"] = df["Close"] / df["Close"].rolling(window=20).mean()
    
    # Volume indicator
    df['Volume_Ratio'] = df['Volume'] / df['Volume'].rolling(20).mean()

    # Add stock name
    df["Stock"] = stock_name

    # Target: 1 hour ahead (12 x 5-min bars)
    df["Forward_Return_1h"] = (df["Close"].shift(-12) - df["Close"]) / df["Close"]
    df["Target"] = (df["Forward_Return_1h"] > 0).astype(int)

    # -----------------------------
    # 4. CLEAN
    # -----------------------------
    df = df.dropna()
    
    cols_to_keep = ['Stock', 'Datetime', 'Return', 'RSI', 'Volatility', 'SMA_20_Ratio', 'Volume_Ratio', 'Target', 'Forward_Return_1h']
    df = df[cols_to_keep]

    df = df.reset_index(drop=True)
    all_dfs.append(df)

# -----------------------------
# 5. COMBINE ALL STOCKS
# -----------------------------
if all_dfs:
    final_df = pd.concat(all_dfs, ignore_index=True)
    save_path = os.path.join(PROCESSED_DIR, "intraday_features.csv")
    final_df.to_csv(save_path, index=False)
    print(f"\n[SUCCESS] Intraday dataset saved to: {save_path}")
else:
    print("\n[ERROR] No intraday data processed.")
