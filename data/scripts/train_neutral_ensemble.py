import os
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.linear_model import Ridge
import joblib
from datetime import datetime

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "trading_features.csv")
MODEL_DIR = os.path.join(BASE_DIR, "data", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
df = df.sort_index()

# Define features for the Neutral Model
features = ["Vol_20", "Beta_Nifty", "Momentum_Score", "Return_Z", 
            "Trend_Intensity", "ATR_Ratio", "Idiosyncratic_Return", 
            "Sector_Z_Score"]

# Target: Sector Neutral Target
target = "Target_Neutral"

# -----------------------------
# 3. WALK-FORWARD TRAINING
# -----------------------------
print("Training Sector-Neutral Alpha Ensemble...")
train_df = df.tail(252 * 5) # Train on last 5 years
X_train, y_train = train_df[features], train_df[target]

# Model 1: LGBM (Non-linear Alpha)
lgb_model = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.03, max_depth=7, random_state=42)
lgb_model.fit(X_train, y_train)

# Model 2: Ridge (Linear Alpha)
ridge_model = Ridge(alpha=10.0)
ridge_model.fit(X_train, y_train)

# Save
joblib.dump(lgb_model, os.path.join(MODEL_DIR, "lgb_neutral.pkl"))
joblib.dump(ridge_model, os.path.join(MODEL_DIR, "ridge_neutral.pkl"))
joblib.dump(features, os.path.join(MODEL_DIR, "neutral_features.pkl"))

# Save a signal file for the backtester
test_df = df.tail(252 * 2) # Test on last 2 years
X_test = test_df[features]
test_df["Pred_Neutral_Return"] = (lgb_model.predict(X_test) + ridge_model.predict(X_test)) / 2
test_df.to_csv(os.path.join(BASE_DIR, "data", "processed", "neutral_wf_results.csv"))

print(f"[SUCCESS] Neutral Alpha Models saved.")
