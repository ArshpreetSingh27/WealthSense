import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import database


class ManualPortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_file = database.DB_FILE
        database.DB_FILE = os.path.join(cls.temp_dir.name, "test.db")
        cls.env_patch = patch.dict(os.environ, {"FLASK_SECRET_KEY": "test-only-secret-key"})
        cls.env_patch.start()
        from app import app
        cls.app = app
        cls.app.config.update(TESTING=True)
        database.init_db()
        database.create_user("alice@example.com", "password123")
        database.create_user("bob@example.com", "password123")

    @classmethod
    def tearDownClass(cls):
        cls.env_patch.stop()
        database.DB_FILE = cls.original_db_file
        cls.temp_dir.cleanup()

    def _client_for(self, email):
        client = self.app.test_client()
        client.environ_base["HTTP_X_REQUESTED_WITH"] = "XMLHttpRequest"
        with client.session_transaction() as session:
            session["user"] = email
        return client

    def test_portfolio_page_is_per_user(self):
        alice = self._client_for("alice@example.com")
        self.assertIn(b"Your <span class=\"italic\">Portfolio", alice.get("/portfolio").data)
        self.assertEqual(alice.get("/portfolio/manual").location, "/portfolio")
        self.assertEqual(self.app.test_client().get("/portfolio").status_code, 302)

    def test_stale_recommendations_are_not_served(self):
        from app import data_is_stale

        old_date = (datetime.now() - timedelta(days=30)).date().isoformat()
        self.assertTrue(data_is_stale(old_date))
        self.assertFalse(data_is_stale(datetime.now().date().isoformat()))
        path = os.path.join(self.temp_dir.name, "stale_recommendations.json")
        with open(path, "w", encoding="utf-8") as output:
            json.dump([{"Stock": "INFY", "Date": old_date, "Recommendation": "BUY"}], output)
        client = self._client_for("alice@example.com")
        with patch("app.LATEST_DATA_FILE", path):
            response = client.get("/api/recommendations")
        self.assertEqual(response.status_code, 503)

    def test_api_auth_and_manual_portfolio_validation(self):
        anonymous_response = self.app.test_client().get("/api/summary")
        self.assertEqual(anonymous_response.status_code, 401)
        self.assertEqual(anonymous_response.headers["Cache-Control"], "no-store")
        client = self._client_for("alice@example.com")
        self.assertEqual(client.get("/api/paper-trading").json["capital"], 1_000_000)
        self.assertEqual(client.post("/api/portfolio/add", json={"ticker": "INFY", "quantity": -1}).status_code, 400)
        self.assertEqual(client.post("/api/portfolio/add", json={"ticker": "INFY", "quantity": "bad"}).status_code, 400)
        self.assertEqual(self.app.test_client().post("/api/register", json={"email": "new@example.com", "password": "123"}).status_code, 400)
        self.assertEqual(self.app.test_client().post("/api/register", json=["bad"]).status_code, 400)

    def test_admin_role_requires_explicit_promotion(self):
        email = "admin@wealthsense.test"
        client = self.app.test_client()
        self.assertEqual(client.post("/api/register", json={"email": email, "password": "password123"}).status_code, 201)
        self.assertFalse(database.user_is_admin(email))
        client.post("/api/login", json={"email": email, "password": "password123"})
        self.assertEqual(client.get("/admin").status_code, 302)
        self.assertTrue(database.set_user_admin(email))
        client.post("/api/login", json={"email": email, "password": "password123"})
        self.assertEqual(client.get("/api/admin/data").status_code, 200)

    def test_manual_portfolio_reports_unpriced_holdings(self):
        database.add_to_portfolio("bob@example.com", "INFY", 2, 100)
        client = self._client_for("bob@example.com")
        with patch("app.get_live_price", side_effect=ValueError("provider unavailable")):
            data = client.get("/api/portfolio").json
        self.assertEqual(data["unpriced_holdings"], ["INFY"])
        self.assertTrue(data["summary"]["partial"])

    def test_directional_signal_does_not_invent_a_price_target(self):
        client = self._client_for("bob@example.com")
        market = {"current_price": 100.0, "dates": ["2026-09-29"], "prices": [100.0]}
        with patch("app.get_live_price", return_value=market):
            history = client.get("/api/stock/INFY")
            portfolio = client.get("/api/portfolio")
        self.assertIsNone(history.json["predicted_price"])
        self.assertIsNone(portfolio.json["summary"]["total_predicted"])
        self.assertTrue(all(item["predicted_price"] is None for item in portfolio.json["holdings"]))


if __name__ == "__main__":
    unittest.main()
