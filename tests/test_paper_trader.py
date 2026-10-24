import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "scripts"))
from paper_trader import PaperTrader


class PaperTraderTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.trader = PaperTrader(os.path.join(self.temp_dir.name, "portfolio.json"))
        self.trader.data["capital"] = 1000
        self.trader.data["cash"] = 1000
        self.trader.data["pending_market_date"] = (date.today() - timedelta(days=1)).isoformat()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_closing_one_position_keeps_the_others(self):
        self.trader.data["positions"] = {
            "AAA": {"qty": 2, "entry_price": 10, "side": "LONG"},
            "BBB": {"qty": 3, "entry_price": 20, "side": "LONG"},
        }
        self.trader.data["cash"] = 920
        self.trader.close_position("AAA", 12, "TEST")
        self.assertNotIn("AAA", self.trader.data["positions"])
        self.assertIn("BBB", self.trader.data["positions"])
        self.assertAlmostEqual(self.trader.calculate_total_equity({"BBB": 20}), 1004)

    def test_short_entry_and_exit_preserve_cash_accounting(self):
        self.trader.data["pending_signals"] = [{
            "ticker": "AAA", "signal": "SHORT", "quantity": 10,
            "allocation": 100, "adv_30": 100000000, "vol_20": 0,
        }]
        self.assertEqual(self.trader.execute_pending_trades({"AAA": 10}), 1)
        entry = self.trader.data["positions"]["AAA"]["entry_price"]
        self.assertAlmostEqual(self.trader.calculate_total_equity({"AAA": entry}), 1000)
        self.trader.close_position("AAA", entry - 1, "TEST")
        self.assertAlmostEqual(self.trader.data["cash"], 1010)
        self.assertAlmostEqual(self.trader.calculate_total_equity({}), 1010)

    def test_zero_quantity_does_not_create_position(self):
        self.trader.data["pending_signals"] = [{"ticker": "AAA", "signal": "LONG", "quantity": 0}]
        self.assertEqual(self.trader.execute_pending_trades({"AAA": 10}), 0)
        self.assertEqual(self.trader.data["positions"], {})

    def test_stale_or_undated_pending_signals_are_discarded(self):
        self.trader.data["pending_signals"] = [{"ticker": "AAA", "signal": "LONG", "quantity": 1}]
        self.trader.data["pending_market_date"] = None
        self.assertEqual(self.trader.execute_pending_trades({"AAA": 10}), 0)
        self.assertEqual(self.trader.data["positions"], {})
        self.assertEqual(self.trader.data["pending_signals"], [])


if __name__ == "__main__":
    unittest.main()
