import json
import os
import pandas as pd
import numpy as np

def run_drift_analysis(paper_path="data/paper_portfolio.json", backtest_path="data/processed/event_wf_results.csv"):
    """
    Compares paper trading performance with backtest results to detect Alpha Drift.
    """
    # 1. Load Paper Data
    if not os.path.exists(paper_path):
        print(f"[ERROR] Paper portfolio not found at {paper_path}")
        return

    with open(paper_path, "r") as f:
        paper_data = json.load(f)
    
    equity_history = pd.DataFrame(paper_data["equity_history"])
    if len(equity_history) < 2:
        print("[INFO] Not enough live data for drift analysis (need at least 2 days).")
        return

    equity_history["Live_Return"] = equity_history["equity"].pct_change()
    
    # Calculate Live Max Drawdown
    equity_history["Peak"] = equity_history["equity"].cummax()
    equity_history["Drawdown"] = (equity_history["equity"] - equity_history["Peak"]) / equity_history["Peak"]
    max_dd_live = equity_history["Drawdown"].min()
    
    # 2. Load Backtest Data
    if not os.path.exists(backtest_path):
        print(f"[WARNING] Backtest results not found at {backtest_path}. Using historical defaults.")
        bt_sharpe = 2.1
        bt_win_rate = 0.58
        bt_max_dd = -0.12
    else:
        backtest_df = pd.read_csv(backtest_path)
        # Assuming Pred_Neutral_Return is the relevant column from backtest
        bt_returns = backtest_df["Pred_Neutral_Return"] if "Pred_Neutral_Return" in backtest_df.columns else backtest_df.iloc[:, -1]
        bt_sharpe = (bt_returns.mean() / (bt_returns.std() + 1e-6)) * np.sqrt(252)
        bt_win_rate = (bt_returns > 0).mean()
        # Max DD from backtest (simplified)
        bt_cum_prod = (1 + bt_returns).cumprod()
        bt_peak = bt_cum_prod.cummax()
        bt_max_dd = ((bt_cum_prod - bt_peak) / bt_peak).min()
    
    # 3. Live Metrics
    live_returns = equity_history["Live_Return"].dropna()
    live_sharpe = (live_returns.mean() / (live_returns.std() + 1e-6)) * np.sqrt(252)
    live_win_rate = (live_returns > 0).mean()
    
    # 4. Drift Assessment
    sharpe_gap = live_sharpe - bt_sharpe
    win_rate_gap = live_win_rate - bt_win_rate
    dd_breach = max_dd_live < (bt_max_dd * 1.5) # Breach if live DD is 50% worse than backtest
    
    print("\n" + "="*40)
    print("      SHADOW MODE DRIFT REPORT")
    print("="*40)
    print(f"Days Active:      {len(equity_history)}")
    print(f"Metric          | Live    | Backtest")
    print(f"----------------|---------|---------")
    print(f"Sharpe Ratio    | {live_sharpe:7.2f} | {bt_sharpe:7.2f}")
    print(f"Win Rate        | {live_win_rate:7.1%} | {bt_win_rate:7.1%}")
    print(f"Max Drawdown    | {max_dd_live:7.1%} | {bt_max_dd:7.1%}")
    print("-" * 40)
    
    # 5. Alerts & Scaling Recommendation
    status = "[OK] STABLE"
    recommendation = "Maintain Shadow Mode."
    
    if dd_breach:
        status = "[CRITICAL] BREACH"
        recommendation = "STOP! Live drawdown exceeds backtest limits. Check for regime change."
    elif sharpe_gap < -1.0 or win_rate_gap < -0.15:
        status = "[WARNING] DRIFT"
        recommendation = "Performance significantly below backtest. Investigate slippage/look-ahead."
    elif len(equity_history) > 30 and live_sharpe > 1.5:
        status = "[OPTIMISTIC] READY"
        recommendation = "Consistent performance. Ready to deploy 25% Real Capital."

    print(f"STATUS:         {status}")
    print(f"ADVICE:         {recommendation}")
    print("="*40 + "\n")

    return {
        "status": status,
        "live_sharpe": live_sharpe,
        "live_win_rate": live_win_rate,
        "max_drawdown": max_dd_live
    }


if __name__ == "__main__":
    run_drift_analysis()
