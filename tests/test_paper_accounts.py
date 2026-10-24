import os
import tempfile
import unittest
import uuid
from unittest.mock import patch

import database


class MultiUserPaperTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.original_db = database.DB_FILE
        database.DB_FILE = os.path.join(self.directory.name, "paper.db")
        database.init_db()
        database.create_user("alice@example.com", "password123")
        database.create_user("bob@example.com", "password123")
        from app import app
        self.app = app
        self.alice = self._client("alice@example.com")
        self.bob = self._client("bob@example.com")

    def tearDown(self):
        database.DB_FILE = self.original_db
        self.directory.cleanup()

    def _client(self, email):
        client = self.app.test_client()
        client.environ_base["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        with client.session_transaction() as session:
            session["user"] = email
        return client

    def _order(self, client, side, quantity, order_id=None):
        return client.post("/api/paper-trading/orders", json={
            "ticker": "INFY", "side": side, "quantity": quantity,
            "client_order_id": order_id or str(uuid.uuid4()),
        })

    def test_user_balances_positions_and_orders_are_isolated(self):
        with patch("app.paper_quote", return_value=(100.0, "2026-10-01")), \
                patch("kite_integration._request") as broker_request:
            order_id = str(uuid.uuid4())
            buy = self._order(self.alice, "BUY", 10, order_id)
            self.assertEqual(buy.status_code, 201)
            self.assertAlmostEqual(buy.json["trade"]["price"], 100.12)
            repeated = self._order(self.alice, "BUY", 10, order_id)
            self.assertEqual(repeated.status_code, 200)
            self.assertTrue(repeated.json["duplicate"])
            alice = self.alice.get("/api/paper-trading").json
            bob = self.bob.get("/api/paper-trading").json
            self.assertEqual(alice["positions"][0]["quantity"], 10)
            self.assertEqual(len(alice["trades"]), 1)
            self.assertEqual(bob["positions"], [])
            self.assertEqual(bob["trades"], [])
            self.assertEqual(bob["cash"], 1_000_000)
            self.assertEqual(self._order(self.bob, "SELL", 1).status_code, 400)
            sell = self._order(self.alice, "SELL", 5)
            self.assertEqual(sell.status_code, 201)
            self.assertEqual(self.alice.get("/api/paper-trading").json["positions"][0]["quantity"], 5)
            broker_request.assert_not_called()

    def test_risk_limits_and_quote_failure_do_not_create_trades(self):
        with patch("app.paper_quote", return_value=(100.0, "2026-10-01")):
            self.assertEqual(self._order(self.alice, "BUY", 2001).status_code, 400)
            self.assertEqual(self._order(self.alice, "BUY", 0).status_code, 400)
        with patch("app.paper_quote", side_effect=ValueError("stale")):
            self.assertEqual(self._order(self.alice, "BUY", 1).status_code, 503)
        self.assertEqual(self.alice.get("/api/paper-trading").json["trades"], [])

    def test_paper_account_is_deleted_with_user(self):
        with patch("app.paper_quote", return_value=(100.0, "2026-10-01")):
            self._order(self.alice, "BUY", 1)
        database.delete_user_account("alice@example.com")
        self.assertEqual(self.alice.get("/api/paper-trading").status_code, 401)
        import sqlite3
        from contextlib import closing
        with closing(sqlite3.connect(database.DB_FILE)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_accounts").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM paper_trades").fetchone()[0], 0)

    def test_opted_in_bot_trades_only_in_own_virtual_account_once_per_day(self):
        toggle = self.alice.post("/api/paper-trading/bot", json={"enabled": True})
        self.assertEqual(toggle.status_code, 200)
        recommendations = ("2026-10-01", [
            {"Stock": "INFY", "Recommendation": "BUY", "Prob_Up": 0.8},
            {"Stock": "SBIN", "Recommendation": "BUY", "Prob_Up": 0.7},
            {"Stock": "TCS", "Recommendation": "BUY", "Prob_Up": 0.6},
            {"Stock": "HDFCBANK", "Recommendation": "BUY", "Prob_Up": 0.5},
        ])
        with patch("paper_bot._recommendations", return_value=recommendations), \
                patch("paper_bot._quote", return_value=100.0), \
                patch("app.paper_quote", return_value=(100.0, "2026-10-01")), \
                patch("kite_integration._request") as broker_request:
            first = self.alice.post("/api/paper-trading/bot/run")
            second = self.alice.post("/api/paper-trading/bot/run")
            self.assertEqual(first.json["buys"], 3)
            self.assertEqual(second.json["buys"], 0)
            self.assertEqual(len(self.alice.get("/api/paper-trading").json["trades"]), 3)
            self.assertEqual(self.bob.get("/api/paper-trading").json["trades"], [])
            broker_request.assert_not_called()

    def test_bot_is_off_by_default_and_dashboard_is_available_to_regular_user(self):
        page = self.alice.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b'paperOrderForm', page.data)
        result = self.alice.post("/api/paper-trading/bot/run")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["skipped"], "disabled")
        self.assertEqual(self.alice.get("/api/paper-trading").json["trades"], [])


if __name__ == "__main__":
    unittest.main()
