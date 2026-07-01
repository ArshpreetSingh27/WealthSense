import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
WF_RESULTS_PATH = os.path.join(BASE_DIR, "data", "processed", "walk_forward_results.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD RESULTS
# -----------------------------
df = pd.read_csv(WF_RESULTS_PATH, index_col=0, parse_dates=True)
df = df.sort_index()

# -----------------------------
# 3. ROLLING 5-DAY REBALANCE BACKTESTER
# -----------------------------
def run_rolling_backtest(df, top_n=10, vol_target=0.12, slippage=0.0005):
    print(f"Running Rolling 5-Day Rebalance Backtest (Target: {vol_target*100}%)")
    
    dates = df.index.unique().sort_values()
    history = []
    
    # Portfolio is split into 5 sub-portfolios, each rebalanced every 5 days
    sub_portfolios = [None] * 5
    
    for i, date in enumerate(dates):
        day_data = df.loc[date]
        day_data = day_data.sort_values("Pred_Return", ascending=False)
        
        # Every 5 days, rebalance the i % 5 sub-portfolio
        slot = i % 5
        
        longs = day_data.head(top_n).index.tolist()
        shorts = day_data.tail(top_n).index.tolist()
        
        # Risk Parity weighting for this sub-portfolio
        raw_w = {}
        for s in (longs + shorts):
            atr = day_data.loc[s, "ATR_Ratio"]
            if isinstance(atr, pd.Series): atr = atr.iloc[0]
            raw_w[s] = 1.0 / max(atr, 0.0001)
        
        total_raw = sum(raw_w.values())
        norm_w = {s: w/total_raw for s, w in raw_w.items()} if total_raw > 0 else {}
        
        sub_portfolios[slot] = {
            "longs": {s: norm_w[s] for s in longs},
            "shorts": {s: norm_w[s] for s in shorts}
        }
        
        # Calculate today's return across all 5 sub-portfolios
        daily_ret = 0
        active_slots = 0
        
        for sp in sub_portfolios:
            if sp is None: continue
            active_slots += 1
            sp_ret = 0
            for s, w in sp["longs"].items():
                if s in day_data.index:
                    r = day_data.loc[s, "Return"] # Realized 1-day return
                    if isinstance(r, pd.Series): r = r.iloc[0]
                    sp_ret += w * r
            for s, w in sp["shorts"].items():
                if s in day_data.index:
                    r = day_data.loc[s, "Return"]
                    if isinstance(r, pd.Series): r = r.iloc[0]
                    sp_ret -= w * r
            daily_ret += (1/5) * sp_ret # Each slot is 1/5th of total capital
            
        history.append({
            "Date": date,
            "Unlev_Return": daily_ret - (slippage if i % 5 == 0 else 0) # Apply slippage only on rebalance
        })

    perf_df = pd.DataFrame(history).set_index("Date")
    
    # Vol Targeting
    perf_df["Rolling_Vol"] = perf_df["Unlev_Return"].rolling(20).std() * np.sqrt(252)
    perf_df["Scale"] = (vol_target / perf_df["Rolling_Vol"]).shift(1).fillna(1.0).clip(0.5, 2.0)
    perf_df["Return"] = perf_df["Unlev_Return"] * perf_df["Scale"]
    perf_df["Equity"] = (1 + perf_df["Return"]).cumprod()
    
    # Metrics
    cagr = (perf_df["Equity"].iloc[-1] ** (252 / len(perf_df))) - 1
    vol = perf_df["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol != 0 else 0
    
    print(f"\n================================")
    print(f" FINAL REBALANCED PERFORMANCE")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Volatility:   {vol:.2%}")
    print(f"Max Drawdown: {((perf_df['Equity'] - perf_df['Equity'].cummax()) / perf_df['Equity'].cummax()).min():.2%}")
    print(f"================================\n")

if __name__ == "__main__":
    run_rolling_backtest(df)
