"""Isolated, long-only virtual trading accounts. No broker order calls."""

import math
import sqlite3
from contextlib import closing
from datetime import datetime, timezone

import database


STARTING_CASH = 1_000_000.0
MAX_POSITION_FRACTION = 0.20
EXECUTION_FRICTION = 0.0012


class PaperOrderError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


def _connect():
    connection = sqlite3.connect(database.DB_FILE, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def _ensure_account(connection, email):
    connection.execute(
        "INSERT OR IGNORE INTO paper_accounts(user_email, starting_cash, cash) VALUES (?, ?, ?)",
        (email, STARTING_CASH, STARTING_CASH),
    )


def get_account(email):
    email = email.lower().strip()
    with closing(_connect()) as connection:
        with connection:
            _ensure_account(connection, email)
        account = connection.execute(
            "SELECT starting_cash, cash, bot_enabled, created_at FROM paper_accounts WHERE user_email=?", (email,)
        ).fetchone()
        positions = connection.execute(
            "SELECT ticker, quantity, average_price FROM paper_positions WHERE user_email=? ORDER BY ticker", (email,)
        ).fetchall()
        trades = connection.execute(
            "SELECT client_order_id, ticker, side, quantity, price, notional, realized_pnl, source, market_date, executed_at "
            "FROM paper_trades WHERE user_email=? ORDER BY id DESC LIMIT 50", (email,)
        ).fetchall()
    return {
        "capital": account["starting_cash"], "cash": account["cash"],
        "bot_enabled": bool(account["bot_enabled"]),
        "created_at": account["created_at"],
        "positions": [dict(row) for row in positions],
        "trades": [dict(row) for row in trades],
    }


def set_bot_enabled(email, enabled):
    email = email.lower().strip()
    with closing(_connect()) as connection:
        with connection:
            _ensure_account(connection, email)
            connection.execute(
                "UPDATE paper_accounts SET bot_enabled=? WHERE user_email=?", (int(enabled), email)
            )


def enabled_accounts():
    with closing(_connect()) as connection:
        rows = connection.execute("SELECT user_email FROM paper_accounts WHERE bot_enabled=1").fetchall()
    return [row["user_email"] for row in rows]


def count_bot_buys(email, market_date):
    with closing(_connect()) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM paper_trades WHERE user_email=? AND market_date=? AND source='bot' AND side='BUY'",
            (email.lower().strip(), market_date),
        ).fetchone()[0]
    return count


def execute_order(email, ticker, side, quantity, market_price, market_date, client_order_id, source="manual"):
    """Fill a virtual order at latest available close with modeled friction."""
    email = email.lower().strip()
    if side not in {"BUY", "SELL"} or not isinstance(quantity, int) or isinstance(quantity, bool) or not 1 <= quantity <= 1_000_000:
        raise PaperOrderError("Side must be BUY or SELL and quantity must be a positive whole number.")
    if not math.isfinite(market_price) or market_price <= 0:
        raise PaperOrderError("A valid market price is required.")
    if source not in {"manual", "bot"}:
        raise PaperOrderError("Invalid paper order source.")
    execution_price = round(market_price * (1 + EXECUTION_FRICTION if side == "BUY" else 1 - EXECUTION_FRICTION), 4)
    notional = round(execution_price * quantity, 2)

    with closing(_connect()) as connection:
        try:
            connection.execute("BEGIN IMMEDIATE")
            _ensure_account(connection, email)
            existing = connection.execute(
                "SELECT ticker, side, quantity, price, notional, realized_pnl, source, market_date, executed_at "
                "FROM paper_trades WHERE user_email=? AND client_order_id=?", (email, client_order_id),
            ).fetchone()
            if existing:
                if (existing["ticker"], existing["side"], existing["quantity"]) != (ticker, side, quantity):
                    raise PaperOrderError("Order ID was already used for a different paper trade.", 409)
                connection.commit()
                return {"trade": dict(existing), "duplicate": True}

            account = connection.execute(
                "SELECT starting_cash, cash FROM paper_accounts WHERE user_email=?", (email,)
            ).fetchone()
            position = connection.execute(
                "SELECT quantity, average_price FROM paper_positions WHERE user_email=? AND ticker=?", (email, ticker),
            ).fetchone()
            realized_pnl = 0.0
            if side == "BUY":
                old_quantity = position["quantity"] if position else 0
                if (old_quantity + quantity) * market_price > account["starting_cash"] * MAX_POSITION_FRACTION:
                    raise PaperOrderError("Paper position would exceed 20% of starting capital.")
                if notional > account["cash"]:
                    raise PaperOrderError("Insufficient virtual cash.")
                new_quantity = old_quantity + quantity
                old_cost = old_quantity * position["average_price"] if position else 0
                average_price = (old_cost + notional) / new_quantity
                connection.execute(
                    "INSERT INTO paper_positions(user_email, ticker, quantity, average_price) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(user_email, ticker) DO UPDATE SET quantity=excluded.quantity, average_price=excluded.average_price",
                    (email, ticker, new_quantity, average_price),
                )
                new_cash = round(account["cash"] - notional, 2)
            else:
                if not position or quantity > position["quantity"]:
                    raise PaperOrderError("You cannot sell more than your paper holding.")
                realized_pnl = round((execution_price - position["average_price"]) * quantity, 2)
                remaining = position["quantity"] - quantity
                if remaining:
                    connection.execute(
                        "UPDATE paper_positions SET quantity=? WHERE user_email=? AND ticker=?",
                        (remaining, email, ticker),
                    )
                else:
                    connection.execute(
                        "DELETE FROM paper_positions WHERE user_email=? AND ticker=?", (email, ticker)
                    )
                new_cash = round(account["cash"] + notional, 2)
            connection.execute("UPDATE paper_accounts SET cash=? WHERE user_email=?", (new_cash, email))
            executed_at = datetime.now(timezone.utc).isoformat()
            connection.execute(
                "INSERT INTO paper_trades(user_email, client_order_id, ticker, side, quantity, price, notional, "
                "realized_pnl, source, market_date, executed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (email, client_order_id, ticker, side, quantity, execution_price, notional,
                 realized_pnl, source, market_date, executed_at),
            )
            connection.commit()
            return {"trade": {
                "ticker": ticker, "side": side, "quantity": quantity, "price": execution_price,
                "notional": notional, "realized_pnl": realized_pnl,
                "source": source,
                "market_date": market_date, "executed_at": executed_at,
            }, "duplicate": False}
        except Exception:
            connection.rollback()
            raise
