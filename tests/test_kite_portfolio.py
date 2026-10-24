import os
import tempfile
import unittest
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from unittest.mock import Mock

from cryptography.fernet import Fernet

import database


class KitePortfolioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.original_db_file = database.DB_FILE
        database.DB_FILE = os.path.join(cls.temp_dir.name, "test.db")
        cls.env_patch = patch.dict(os.environ, {
            "FLASK_SECRET_KEY": "test-only-secret-key",
            "KITE_API_KEY": "test-key",
            "KITE_API_SECRET": "test-secret",
            "KITE_TOKEN_ENCRYPTION_KEY": Fernet.generate_key().decode(),
            "KITE_ENV": "sandbox",
        })
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

    def test_connection_state_and_user_isolation(self):
        alice = self._client_for("alice@example.com")
        bob = self._client_for("bob@example.com")
        self.assertIn(b"Your <span class=\"italic\">Kite Portfolio", alice.get("/portfolio").data)
        self.assertEqual(self.app.test_client().get("/portfolio").status_code, 302)
        self.assertEqual(bob.get("/api/kite/portfolio").json["connected"], False)

        response = alice.get("/kite/connect")
        self.assertEqual(response.status_code, 302)
        self.assertIn("sandbox.kite.trade", response.location)
        with alice.session_transaction() as session:
            state = session["kite_connect_state"]

        invalid = alice.get("/kite/callback?state=wrong&status=success&request_token=one")
        self.assertEqual(invalid.status_code, 400)
        self.assertIsNone(database.get_kite_connection("alice@example.com"))

        alice.get("/kite/connect")
        with alice.session_transaction() as session:
            state = session["kite_connect_state"]
        with patch("kite_routes.exchange_request_token", return_value={"user_id": "ZA1234", "access_token": "alice-token"}):
            self.assertEqual(alice.get(f"/kite/callback?state={state}&status=success&request_token=one").status_code, 302)

        saved = database.get_kite_connection("alice@example.com")
        self.assertNotIn(b"alice-token", saved["access_token_encrypted"])
        self.assertIsNone(database.get_kite_connection("bob@example.com"))
        self.assertEqual(bob.get("/api/kite/portfolio").json["connected"], False)

        portfolio = {"holdings": [{"tradingsymbol": "INFY", "quantity": 2}], "positions": [], "funds": {}, "orders": [], "fetched_at": "2026-09-29T00:00:00+00:00"}
        with patch("kite_routes.fetch_portfolio", return_value=portfolio) as fetch:
            result = alice.get("/api/kite/portfolio")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json["broker_user_id"], "ZA1234")
        self.assertEqual(result.json["holdings"][0]["tradingsymbol"], "INFY")
        fetch.assert_called_once_with("alice-token")

    def test_expired_connection_requires_reconnect(self):
        old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        database.save_kite_connection("alice@example.com", "ZA1234", b"unused", old)
        alice = self._client_for("alice@example.com")
        with patch("kite_routes.fetch_portfolio") as fetch:
            result = alice.get("/api/kite/portfolio")
        self.assertEqual(result.json, {"connected": False, "reconnect_required": True})
        fetch.assert_not_called()

    def test_disconnect_revokes_only_current_users_kite_session(self):
        from kite_integration import encrypt_token
        database.save_kite_connection(
            "bob@example.com", "ZB5678", encrypt_token("bob-token"),
            datetime.now(timezone.utc).isoformat(),
        )
        bob = self._client_for("bob@example.com")
        self.assertEqual(bob.post("/api/kite/disconnect", headers={"X-Requested-With": ""}).status_code, 403)
        with patch("kite_routes.invalidate_token") as revoke:
            response = bob.post("/api/kite/disconnect", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"disconnected": True, "broker_session_revoked": True})
        revoke.assert_called_once_with("bob-token")
        self.assertIsNone(database.get_kite_connection("bob@example.com"))
        self.assertIsNotNone(database.get_kite_connection("alice@example.com"))

    def test_callback_cannot_cross_users(self):
        client = self._client_for("alice@example.com")
        client.get("/kite/connect")
        with client.session_transaction() as session:
            state = session["kite_connect_state"]
            session["user"] = "bob@example.com"
        with patch("kite_routes.exchange_request_token") as exchange:
            response = client.get(f"/kite/callback?state={state}&status=success&request_token=one")
        self.assertEqual(response.status_code, 400)
        exchange.assert_not_called()

    def test_invalid_kite_response_is_handled(self):
        from kite_integration import KiteAPIError, fetch_portfolio, session_is_current
        self.assertFalse(session_is_current("broken-timestamp"))
        reply = Mock(status_code=200, ok=True)
        reply.json.return_value = {"status": "success"}
        with patch("kite_integration.requests.request", return_value=reply):
            with self.assertRaises(KiteAPIError):
                fetch_portfolio("user-token")

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

    def test_kite_client_reads_broker_endpoints(self):
        from kite_integration import fetch_portfolio
        bodies = [
            [{"tradingsymbol": "INFY", "quantity": 2}],
            {"net": [{"tradingsymbol": "NIFTY", "quantity": 1}], "day": []},
            {"equity": {"available": {"cash": 1000}}},
            [{"order_id": "one", "status": "COMPLETE"}],
        ]
        replies = []
        for body in bodies:
            reply = Mock(status_code=200, ok=True)
            reply.json.return_value = {"status": "success", "data": body}
            replies.append(reply)
        with patch("kite_integration.requests.request", side_effect=replies) as request:
            result = fetch_portfolio("user-token")
        self.assertEqual(result["positions"][0]["tradingsymbol"], "NIFTY")
        self.assertEqual(result["funds"]["equity"]["available"]["cash"], 1000)
        self.assertEqual(request.call_count, 4)
        self.assertIn("/portfolio/holdings", request.call_args_list[0].args[1])
        self.assertEqual(request.call_args_list[0].kwargs["headers"]["Authorization"], "token test-key:user-token")


if __name__ == "__main__":
    unittest.main()
