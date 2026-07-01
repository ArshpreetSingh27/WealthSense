import os
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.linear_model import Ridge
import joblib

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_PATH = os.path.join(BASE_DIR, "data", "processed", "event_alpha_features.csv")
MODEL_DIR = os.path.join(BASE_DIR, "data", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(DATA_PATH, index_col=0, parse_dates=True)
df = df.sort_index()

# Event-Driven + Information Alpha Features
features = ["Vol_20", "Gap_Return", "Volume_Shock", "PEAD_Signal", 
            "Earnings_Surprise_Score", "Insider_Signal", "Sentiment_Score",
            "Persistence_Score", "BB_Width"]
target = "Target_Neutral"

# -----------------------------
# 3. TRAINING
# -----------------------------
print(f"Training Event-Driven Ensemble (N={len(df)})...")

train_cutoff = df.index.max() - pd.Timedelta(days=365)
train_df = df[df.index <= train_cutoff]
test_df = df[df.index > train_cutoff]

X_train, y_train = train_df[features], train_df[target]
X_test, y_test = test_df[features], test_df[target]

# Model 1: LGBM (Structural Breaks)
lgb_model = lgb.LGBMRegressor(n_estimators=400, learning_rate=0.02, max_depth=7, random_state=42)
lgb_model.fit(X_train, y_train)

# Model 2: Ridge (Linear Alpha)
ridge_model = Ridge(alpha=10.0)
ridge_model.fit(X_train, y_train)

# Save
joblib.dump(lgb_model, os.path.join(MODEL_DIR, "lgb_event.pkl"))
joblib.dump(ridge_model, os.path.join(MODEL_DIR, "ridge_event.pkl"))
joblib.dump(features, os.path.join(MODEL_DIR, "event_features_list.pkl"))

# Save Predictions
test_df["Pred_Neutral_Return"] = (lgb_model.predict(X_test) + ridge_model.predict(X_test)) / 2
test_df.to_csv(os.path.join(BASE_DIR, "data", "processed", "event_wf_results.csv"))

print(f"[SUCCESS] Event Ensemble Models saved.")
