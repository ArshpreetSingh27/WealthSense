import unittest
from unittest.mock import patch

import pandas as pd

from realtime import get_live_price


class NseQuoteTests(unittest.TestCase):
    def test_unqualified_nse_symbol_cannot_resolve_to_us_adr(self):
        history = pd.DataFrame(
            {"Close": [1035.0]}, index=pd.to_datetime(["2026-10-01"])
        )
        with patch("realtime.yf.Ticker") as ticker:
            ticker.return_value.history.return_value = history
            quote = get_live_price("INFY")
        ticker.assert_called_once_with("INFY.NS")
        self.assertEqual(quote["current_price"], 1035.0)


if __name__ == "__main__":
    unittest.main()
