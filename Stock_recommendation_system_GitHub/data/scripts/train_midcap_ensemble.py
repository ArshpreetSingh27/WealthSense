import os
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.ensemble import RandomForestRegressor
import joblib

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "midcap_features.csv")
MODEL_DIR = os.path.join(BASE_DIR, "data", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
df = df.sort_index()

# Features for Midcap Inefficiency
features = ["Vol_20", "Momentum_60", "Return_Z", "Volume_Shock", 
            "Gap_Return", "BB_Width", "Sector_Vol_Shock"]
target = "Target_Neutral"

# -----------------------------
# 3. TRAINING
# -----------------------------
print(f"Training Midcap Inefficiency Ensemble (N={len(df)})...")

# Use a split that respects time
train_cutoff = df.index.max() - pd.Timedelta(days=365)
train_df = df[df.index <= train_cutoff]
test_df = df[df.index > train_cutoff]

X_train, y_train = train_df[features], train_df[target]
X_test, y_test = test_df[features], test_df[target]

# Model 1: LGBM (Non-linear Alpha)
lgb_model = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, max_depth=6, random_state=42)
lgb_model.fit(X_train, y_train)

# Model 2: RandomForest (Ensemble Robustness)
rf_model = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42)
rf_model.fit(X_train, y_train)

# Save
joblib.dump(lgb_model, os.path.join(MODEL_DIR, "lgb_midcap.pkl"))
joblib.dump(rf_model, os.path.join(MODEL_DIR, "rf_midcap.pkl"))
joblib.dump(features, os.path.join(MODEL_DIR, "midcap_features_list.pkl"))

# Out-of-Sample Predictions
test_df["Pred_Neutral_Return"] = (lgb_model.predict(X_test) + rf_model.predict(X_test)) / 2
test_df.to_csv(os.path.join(BASE_DIR, "data", "processed", "midcap_wf_results.csv"))

print(f"[SUCCESS] Midcap Ensemble Models saved.")
