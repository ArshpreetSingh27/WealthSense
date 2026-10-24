import os
import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, mean_absolute_error
import matplotlib.pyplot as plt
import warnings

warnings.filterwarnings('ignore')

# =========================
# PATH SETUP
# =========================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRICE_FEATURES = os.path.join(BASE_DIR, "data", "processed", "nifty50_features.csv")
OPTIONS_FEATURES = os.path.join(BASE_DIR, "data", "options", "historical_options_features.csv")

def train_enhanced():
    print("Loading datasets...")
    if not os.path.exists(PRICE_FEATURES):
        print("Error: Price features CSV missing. Run process_all_stocks.py first.")
        return

    df_price = pd.read_csv(PRICE_FEATURES)
    df_price['Date'] = pd.to_datetime(df_price['Date'])
    
    # Check if options data exists
    if not os.path.exists(OPTIONS_FEATURES):
        print("Warning: Historical options features CSV missing. Creating mockup for demonstration...")
        # Creation of mock data based on price data for training demo purposes
        # In production, this would be populated by collect_options_data.py over time
        df_opt = df_price[['Date', 'Stock']].copy()
        df_opt['Ticker'] = df_opt['Stock']
        df_opt['PCR'] = np.random.uniform(0.6, 1.4, len(df_opt))
        df_opt['IV_Skew'] = np.random.uniform(-0.05, 0.05, len(df_opt))
        df_opt['MaxPain_Diff_Pct'] = np.random.uniform(-0.02, 0.02, len(df_opt))
        df_opt['ITM_CE_OI'] = np.random.randint(100000, 500000, len(df_opt))
        df_opt['OTM_CE_OI'] = np.random.randint(100000, 500000, len(df_opt))
    else:
        df_opt = pd.read_csv(OPTIONS_FEATURES)
        df_opt['Date'] = pd.to_datetime(df_opt['Date'])
        # Map Ticker NIFTY -> NIFTY50 (or whatever is in price df)
        df_opt['Stock'] = df_opt['Ticker'].replace({"NIFTY": "NIFTY50", "BANKNIFTY": "BANKNIFTY"})

    # =========================
    # DATA ALIGNMENT & JOIN
    # =========================
    print("Merging price and options features...")
    df = pd.merge(df_price, df_opt, on=['Date', 'Stock'], how='inner')
    
    if df.empty:
        print("Merge resulted in empty dataframe. Ensure dates match.")
        return

    # Regression Target: Actual Price in 5 days (if available) or Return
    # Here we assume process_all_stocks.py already added 'Forward_Return_5d'
    # We will predict next week's absolute price multiplier (Return + 1)
    target = 'Forward_Return_5d'
    
    # Feature Selection
    # Drop non-feature columns
    cols_to_exclude = ['Date', 'Stock', 'Ticker', 'Target', target]
    features = [c for c in df.columns if c not in cols_to_exclude]
    
    print(f"Training on {len(df)} samples with {len(features)} features.")
    
    # Chronological Split
    df = df.sort_values('Date')
    train_size = int(len(df) * 0.8)
    train_df = df.iloc[:train_size]
    test_df = df.iloc[train_size:]
    
    X_train, y_train = train_df[features], train_df[target]
    X_test, y_test = test_df[features], test_df[target]
    
    # =========================
    # MODEL: LIGHTGBM REGRESSION
    # =========================
    model = lgb.LGBMRegressor(
        n_estimators=500,
        learning_rate=0.03,
        max_depth=6,
        num_leaves=31,
        importance_type='gain', # Use GAIN for better feature contribution analysis
        random_state=42
    )
    
    print("Fitting Enhanced model...")
    model.fit(
        X_train, y_train,
        eval_set=[(X_test, y_test)],
        eval_metric='rmse',
        callbacks=[lgb.early_stopping(50)]
    )
    
    # =========================
    # EVALUATION
    # =========================
    y_pred = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    mae = mean_absolute_error(y_test, y_pred)
    
    print("\n--- PERFORMANCE METRICS ---")
    print(f"RMSE: {rmse:.4f}")
    print(f"MAE:  {mae:.4f}")
    
    # =========================
    # FEATURE IMPORTANCE
    # =========================
    importance = pd.DataFrame({
        'Feature': features,
        'Importance': model.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    print("\n--- TOP 10 FEATURES ---")
    print(importance.head(10))
    
    # Save model metadata
    importance.to_csv(os.path.join(BASE_DIR, "data", "processed", "feature_importance.csv"), index=False)
    print("\nTraining Complete.")

if __name__ == "__main__":
    train_enhanced()
