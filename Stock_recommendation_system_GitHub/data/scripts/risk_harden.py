import numpy as np

class RiskHarden:
    @staticmethod
    def calculate_dynamic_slippage(volatility, trade_size, adv):
        """
        Calculates dynamic slippage based on market conditions.
        Slippage = Base + Volatility Impact + Market Impact (TradeSize/ADV)
        """
        base_slippage = 0.0002 # 0.02%
        vol_impact = volatility * 0.1
        market_impact = 0.5 * (trade_size / (adv + 1e-6))
        
        return base_slippage + vol_impact + market_impact

    @staticmethod
    def get_atr_stop(current_price, atr, multiplier=2.0):
        """
        Volatility-adjusted stop loss.
        """
        return current_price - (atr * multiplier)

    @staticmethod
    def detect_regime(current_vix, avg_vix):
        """
        Regime Detection: Pause if market is in 'Panic' mode.
        """
        if current_vix > (avg_vix * 1.5):
            return "PANIC"
        return "NORMAL"

    @staticmethod
    def check_alpha_decay(days_held, current_pnl, min_momentum=0.005):
        """
        Exit if alpha hasn't materialized in 3 days.
        """
        if days_held >= 3 and current_pnl < min_momentum:
            return True
        return False

if __name__ == "__main__":
    print("Risk Hardening Module Loaded.")
