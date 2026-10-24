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
# 3. OPTIMIZED BACKTESTER WITH VOL TARGETING
# -----------------------------
def run_vol_targeted_backtest(df, top_n=10, vol_target=0.10, slippage=0.0005):
    print(f"Running Vol-Targeted Backtest (Target: {vol_target*100}%)")
    
    dates = df.index.unique().sort_values()
    history = []
    
    # State tracking
    current_longs = set()
    current_shorts = set()
    
    for date in dates:
        day_data = df.loc[date]
        day_data = day_data.sort_values("Pred_Return", ascending=False)
        
        # 1. Rank & Buffer Logic
        top_25_longs = day_data.head(25).index.tolist()
        top_25_shorts = day_data.tail(25).index.tolist()
        
        current_longs = {s for s in current_longs if s in top_25_longs}
        current_shorts = {s for s in current_shorts if s in top_25_shorts}
        
        pot_longs = day_data.head(top_n).index.tolist()
        pot_shorts = day_data.tail(top_n).index.tolist()
        
        while len(current_longs) < top_n and pot_longs:
            c = pot_longs.pop(0); current_longs.add(c)
        while len(current_shorts) < top_n and pot_shorts:
            c = pot_shorts.pop(0); current_shorts.add(c)

        # 2. Risk Parity Weights (1/ATR)
        raw_w = {}
        for s in current_longs:
            if s in day_data.index:
                atr = day_data.loc[s, "ATR_Ratio"]
                if isinstance(atr, pd.Series): atr = atr.iloc[0]
                raw_w[s] = 1.0 / max(atr, 0.0001)
        for s in current_shorts:
            if s in day_data.index:
                atr = day_data.loc[s, "ATR_Ratio"]
                if isinstance(atr, pd.Series): atr = atr.iloc[0]
                raw_w[s] = 1.0 / max(atr, 0.0001)
        
        total_raw = sum(raw_w.values())
        
        # 3. Calculate Strategy Return (Unleveraged)
        unlev_ret = 0
        if total_raw > 0:
            for s, w in raw_w.items():
                norm_w = w / total_raw
                ret = day_data.loc[s, "Target_Return"] # THIS IS THE T+1 RETURN
                if isinstance(ret, pd.Series): ret = ret.iloc[0]
                if s in current_longs: unlev_ret += norm_w * ret
                else: unlev_ret -= norm_w * ret
        
        history.append({
            "Date": date,
            "Unlev_Return": unlev_ret - slippage
        })

    perf_df = pd.DataFrame(history).set_index("Date")
    
    # 4. Volatility Scaling (Lookback 20d)
    perf_df["Rolling_Vol"] = perf_df["Unlev_Return"].rolling(20).std() * np.sqrt(252)
    perf_df["Scale"] = (vol_target / perf_df["Rolling_Vol"]).shift(1).fillna(1.0)
    perf_df["Scale"] = perf_df["Scale"].clip(0.5, 2.0) # Cap leverage at 2x
    
    perf_df["Return"] = perf_df["Unlev_Return"] * perf_df["Scale"]
    perf_df["Equity"] = (1 + perf_df["Return"]).cumprod()
    
    # Metrics
    cagr = (perf_df["Equity"].iloc[-1] ** (252 / len(perf_df))) - 1
    vol = perf_df["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol != 0 else 0
    
    print(f"\n================================")
    print(f" FINAL OPTIMIZED PERFORMANCE")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Volatility:   {vol:.2%}")
    print(f"Max Drawdown: {((perf_df['Equity'] - perf_df['Equity'].cummax()) / perf_df['Equity'].cummax()).min():.2%}")
    print(f"================================\n")
    
    perf_df.to_csv(os.path.join(REPORTS_DIR, "final_optimized_equity.csv"))

if __name__ == "__main__":
    run_vol_targeted_backtest(df, vol_target=0.15) # 15% Vol target
