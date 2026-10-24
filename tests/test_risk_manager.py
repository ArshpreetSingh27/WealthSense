import unittest

from risk_manager import RiskManager


class RiskManagerTests(unittest.TestCase):
    def test_drawdown_blocks_new_signals(self):
        manager = RiskManager(capital=1000, drawdown_kill=0.10)
        history = [{"equity": 1000}, {"equity": 1100}, {"equity": 950}]
        drawdown = manager.current_drawdown(history)
        self.assertGreater(drawdown, 0.10)
        signals = [{"ticker": "AAA", "sector": "IT", "weight": 0.05, "price": 10, "adv_30": 10000}]
        self.assertEqual(manager.apply_constraints(signals, drawdown), [])


if __name__ == "__main__":
    unittest.main()
