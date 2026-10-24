import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
EQUITY_PATH = os.path.join(BASE_DIR, "data", "reports", "optimized_equity.csv")

if not os.path.exists(EQUITY_PATH):
    print("Error: Optimized equity curve not found. Run optimized_backtester first.")
    exit()

df = pd.read_csv(EQUITY_PATH)
returns = df["Return"].dropna()

def run_monte_carlo(returns, num_sims=1000, horizon=252):
    print(f"Running {num_sims} Monte Carlo simulations...")
    sim_results = []
    
    for _ in range(num_sims):
        # Sample with replacement
        sim_returns = np.random.choice(returns, size=horizon)
        equity_curve = np.cumprod(1 + sim_returns)
        sim_results.append(equity_curve)
        
    sim_results = np.array(sim_results)
    
    # Analyze
    final_returns = sim_results[:, -1]
    sharpes = (np.mean(sim_results[:, -1]) - 1) / np.std(sim_results[:, -1])
    
    print(f"\n================================")
    print(f" MONTE CARLO STRESS TEST")
    print(f"================================")
    print(f"Mean Final Equity: {np.mean(final_returns):.2f}x")
    print(f"5th Percentile:    {np.percentile(final_returns, 5):.2f}x")
    print(f"95th Percentile:   {np.percentile(final_returns, 95):.2f}x")
    print(f"Prob. of Loss:     {np.mean(final_returns < 1.0)*100:.1f}%")
    print(f"================================\n")
    
    # Plot
    plt.figure(figsize=(10, 6))
    for i in range(min(num_sims, 100)):
        plt.plot(sim_results[i], color='gray', alpha=0.1)
    
    plt.plot(np.percentile(sim_results, 50, axis=0), color='blue', label='Median')
    plt.plot(np.percentile(sim_results, 5, axis=0), color='red', linestyle='--', label='5th Percentile (Stress)')
    plt.title("Monte Carlo: 1,000 Portfolio Path Simulations")
    plt.legend()
    plt.savefig(os.path.join(BASE_DIR, "data", "reports", "monte_carlo.png"))

if __name__ == "__main__":
    run_monte_carlo(returns)
