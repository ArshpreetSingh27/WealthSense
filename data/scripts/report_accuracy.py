import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
import os
import warnings
warnings.filterwarnings('ignore')

def calculate_accuracy(csv_path, time_col, target_col, features, name):
    print(f"\n{'='*40}")
    print(f" REPORT FOR: {name.upper()}")
    print(f"{'='*40}")
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    df[time_col] = pd.to_datetime(df[time_col])
    df = df.sort_values(by=[time_col, 'Stock']).reset_index(drop=True)
    
    if 'Stock' in df.columns:
        df['Stock'] = df['Stock'].astype('category')

    # Rigorous Temporal Split
    unique_times = sorted(df[time_col].unique())
    if not unique_times:
        print("No data found.")
        return
        
    split_idx = int(len(unique_times) * 0.8)
    split_time = unique_times[split_idx]

    train_df = df[df[time_col] < split_time]
    test_df = df[df[time_col] >= split_time]

    if train_df.empty or test_df.empty:
        print(f"Insufficient data for split. Train: {len(train_df)}, Test: {len(test_df)}")
        return

    X_train, y_train = train_df[features], train_df[target_col]
    X_test, y_test = test_df[features], test_df[target_col]

    print(f"Split Time: {split_time}")
    print(f"Training samples: {len(train_df)} ({train_df[time_col].min()} to {train_df[time_col].max()})")
    print(f"Testing samples:  {len(test_df)} ({test_df[time_col].min()} to {test_df[time_col].max()})")

    model = lgb.LGBMClassifier(n_estimators=100, random_state=42, verbose=-1)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    print(f"\nAccuracy Score: {acc:.4f}")
    print("\nConfusion Matrix:")
    print(confusion_matrix(y_test, y_pred))
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))

if __name__ == "__main__":
    # Correct BASE_DIR to root
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    
    # Daily Accuracy
    daily_csv = os.path.join(BASE_DIR, "data", "processed", "nifty50_features.csv")
    daily_features = ['SMA_20_Ratio', 'EMA_20_Ratio', 'SMA_50_Ratio', 'EMA_50_Ratio', 'RSI', 'MACD_Ratio', 
                      'Volatility', 'BB_Position', 'Volume_Ratio', 'Volume_Change', 'High_Low_Range',
                      'SMA_Cross', 'Price_Lag_1', 'RSI_Lag_1', '52W_Pos', 'ATR_Ratio']
    calculate_accuracy(daily_csv, 'Date', 'Target', daily_features, "Daily Prediction (T+1)")
