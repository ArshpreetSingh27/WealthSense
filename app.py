import os
import requests
from datetime import date
from datetime import datetime
import math
import re
import uuid
from zoneinfo import ZoneInfo
from flask import Flask, jsonify, render_template, request, redirect, json, url_for, session
import pandas as pd
from dotenv import load_dotenv
from database import init_db, create_user, authenticate_user, user_exists, user_is_admin, add_to_portfolio, remove_from_portfolio, get_user_portfolio
from realtime import get_live_price, get_news_headlines, get_sentiment, get_indices_data
from paper_accounts import (
    PaperOrderError, execute_order as execute_paper_order,
    get_account as get_paper_account, set_bot_enabled,
)
from paper_bot import run_for_user as run_paper_bot_for_user
from data.scripts.universe import TICKERS
from data.scripts.load_and_plot import load_stock

load_dotenv()
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("APP_HTTPS") == "1",
)
print("Initializing configuration...")

@app.before_request
def require_login_for_api():
    if "user" in session and not user_exists(session["user"]):
        session.clear()
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect(url_for("login_page"))
    if request.path.startswith("/api/") and request.endpoint not in {"register", "login_api"} and "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if (request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"}
            and request.endpoint not in {"register", "login_api"}
            and request.headers.get("X-Requested-With") != "XMLHttpRequest"):
        return jsonify({"error": "Invalid request."}), 403


@app.after_request
def prevent_account_data_caching(response):
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
    return response

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LATEST_DATA_FILE = os.path.join(BASE_DIR, "data", "processed", "latest_recommendations.json")
LATEST_INTRADAY_DATA_FILE = os.path.join(BASE_DIR, "data", "processed", "latest_recommendations_intraday.json")

def data_is_stale(value, max_age_days=7):
    try:
        source_date = date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return True
    age = (date.today() - source_date).days
    return age < 0 or age > max_age_days

# Ensure DB is initialized
init_db()
print("Database initialized.")

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY")
PAPER_TICKERS = {ticker.removesuffix(".NS") for ticker in TICKERS}


def paper_quote(ticker):
    path = os.path.join(BASE_DIR, "data", "raw", f"{ticker}.NS.csv")
    history = load_stock(path)
    if history.empty:
        raise ValueError("No NSE closing price is available for this paper order.")
    price = float(history["Close"].iloc[-1])
    market_day = history["Date"].iloc[-1].date()
    age = (datetime.now(ZoneInfo("Asia/Kolkata")).date() - market_day).days
    if not math.isfinite(price) or price <= 0 or not 0 <= age <= 7:
        raise ValueError("No recent NSE quote is available for this paper order.")
    return price, market_day.isoformat()

# ================================
# ROUTES
# ================================

@app.route("/login")
def login_page():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("index.html")

@app.route("/portfolio")
def portfolio():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return render_template("portfolio.html")

@app.route("/portfolio/manual")
def manual_portfolio():
    if "user" not in session:
        return redirect(url_for("login_page"))
    return redirect(url_for("portfolio"))


# ================================
# AUTH API ENDPOINTS
# ================================

@app.route("/api/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True)
    data = payload if isinstance(payload, dict) else {}
    raw_email = data.get("email")
    email = raw_email.lower().strip() if isinstance(raw_email, str) else ""
    password = data.get("password")
    
    if not re.fullmatch(r"[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}", email) or not isinstance(password, str) or len(password) < 8:
        return jsonify({"error": "Valid email and password of at least 8 characters are required."}), 400
        
    success, message = create_user(email, password)
    if success:
        return jsonify({"message": message}), 201
    else:
        return jsonify({"error": message}), 400

@app.route("/api/login", methods=["POST"])
def login_api():
    payload = request.get_json(silent=True)
    data = payload if isinstance(payload, dict) else {}
    raw_email = data.get("email")
    email = raw_email.lower().strip() if isinstance(raw_email, str) else ""
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
        
    if authenticate_user(email, password):
        session.clear()
        session["user"] = email
        session["is_admin"] = user_is_admin(email)
        return jsonify({"message": "Login successful", "email": email}), 200
    else:
        return jsonify({"error": "Invalid email or password."}), 401
        
@app.route("/api/logout", methods=["POST"])
def logout_api():
    session.clear()
    return jsonify({"message": "Logged out successfully"}), 200

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_page"))

# ================================
# ADMIN ENDPOINTS
# ================================

@app.route("/admin")
def admin_page():
    if not user_is_admin(session.get("user")):
        return redirect("/login")
    return render_template("admin.html")

@app.route("/api/paper-trading", methods=["GET"])
def get_paper_trading_api():
    account = get_paper_account(session["user"])
    equity = account["cash"]
    unpriced = []
    for position in account["positions"]:
        try:
            price, market_date = paper_quote(position["ticker"])
            position["current_price"] = price
            position["market_date"] = market_date
            position["current_value"] = round(position["quantity"] * price, 2)
            position["unrealized_pnl"] = round(position["quantity"] * (price - position["average_price"]), 2)
            equity += position["current_value"]
        except Exception:
            position["current_price"] = None
            position["current_value"] = None
            position["unrealized_pnl"] = None
            unpriced.append(position["ticker"])
    account["equity"] = round(equity, 2) if not unpriced else None
    account["unpriced_positions"] = unpriced
    account["partial"] = bool(unpriced)
    return jsonify(account)


@app.route("/api/paper-trading/orders", methods=["POST"])
def place_paper_order():
    payload = request.get_json(silent=True)
    data = payload if isinstance(payload, dict) else {}
    ticker = str(data.get("ticker", "")).strip().upper().removesuffix(".NS")
    side = str(data.get("side", "")).strip().upper()
    quantity = data.get("quantity")
    try:
        client_order_id = str(uuid.UUID(str(data.get("client_order_id", ""))))
    except ValueError:
        return jsonify({"error": "A valid order ID is required."}), 400
    if ticker not in PAPER_TICKERS:
        return jsonify({"error": "Choose a stock from the active NSE paper-trading universe."}), 400
    if side not in {"BUY", "SELL"} or type(quantity) is not int or not 1 <= quantity <= 1_000_000:
        return jsonify({"error": "Side must be BUY or SELL and quantity must be a positive whole number."}), 400
    try:
        price, market_date = paper_quote(ticker)
    except Exception:
        return jsonify({"error": "A recent NSE market quote is unavailable. Try again later."}), 503
    try:
        result = execute_paper_order(session["user"], ticker, side, quantity, price, market_date, client_order_id)
    except PaperOrderError as exc:
        return jsonify({"error": str(exc)}), exc.status_code
    return jsonify(result), 200 if result["duplicate"] else 201


@app.route("/api/paper-trading/bot", methods=["POST"])
def configure_paper_bot():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or type(payload.get("enabled")) is not bool:
        return jsonify({"error": "enabled must be true or false."}), 400
    set_bot_enabled(session["user"], payload["enabled"])
    return jsonify({"bot_enabled": payload["enabled"]})


@app.route("/api/paper-trading/bot/run", methods=["POST"])
def run_paper_bot_api():
    try:
        return jsonify(run_paper_bot_for_user(session["user"]))
    except (ValueError, RuntimeError, OSError) as exc:
        return jsonify({"error": str(exc)}), 503

@app.route("/api/admin/data")
def admin_data():
    if not user_is_admin(session.get("user")):
        return jsonify({"error": "Unauthorized"}), 401
    
    from database import get_all_users_summary
    data = get_all_users_summary()
    return jsonify(data)

@app.route("/api/admin/delete_user", methods=["POST"])
def admin_delete_user():
    if not user_is_admin(session.get("user")):
        return jsonify({"error": "Unauthorized"}), 401
    
    payload = request.get_json(silent=True)
    email = payload.get("email") if isinstance(payload, dict) else None
    if not isinstance(email, str) or not email:
        return jsonify({"error": "Email is required"}), 400
        
    if user_is_admin(email):
        return jsonify({"error": "Cannot delete an administrator account"}), 400
        
    from database import delete_user_account
    success, message = delete_user_account(email)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400

# ================================
# DATA API ENDPOINTS
# ================================

@app.route("/api/recommendations", methods=["GET"])
def get_recommendations():
    mode = request.args.get("mode", "daily")
    data_file = LATEST_INTRADAY_DATA_FILE if mode == "intraday" else LATEST_DATA_FILE
    
    if not os.path.exists(data_file):
        return jsonify({"error": f"No {mode} recommendation data available."}), 404
        
    try:
        df = pd.read_json(data_file)
        if df.empty or data_is_stale(df["Date"].max()):
            return jsonify({"error": "Recommendation data is stale. Run the market pipeline."}), 503
        data = df.to_dict(orient="records")
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/trading-alpha", methods=["GET"])
def get_trading_alpha():
    try:
        signals_file = os.path.join(BASE_DIR, "data", "latest_trading_signals.json")
        with open(signals_file, "r") as f:
            data = json.load(f)
        if data_is_stale(data.get("market_date", data.get("timestamp"))):
            return jsonify({"error": "Trading signals are stale. Run the market pipeline."}), 503
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/summary", methods=["GET"])
def get_summary():
    mode = request.args.get("mode", "daily")
    data_file = LATEST_INTRADAY_DATA_FILE if mode == "intraday" else LATEST_DATA_FILE
    
    if not os.path.exists(data_file):
        return jsonify({"error": "No data."}), 404
        
    df = pd.read_json(data_file)
    latest_date = df["Date"].max() if not df.empty else None
    summary = {
        "total_stocks": len(df),
        "buy_signals": len(df[df['Recommendation'] == 'BUY']),
        "sell_signals": len(df[df['Recommendation'] == 'SELL']),
        "hold_signals": len(df[df['Recommendation'] == 'HOLD']),
        "latest_date": str(latest_date)[:16] if latest_date is not None else "N/A",
        "stale": data_is_stale(latest_date)
    }
    return jsonify(summary)

@app.route("/api/indices", methods=["GET"])
def get_indices():
    """
    Fetches real-time global index data.
    """
    try:
        indices = get_indices_data()
        return jsonify(indices), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================================
# PORTFOLIO API ENDPOINTS
# ================================

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    email = session["user"]
    holdings = get_user_portfolio(email)
    
    portfolio_data = []
    unpriced_holdings = []
    total_invested = 0
    total_current = 0
    
    for item in holdings:
        ticker = item["ticker"]
        qty = item["quantity"]
        purchase_price = item["purchase_price"]
        
        try:
            # 1. Get live data
            price_data = get_live_price(ticker)
            current_price = price_data["current_price"]
            
            # 2. Get the directional model signal. It does not predict a price.
            recommendation = "HOLD"
            
            if os.path.exists(LATEST_DATA_FILE):
                latest_df = pd.read_json(LATEST_DATA_FILE)
                stock_match = latest_df[latest_df['Stock'] == ticker.upper()] if not latest_df.empty and not data_is_stale(latest_df["Date"].max()) else pd.DataFrame()
                if not stock_match.empty:
                    recommendation = stock_match.iloc[0]['Recommendation']

            # 3. Calculations
            cost_basis = qty * purchase_price
            current_val = qty * current_price
            p_l = current_val - cost_basis
            p_l_pct = (p_l / cost_basis * 100) if cost_basis != 0 else 0
            
            total_invested += cost_basis
            total_current += current_val

            portfolio_data.append({
                "ticker": ticker,
                "quantity": qty,
                "purchase_price": purchase_price,
                "current_price": current_price,
                "predicted_price": None,
                "cost_basis": round(cost_basis, 2),
                "current_value": round(current_val, 2),
                "predicted_value": None,
                "p_l": round(p_l, 2),
                "p_l_pct": round(p_l_pct, 2),
                "recommendation": recommendation
            })
        except Exception:
            unpriced_holdings.append(ticker)
            
    return jsonify({
        "holdings": portfolio_data,
        "unpriced_holdings": unpriced_holdings,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "total_predicted": None,
            "total_p_l": round(total_current - total_invested, 2),
            "total_p_l_pct": round(((total_current - total_invested) / total_invested * 100) if total_invested != 0 else 0, 2),
            "partial": bool(unpriced_holdings)
        }
    })

@app.route("/api/portfolio/add", methods=["POST"])
def add_portfolio_item():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    payload = request.get_json(silent=True)
    data = payload if isinstance(payload, dict) else {}
    ticker = str(data.get("ticker", "")).strip().upper()
    try:
        quantity = float(data.get("quantity", 1))
        purchase_price = float(data.get("purchase_price", 0))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity and purchase price must be numbers."}), 400
    
    if not re.fullmatch(r"[A-Z0-9.-]{1,20}", ticker):
        return jsonify({"error": "A valid ticker is required."}), 400
    if not math.isfinite(quantity) or quantity <= 0 or not math.isfinite(purchase_price) or purchase_price < 0:
        return jsonify({"error": "Quantity must be positive and purchase price cannot be negative."}), 400
        
    email = session["user"]
    success, message = add_to_portfolio(email, ticker, quantity, purchase_price)
    if success:
        return jsonify({"message": message}), 201
    else:
        return jsonify({"error": message}), 400

@app.route("/api/portfolio/remove/<ticker>", methods=["DELETE"])
def remove_portfolio_item(ticker):
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    email = session["user"]
    success, message = remove_from_portfolio(email, ticker)
    if success:
        return jsonify({"message": message}), 200
    else:
        return jsonify({"error": message}), 400

@app.route("/api/stock/<ticker>", methods=["GET"])
def get_stock_history(ticker):
    """
    Returns historical close prices for the chart.
    """
    mode = request.args.get("mode", "daily")
    interval = "5m" if mode == "intraday" else "1d"
    period = "5d" if mode == "intraday" else "35d"
    try:
        # Get data from realtime module
        price_data = get_live_price(ticker, period=period, interval=interval)
        dates = price_data["dates"]
        prices = price_data["prices"]
        current_value = price_data["current_price"]
            
        return jsonify({
            "ticker": ticker,
            "dates": dates,
            "prices": prices,
            "current_price": current_value,
            "predicted_price": None
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news/<ticker>", methods=["GET"])
def get_news(ticker):
    """
    Fetches the latest relative financial news items using the Polygon.io API.
    """
    if not POLYGON_API_KEY:
        return jsonify({"error": "News provider is not configured."}), 503
    try:
        url = f"https://api.polygon.io/v2/reference/news?ticker={ticker.upper()}&limit=4&apiKey={POLYGON_API_KEY}"
        res = requests.get(url)
        if res.status_code != 200:
            return jsonify({"error": "Failed to fetch news from provider."}), res.status_code
        data = res.json()
        articles = []
        for result in data.get("results", []):
            articles.append({
                "title": result.get("title"),
                "publisher": result.get("publisher", {}).get("name", "Unknown"),
                "article_url": result.get("article_url"),
                "published_utc": result.get("published_utc"),
                "image_url": result.get("image_url")
            })
            
        return jsonify(articles), 200
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/live/<ticker>", methods=["GET"])
def get_live_data(ticker):
    """
    Combined real-time endpoint.
    """
    mode = request.args.get("mode", "daily")
    interval = "5m" if mode == "intraday" else "1d"
    period = "5d" if mode == "intraday" else "35d"
    data_file = LATEST_INTRADAY_DATA_FILE if mode == "intraday" else LATEST_DATA_FILE

    try:
        # 1. Live price & history
        price_data = get_live_price(ticker, period=period, interval=interval)
        current_price = price_data["current_price"]

        # 2. Match with model recommendations
        recommendation = "HOLD"
        if os.path.exists(data_file):
            latest_df = pd.read_json(data_file)
            stock_match = latest_df[latest_df['Stock'] == ticker.upper()] if not latest_df.empty and not data_is_stale(latest_df["Date"].max()) else pd.DataFrame()
            if not stock_match.empty:
                recommendation = stock_match.iloc[0]['Recommendation']

        # 3. News & Sentiment
        headlines = get_news_headlines(ticker)
        sentiment = get_sentiment(headlines)

        suggestion = recommendation 

        return jsonify({
            "ticker": ticker.upper(),
            "current_price": current_price,
            "predicted_price": None,
            "suggestion": suggestion, 
            "sentiment_label": sentiment["label"],
            "sentiment_score": sentiment["score"],
            "headlines": headlines,
            "price_history": {
                "dates": price_data["dates"],
                "prices": price_data["prices"]
            }
        }), 200

    except Exception as e:
        return jsonify({"error": f"Failed to fetch live data: {str(e)}"}), 500

if __name__ == "__main__":
    try:
        port = int(os.environ.get("APP_PORT", "5050"))
        print(f"Starting WEALTH sense on http://127.0.0.1:{port}/ ...")
        app.run(host="127.0.0.1", debug=os.environ.get("FLASK_DEBUG") == "1", port=port)
    except Exception as e:
        print(f"CRITICAL ERROR DURING STARTUP: {e}")
        import traceback
        traceback.print_exc()
