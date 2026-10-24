import os
import sqlite3
import tempfile
import unittest
from datetime import date
from unittest.mock import patch

import database


class VercelDeploymentTests(unittest.TestCase):
    def test_hosted_storage_uses_remote_driver_and_preserves_paper_accounts(self):
        import turso_serverless
        from paper_accounts import execute_order, get_account

        with tempfile.TemporaryDirectory() as directory:
            remote_file = os.path.join(directory, "remote.db")
            original_file = database.DB_FILE
            database.DB_FILE = os.path.join(directory, "unused-local.db")
            try:
                with patch.dict(os.environ, {
                    "VERCEL": "1",
                    "TURSO_DATABASE_URL": "libsql://example.turso.io",
                    "TURSO_AUTH_TOKEN": "test-token",
                }), patch.object(turso_serverless, "connect", side_effect=lambda *args, **kwargs: sqlite3.connect(remote_file)) as remote:
                    database.init_db()
                    self.assertTrue(database.create_user("alice@example.com", "password123")[0])
                    result = execute_order(
                        "alice@example.com", "INFY", "BUY", 2, 100, "2026-10-24", "order-1"
                    )
                    self.assertFalse(result["duplicate"])
                    self.assertEqual(get_account("alice@example.com")["positions"][0]["quantity"], 2)
                    self.assertTrue(remote.called)
                    self.assertFalse(os.path.exists(database.DB_FILE))
            finally:
                database.DB_FILE = original_file

    def test_vercel_refuses_ephemeral_local_database(self):
        with patch.dict(os.environ, {"VERCEL": "1", "TURSO_DATABASE_URL": ""}):
            with self.assertRaisesRegex(RuntimeError, "Turso database is required"):
                database.connect()

    def test_paper_quote_uses_recent_live_nse_price_without_csv(self):
        from app import paper_quote

        today = date.today().isoformat()
        with patch("app.os.path.exists", return_value=False), patch(
            "app.get_live_price", return_value={"current_price": 123.45, "dates": [today]}
        ) as live:
            self.assertEqual(paper_quote("INFY"), (123.45, today))
            live.assert_called_once_with("INFY", period="10d")


if __name__ == "__main__":
    unittest.main()
