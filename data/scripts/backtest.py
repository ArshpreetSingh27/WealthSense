import os
import pandas as pd
import lightgbm as lgb
import numpy as np
import warnings
warnings.filterwarnings('ignore')

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_file = os.path.join(BASE_DIR, "data", "processed", "nifty50_features.csv")

def run_portfolio_backtest():
    print("Loading data for ROI Backtesting...")
    df = pd.read_csv(csv_file)
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by=['Date', 'Stock']).reset_index(drop=True)

    # 1. DEFINE BACKTEST PERIOD (Last 365 days for a better sample)
    latest_date = df['Date'].max()
    backtest_start = latest_date - pd.Timedelta(days=365)
    
    # 2. SPLIT DATA
    train_df = df[df['Date'] < backtest_start]
    test_df = df[df['Date'] >= backtest_start]
    
    features = [col for col in df.columns if col not in ['Target', 'Date', 'Stock', 'Recommendation', 'Prob_Up', 'Forward_Return_5d']]
    
    X_train = train_df[features]
    y_train = train_df['Target']
    X_test = test_df[features]
    y_test = test_df['Target']

    print(f"\n--- PORTFOLIO BACKTEST: {backtest_start.date()} to {latest_date.date()} ---")
    
    # 3. TRAIN MODEL
    model = lgb.LGBMClassifier(
        objective='binary',
        n_estimators=300,
        learning_rate=0.05,
        max_depth=5,
        num_leaves=31,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train, eval_set=[(X_test, y_test)], callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)])
    
    # 4. SIMULATE TRADING
    test_probs = model.predict_proba(X_test)[:, 1]
    
    print(f"\n--- PROBABILITY STATS ---")
    print(f"Min Prob: {test_probs.min():.4f}")
    print(f"Max Prob: {test_probs.max():.4f}")
    print(f"Mean Prob: {test_probs.mean():.4f}")
    print(f"Std Prob: {test_probs.std():.4f}")

    # Use a threshold variable for easier testing
    BUY_THRESH = 0.55
    test_df['Prob'] = test_probs
    test_df['Rec'] = test_df['Prob'].apply(lambda x: "BUY" if x > BUY_THRESH else "SELL" if x < (1-BUY_THRESH) else "HOLD")
    
    dates = sorted(test_df['Date'].unique())
    
    model_balance = 100000.0
    benchmark_balance = 100000.0
    
    model_history = []
    benchmark_history = []
    
    print("\nSimulating daily trading...")
    total_buys_count = 0
    
    for i, date in enumerate(dates):
        day_data = test_df[test_df['Date'] == date]
        
        # Benchmark logic: Buy all stocks equally
        daily_bench_return = day_data['Return'].mean()
        benchmark_balance *= (1 + daily_bench_return)
        
        # Model logic:
        buys = day_data[day_data['Rec'] == "BUY"]
        
        if len(buys) > 0:
            total_buys_count += len(buys)
            # Equal weight among all BUY signals
            daily_model_return = buys['Forward_Return_5d'].mean() / 5
            model_balance *= (1 + daily_model_return)
            
        model_history.append(model_balance)
        benchmark_history.append(benchmark_balance)

    # 5. RESULTS
    final_model_roi = ((model_balance - 100000) / 100000) * 100
    final_bench_roi = ((benchmark_balance - 100000) / 100000) * 100
    
    print(f"\n--- FINAL PERFORMANCE ---")
    print(f"Total BUY Signals Executed: {total_buys_count}")
    print(f"Starting Capital: 100,000")
    print(f"Model Final Balance: {model_balance:,.2f} ({final_model_roi:+.2f}% ROI)")
    print(f"Benchmark (Nifty 50) Balance: {benchmark_balance:,.2f} ({final_bench_roi:+.2f}% ROI)")
    
    if model_balance > benchmark_balance:
        print(f"\nSUCCESS: The model beat the market by {final_model_roi - final_bench_roi:+.2f}%")
    else:
        print(f"\nCAUTION: The market outperformed the model by {final_bench_roi - final_model_roi:+.2f}%")

if __name__ == "__main__":
    run_portfolio_backtest()
