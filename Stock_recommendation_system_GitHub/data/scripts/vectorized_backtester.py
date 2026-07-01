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
# 3. STRATEGY: CROSS-SECTIONAL RANKING
# -----------------------------
def run_backtest(df, top_n=5, cost=0.0005): # 0.05% per side
    print(f"Running backtest with Top/Bottom {top_n} ranking...")
    
    # 1. Rank daily
    df["Rank"] = df.groupby(level=0)["Pred_Return"].rank(ascending=False)
    df["Inverse_Rank"] = df.groupby(level=0)["Pred_Return"].rank(ascending=True)
    
    # 2. Identify Positions
    df["Is_Long"] = df["Rank"] <= top_n
    df["Is_Short"] = df["Inverse_Rank"] <= top_n
    
    # 3. Position Sizing: Volatility Adjusted (1/ATR)
    # Ensure every trade contributes equal risk
    df["Size"] = 1 / df["ATR_Ratio"]
    
    # Normalize sizes daily to sum to 1.0 (Leverage = 1)
    def normalize_size(group):
        longs = group[group["Is_Long"]]
        shorts = group[group["Is_Short"]]
        
        if len(longs) > 0:
            group.loc[group["Is_Long"], "Size"] = (longs["Size"] / longs["Size"].sum()) * 0.5
        if len(shorts) > 0:
            group.loc[group["Is_Short"], "Size"] = (shorts["Size"] / shorts["Size"].sum()) * 0.5
        
        # Non-positions have 0 size
        group.loc[~(group["Is_Long"] | group["Is_Short"]), "Size"] = 0
        return group

    print("Calculating position sizes...")
    df = df.groupby(level=0).apply(normalize_size)
    
    # 4. Calculate Daily Returns
    # Strategy Return = Sum(Size * Target_Return) - Costs
    # We apply costs only when position changes (simplified here as daily friction)
    df["Daily_PnL"] = np.where(df["Is_Long"], df["Size"] * df["Target_Return"], 0)
    df["Daily_PnL"] += np.where(df["Is_Short"], -df["Size"] * df["Target_Return"], 0)
    
    # Aggregate to Portfolio level
    portfolio = df.groupby(level=0)["Daily_PnL"].sum().to_frame("Return")
    portfolio["Return"] = portfolio["Return"] - (cost * 2 * (top_n * 2 / 50)) # Estimating turnover friction
    
    # 5. Metrics
    portfolio["Equity"] = (1 + portfolio["Return"]).cumprod()
    
    cagr = (portfolio["Equity"].iloc[-1] ** (252 / len(portfolio))) - 1
    vol = portfolio["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol # 5% risk-free rate
    
    portfolio["Peak"] = portfolio["Equity"].cummax()
    portfolio["Drawdown"] = (portfolio["Equity"] - portfolio["Peak"]) / portfolio["Peak"]
    max_dd = portfolio["Drawdown"].min()
    
    print(f"\n================================")
    print(f" STRATEGY PERFORMANCE REPORT")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Max Drawdown: {max_dd:.2%}")
    print(f"Volatility:   {vol:.2%}")
    print(f"Final Equity: {portfolio['Equity'].iloc[-1]:.2f}x")
    print(f"================================\n")
    
    # 6. Save Report
    portfolio.to_csv(os.path.join(REPORTS_DIR, "equity_curve.csv"))
    
    # Plot
    plt.figure(figsize=(12, 6))
    plt.plot(portfolio["Equity"], label="Strategy Equity", color="blue")
    plt.title("Master Predictor: Alpha-Risk Strategy Equity Curve")
    plt.xlabel("Date")
    plt.ylabel("Cumulative Growth")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.savefig(os.path.join(REPORTS_DIR, "equity_curve.png"))
    print(f"Equity curve saved to {REPORTS_DIR}")

if __name__ == "__main__":
    run_backtest(df, top_n=10)
