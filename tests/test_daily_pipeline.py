import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "scripts"))
from drift_monitor import run_drift_analysis
from run_daily_pipeline import get_latest_prices


class DailyPipelineTests(unittest.TestCase):
    def test_held_position_must_have_a_current_price_before_paper_trades(self):
        stock = pd.DataFrame({"Date": pd.to_datetime(["2026-10-01"]), "Close": [100.0]})
        with patch("run_daily_pipeline.active_raw_files", return_value=["AAA.NS.csv"]), \
                patch("run_daily_pipeline.load_stock", return_value=stock), \
                patch("run_daily_pipeline.get_live_price", return_value={
                    "dates": ["2026-09-29"], "current_price": 50.0,
                }):
            with self.assertRaisesRegex(RuntimeError, "held position BBB"):
                get_latest_prices("2026-10-01", ["BBB"])

    def test_drift_report_never_invents_a_backtest_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            paper = Path(directory) / "paper.json"
            paper.write_text(json.dumps({"equity_history": [
                {"date": f"day-{day}", "equity": 1000 + day} for day in range(31)
            ]}), encoding="utf-8")
            result = run_drift_analysis(str(paper), str(Path(directory) / "missing.csv"))
        self.assertEqual(result["status"], "NO_BACKTEST_BASELINE")


if __name__ == "__main__":
    unittest.main()
