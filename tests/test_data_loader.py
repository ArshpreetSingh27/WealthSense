import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "data" / "scripts"))
from load_and_plot import load_stock


class DataLoaderTests(unittest.TestCase):
    def test_project_yahoo_csv_keeps_real_dates_and_close(self):
        csv = (
            "Price,Adj Close,Close,High,Low,Open,Volume\n"
            "Ticker,INFY.NS,INFY.NS,INFY.NS,INFY.NS,INFY.NS,INFY.NS\n"
            "Date,,,,,,\n"
            "2026-09-28 00:00:00,99,100,102,98,99,1000\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "INFY.NS.csv"
            path.write_text(csv, encoding="utf-8")
            data = load_stock(path)
        self.assertEqual(data.loc[0, "Date"].strftime("%Y-%m-%d"), "2026-09-28")
        self.assertEqual(data.loc[0, "Close"], 100)
        self.assertEqual(data.loc[0, "Volume"], 1000)

    def test_plain_csv_is_supported(self):
        csv = "Date,Close,High,Low,Open,Volume\n2026-09-28,100,102,98,99,1000\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stock.csv"
            path.write_text(csv, encoding="utf-8")
            data = load_stock(path)
        self.assertEqual(data.loc[0, "Date"].year, 2026)
        self.assertEqual(data.loc[0, "Close"], 100)


if __name__ == "__main__":
    unittest.main()
