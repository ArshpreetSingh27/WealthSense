"""Opt-in per-user bot that can only submit virtual paper orders."""

import json
import math
import os
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

import paper_accounts
from data.scripts.load_and_plot import load_stock


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECOMMENDATIONS_FILE = os.path.join(BASE_DIR, "data", "processed", "latest_recommendations.json")
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
MAX_OPEN_POSITIONS = 10
MAX_NEW_BUYS = 3
BUY_BUDGET_FRACTION = 0.05


def _recommendations():
    with open(RECOMMENDATIONS_FILE, encoding="utf-8") as source:
        rows = json.load(source)
    if not isinstance(rows, list) or not rows:
        raise ValueError("No daily recommendations are available for the paper bot.")
    market_date = max(str(row.get("Date", ""))[:10] for row in rows)
    market_day = datetime.fromisoformat(market_date).date()
    age = (datetime.now(ZoneInfo("Asia/Kolkata")).date() - market_day).days
    if not 0 <= age <= 7:
        raise ValueError("Paper bot recommendations are stale.")
    current_rows = [row for row in rows if str(row.get("Date", ""))[:10] == market_date]
    return market_date, current_rows


def _quote(ticker, market_date):
    df = load_stock(os.path.join(RAW_DIR, f"{ticker}.NS.csv"))
    if df.empty or df["Date"].iloc[-1].date().isoformat() != market_date:
        raise ValueError(f"Current market data is missing for {ticker}.")
    price = float(df["Close"].iloc[-1])
    if not math.isfinite(price) or price <= 0:
        raise ValueError(f"Invalid market price for {ticker}.")
    return price


def run_for_user(email, recommendations=None):
    account = paper_accounts.get_account(email)
    if not account["bot_enabled"]:
        return {"market_date": None, "buys": 0, "sells": 0, "skipped": "disabled"}
    market_date, rows = recommendations or _recommendations()
    by_ticker = {row["Stock"]: row for row in rows}
    open_positions = {position["ticker"]: position for position in account["positions"]}
    buys = sells = 0

    for ticker, position in open_positions.items():
        if by_ticker.get(ticker, {}).get("Recommendation") != "SELL":
            continue
        price = _quote(ticker, market_date)
        order_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"paper-bot:{email}:{market_date}:{ticker}:SELL"))
        result = paper_accounts.execute_order(
            email, ticker, "SELL", position["quantity"], price, market_date, order_id, source="bot"
        )
        sells += not result["duplicate"]

    account = paper_accounts.get_account(email)
    held = {position["ticker"] for position in account["positions"]}
    remaining_buy_slots = max(0, MAX_NEW_BUYS - paper_accounts.count_bot_buys(email, market_date))
    used_buy_slots = 0
    candidates = sorted(
        (row for row in rows if row.get("Recommendation") == "BUY" and row.get("Stock") not in held),
        key=lambda row: float(row.get("Prob_Up", 0)), reverse=True,
    )
    for row in candidates:
        if used_buy_slots >= remaining_buy_slots or len(held) >= MAX_OPEN_POSITIONS:
            break
        ticker = row["Stock"]
        price = _quote(ticker, market_date)
        quantity = math.floor(
            account["capital"] * BUY_BUDGET_FRACTION /
            (price * (1 + paper_accounts.EXECUTION_FRICTION))
        )
        if quantity < 1:
            continue
        order_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"paper-bot:{email}:{market_date}:{ticker}:BUY"))
        try:
            result = paper_accounts.execute_order(
                email, ticker, "BUY", quantity, price, market_date, order_id, source="bot"
            )
        except paper_accounts.PaperOrderError:
            continue
        used_buy_slots += 1
        buys += not result["duplicate"]
        held.add(ticker)
    return {"market_date": market_date, "buys": buys, "sells": sells}


def run_all_enabled():
    if not paper_accounts.enabled_accounts():
        return []
    recommendations = _recommendations()
    results = []
    failures = []
    for email in paper_accounts.enabled_accounts():
        try:
            results.append({"user": email, **run_for_user(email, recommendations)})
        except Exception as exc:
            failures.append(f"{email}: {exc}")
    if failures:
        raise RuntimeError("Paper bot failed for: " + "; ".join(failures))
    return results
