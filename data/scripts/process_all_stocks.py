import os
import pandas as pd
import numpy as np
from load_and_plot import load_stock
from universe import active_raw_files

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")

os.makedirs(PROCESSED_DIR, exist_ok=True)

# -----------------------------
# 2. LOOP THROUGH ALL STOCK FILES
# -----------------------------
all_dfs = []
latest_rows = []

for file in active_raw_files():

    stock_name = file.replace(".NS.csv", "").replace(".csv", "")
    csv_path = os.path.join(RAW_DIR, file)

    print(f"Processing {stock_name}...")

    # Load stock data safely
    df = load_stock(csv_path)

    if len(df) < 50:
        print(f"Skipping {stock_name} due to insufficient data.")
        continue

    # Sort by date
    df = df.sort_values("Date")

    # -----------------------------
    # 3. FEATURE ENGINEERING (RELATIVE)
    # -----------------------------
    # SMA/EMA (Relative to Close)
    df["SMA_20_Ratio"] = df["Close"] / df["Close"].rolling(window=20).mean()
    df["EMA_20_Ratio"] = df["Close"] / df["Close"].ewm(span=20, adjust=False).mean()
    df["SMA_50_Ratio"] = df["Close"] / df["Close"].rolling(window=50).mean()
    df["EMA_50_Ratio"] = df["Close"] / df["Close"].ewm(span=50, adjust=False).mean()

    # Momentum
    df["Return"] = df["Close"].pct_change()
    
    delta = df['Close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))

    ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_signal']
    # Scaling MACD by Close price to make it relative
    df['MACD_Ratio'] = df['MACD'] / df['Close']

    # Volatility
    df['Volatility'] = df['Return'].rolling(20).std()

    # Bollinger Bands (Relative Distance)
    sma_20 = df["Close"].rolling(window=20).mean()
    std_20 = df["Close"].rolling(window=20).std()
    df['Bollinger_upper'] = sma_20 + 2 * std_20
    df['Bollinger_lower'] = sma_20 - 2 * std_20
    df['BB_Position'] = (df['Close'] - df['Bollinger_lower']) / (df['Bollinger_upper'] - df['Bollinger_lower'])

    # Volume Indicators
    df['Volume_SMA_20'] = df['Volume'].rolling(20).mean()
    df['Volume_Ratio'] = df['Volume'] / df['Volume_SMA_20']
    df['Volume_Change'] = df['Volume'].pct_change()

    # ATR (Average True Range) simplified
    df['High_Low'] = df['High'] - df['Low']
    df['High_CP'] = (df['High'] - df['Close'].shift(1)).abs()
    df['Low_CP'] = (df['Low'] - df['Close'].shift(1)).abs()
    df['TR'] = df[['High_Low', 'High_CP', 'Low_CP']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    df['ATR_Ratio'] = df['ATR'] / df['Close']

    # Trend & Momentum Boosters
    df["SMA_Cross"] = df["SMA_20_Ratio"] / df["SMA_50_Ratio"]
    df["Price_Lag_1"] = df["Return"].shift(1)
    df["RSI_Lag_1"] = df["RSI"].shift(1)
    
    # 52-Week Range Position
    df['52W_High'] = df['Close'].rolling(window=252).max()
    df['52W_Low'] = df['Close'].rolling(window=252).min()
    df['52W_Pos'] = (df['Close'] - df['52W_Low']) / (df['52W_High'] - df['52W_Low'])

    # Daily Range
    df['High_Low_Range'] = (df['High'] - df['Low']) / df['Close']

    # Add stock name (Categorical for LGBM later)
    df["Stock"] = stock_name

    # Target: 1-week ahead up/down
    # Shift(-5) brings next week's close directly to today's row.
    df["Forward_Return_5d"] = (df["Close"].shift(-5) - df["Close"]) / df["Close"]
    df["Target_Date"] = df["Date"].shift(-5)
    df["Target"] = (df["Forward_Return_5d"] > 0).astype(int)

    # -----------------------------
    # 4. CLEAN
    # -----------------------------
    # Drop rows that don't have enough data to calculate all features (e.g. first 50 rows)
    # Also drop the last row where Target is NaN
    # Drop absolute pricing columns that cause overfitting (keep Date for split)
    cols_to_drop = ['High', 'Low', 'Open', 'Volume', 'Close', 'Bollinger_upper', 'Bollinger_lower', 'Volume_SMA_20', 'MACD', 'MACD_signal']
    latest = df.tail(1).drop(columns=cols_to_drop + ['Forward_Return_5d', 'Target_Date', 'Target'], errors='ignore')
    latest = latest.replace([np.inf, -np.inf], np.nan).dropna()
    if not latest.empty:
        latest_rows.append(latest)

    df = df.replace([np.inf, -np.inf], np.nan).dropna()
    df = df.drop(columns=cols_to_drop, errors='ignore')

    df = df.reset_index(drop=True)
    all_dfs.append(df)

# -----------------------------
# 5. COMBINE ALL STOCKS
# -----------------------------
if not all_dfs or not latest_rows:
    raise RuntimeError("No usable training and latest feature rows were generated.")
final_df = pd.concat(all_dfs, ignore_index=True)
latest_df = pd.concat(latest_rows, ignore_index=True)

# -----------------------------
# 6. SAVE FINAL DATASET
# -----------------------------
save_path = os.path.join(PROCESSED_DIR, "nifty50_features.csv")

final_df.to_csv(save_path, index=False, mode="w")
latest_path = os.path.join(PROCESSED_DIR, "nifty50_latest_features.csv")
latest_df.to_csv(latest_path, index=False)

print("\n[SUCCESS] All stocks processed successfully")
print("Saved to:", save_path)
print("Latest features saved to:", latest_path)
print("Final dataset shape:", final_df.shape)
print("Columns:", final_df.columns.tolist())
