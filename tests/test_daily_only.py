import unittest
from unittest.mock import patch

from app import app


class DailyOnlyDashboardTests(unittest.TestCase):
    def test_dashboard_does_not_offer_intraday_predictions(self):
        with app.test_client() as client, patch("app.user_exists", return_value=True):
            with client.session_transaction() as session:
                session["user"] = "reader@example.com"

            page = client.get("/")
            self.assertEqual(page.status_code, 200)
            self.assertNotIn(b"INTRADAY SCALPS", page.data)
            self.assertNotIn(b'id="modeIntraday"', page.data)

            for path in (
                "/api/recommendations?mode=intraday",
                "/api/summary?mode=intraday",
                "/api/stock/INFY?mode=intraday",
                "/api/live/INFY?mode=intraday",
            ):
                with self.subTest(path=path):
                    self.assertEqual(client.get(path).status_code, 400)


if __name__ == "__main__":
    unittest.main()
