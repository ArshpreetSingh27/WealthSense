import os
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error
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

# Define features
features = ["Vol_20", "Nifty_Return", "Nifty_Vol", "Nifty_Regime", 
            "BankNifty_Return", "Beta_Nifty", "RS_BankNifty", 
            "Momentum_Score", "ATR_Ratio", "Idiosyncratic_Return", 
            "Z_Score_20", "Return_Z", "Trend_Intensity"]
target = "Target_Return"

# -----------------------------
# 3. WALK-FORWARD VALIDATION
# -----------------------------
# We will use a rolling window: 3 years train, 1 year test
years = df.index.year.unique().sort_values()
test_years = years[3:] # Start testing from the 4th year

results = []

print(f"Starting Walk-Forward Validation for {len(test_years)} years...")

for test_year in test_years:
    train_df = df[df.index.year < test_year].tail(252 * 3) # Last 3 years
    test_df = df[df.index.year == test_year]
    
    if len(test_df) == 0: continue
    
    X_train, y_train = train_df[features], train_df[target]
    X_test, y_test = test_df[features], test_df[target]
    
    # Model 1: LightGBM Regressor (Non-linear)
    lgb_model = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.05, max_depth=5, random_state=42, n_jobs=-1)
    lgb_model.fit(X_train, y_train)
    
    # Model 2: Ridge (Linear)
    ridge_model = Ridge(alpha=1.0)
    ridge_model.fit(X_train, y_train)
    
    # Ensemble (Simple Averaging for robustness)
    lgb_preds = lgb_model.predict(X_test)
    ridge_preds = ridge_model.predict(X_test)
    ensemble_preds = (lgb_preds + ridge_preds) / 2
    
    test_df["Pred_Return"] = ensemble_preds
    results.append(test_df)
    
    mse = mean_squared_error(y_test, ensemble_preds)
    print(f"Year {test_year}: MSE={mse:.6f}")

# -----------------------------
# 4. FINAL PRODUCTION MODEL
# -----------------------------
# Train on the most recent data
print("Training final production ensemble...")
final_train = df.tail(252 * 4) # Last 4 years
X_final, y_final = final_train[features], final_train[target]

lgb_final = lgb.LGBMRegressor(n_estimators=300, learning_rate=0.03, max_depth=6, random_state=42)
lgb_final.fit(X_final, y_final)

ridge_final = Ridge(alpha=1.0)
ridge_final.fit(X_final, y_final)

# Save models
joblib.dump(lgb_final, os.path.join(MODEL_DIR, "lgb_ranking.pkl"))
joblib.dump(ridge_final, os.path.join(MODEL_DIR, "ridge_ranking.pkl"))
joblib.dump(features, os.path.join(MODEL_DIR, "ranking_features.pkl"))

# Save walk-forward results for backtester
if results:
    wf_results = pd.concat(results)
    wf_results.to_csv(os.path.join(BASE_DIR, "data", "processed", "walk_forward_results.csv"))
    print(f"[SUCCESS] Walk-forward results saved. Total rows: {len(wf_results)}")
