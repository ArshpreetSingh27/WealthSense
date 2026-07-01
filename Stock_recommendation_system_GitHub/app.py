import os
import random
import requests
from flask import Flask, jsonify, render_template, request, redirect, json, url_for, session
from flask_cors import CORS
import pandas as pd
from database import init_db, create_user, authenticate_user, add_to_portfolio, remove_from_portfolio, get_user_portfolio
from realtime import get_live_price, get_news_headlines, get_sentiment, get_indices_data

app = Flask(__name__)
CORS(app)
# Required for session management (this should be randomly generated and secret in production)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "master_predictor_super_secret_key")
print("Initializing configuration...")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LATEST_DATA_FILE = os.path.join(BASE_DIR, "data", "processed", "latest_recommendations.json")
LATEST_INTRADAY_DATA_FILE = os.path.join(BASE_DIR, "data", "processed", "latest_recommendations_intraday.json")

# Ensure DB is initialized
init_db()
print("Database initialized.")

POLYGON_API_KEY = os.environ.get("POLYGON_API_KEY", "tfxcnwHfXp4_XP074LZoDt8CQoWRcu73")

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


# ================================
# AUTH API ENDPOINTS
# ================================

@app.route("/api/register", methods=["POST"])
def register():
    data = request.json
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
        
    success, message = create_user(email, password)
    if success:
        return jsonify({"message": message}), 201
    else:
        return jsonify({"error": message}), 400

@app.route("/api/login", methods=["POST"])
def login_api():
    data = request.json
    email = (data.get("email") or "").lower().strip()
    password = data.get("password")
    
    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400
        
    if authenticate_user(email, password):
        session["user"] = email
        return jsonify({"message": "Login successful", "email": email}), 200
    else:
        return jsonify({"error": "Invalid email or password."}), 401
        
@app.route("/api/logout", methods=["POST"])
def logout_api():
    session.pop("user", None)
    return jsonify({"message": "Logged out successfully"}), 200

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login_page"))

# ================================
# ADMIN ENDPOINTS
# ================================

@app.route("/admin")
def admin_page():
    if session.get("user") != "admin@masterpredictor.com":
        return redirect("/login")
    return render_template("admin.html")

@app.route("/api/paper-trading", methods=["GET"])
def get_paper_trading_api():
    portfolio_file = os.path.join(BASE_DIR, "data", "paper_portfolio.json")
    if not os.path.exists(portfolio_file):
        return jsonify({"error": "Paper portfolio data not found."}), 404
    
    try:
        with open(portfolio_file, "r") as f:
            data = json.load(f)
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/data")
def admin_data():
    if session.get("user") != "admin@masterpredictor.com":
        return jsonify({"error": "Unauthorized"}), 401
    
    from database import get_all_users_summary
    data = get_all_users_summary()
    return jsonify(data)

@app.route("/api/admin/delete_user", methods=["POST"])
def admin_delete_user():
    if session.get("user") != "admin@masterpredictor.com":
        return jsonify({"error": "Unauthorized"}), 401
    
    email = request.json.get("email")
    if not email:
        return jsonify({"error": "Email is required"}), 400
        
    if email == "admin@masterpredictor.com":
        return jsonify({"error": "Cannot delete administrator account"}), 400
        
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
    summary = {
        "total_stocks": len(df),
        "buy_signals": len(df[df['Recommendation'] == 'BUY']),
        "sell_signals": len(df[df['Recommendation'] == 'SELL']),
        "hold_signals": len(df[df['Recommendation'] == 'HOLD']),
        "latest_date": str(df['Date'].iloc[0])[:16] if not df.empty else "N/A"
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
    total_invested = 0
    total_current = 0
    total_predicted = 0
    
    for item in holdings:
        ticker = item["ticker"]
        qty = item["quantity"]
        purchase_price = item["purchase_price"]
        
        try:
            # 1. Get live data
            price_data = get_live_price(ticker)
            current_price = price_data["current_price"]
            
            # 2. Get model prediction (T+1)
            recommendation = "HOLD"
            predicted_price = current_price # Default
            
            if os.path.exists(LATEST_DATA_FILE):
                latest_df = pd.read_json(LATEST_DATA_FILE)
                stock_match = latest_df[latest_df['Stock'] == ticker.upper()]
                if not stock_match.empty:
                    recommendation = stock_match.iloc[0]['Recommendation']
                    prob_up = stock_match.iloc[0]['Prob_Up']
                    
                    # Simulated prediction logic (matching get_stock_history/get_live_data)
                    if recommendation == 'BUY':
                        drift = 0.015 + (prob_up - 0.5) * 0.05
                    elif recommendation == 'SELL':
                        drift = -0.015 - ((1 - prob_up) - 0.5) * 0.05
                    else:
                        drift = 0.0
                    
                    predicted_price = round(current_price * (1 + drift), 2)

            # 3. Calculations
            cost_basis = qty * purchase_price
            current_val = qty * current_price
            predicted_val = qty * predicted_price
            p_l = current_val - cost_basis
            p_l_pct = (p_l / cost_basis * 100) if cost_basis != 0 else 0
            
            total_invested += cost_basis
            total_current += current_val
            total_predicted += predicted_val

            portfolio_data.append({
                "ticker": ticker,
                "quantity": qty,
                "purchase_price": purchase_price,
                "current_price": current_price,
                "predicted_price": predicted_price,
                "cost_basis": round(cost_basis, 2),
                "current_value": round(current_val, 2),
                "predicted_value": round(predicted_val, 2),
                "p_l": round(p_l, 2),
                "p_l_pct": round(p_l_pct, 2),
                "recommendation": recommendation
            })
        except Exception as e:
            continue
            
    return jsonify({
        "holdings": portfolio_data,
        "summary": {
            "total_invested": round(total_invested, 2),
            "total_current": round(total_current, 2),
            "total_predicted": round(total_predicted, 2),
            "total_p_l": round(total_current - total_invested, 2),
            "total_p_l_pct": round(((total_current - total_invested) / total_invested * 100) if total_invested != 0 else 0, 2)
        }
    })

@app.route("/api/portfolio/add", methods=["POST"])
def add_portfolio_item():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    ticker = data.get("ticker", "").upper()
    quantity = float(data.get("quantity", 1))
    purchase_price = float(data.get("purchase_price", 0))
    
    if not ticker:
        return jsonify({"error": "Ticker is required"}), 400
        
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
    data_file = LATEST_INTRADAY_DATA_FILE if mode == "intraday" else LATEST_DATA_FILE

    try:
        # Get data from realtime module
        price_data = get_live_price(ticker, period=period, interval=interval)
        dates = price_data["dates"]
        prices = price_data["prices"]
        current_value = price_data["current_price"]
            
        # Extrapolate predicted Price based on the model probabilities
        predicted_value = current_value
        
        if os.path.exists(data_file):
            latest_df = pd.read_json(data_file)
            stock_rec = latest_df[latest_df['Stock'] == ticker.upper()]
            
            if not stock_rec.empty:
                rec = stock_rec.iloc[0]['Recommendation']
                prob = stock_rec.iloc[0]['Prob_Up']
                
                # Drift logic
                if rec == 'BUY':
                    drift = 0.015 + (prob - 0.5) * 0.05
                elif rec == 'SELL':
                    drift = -0.015 - ((1 - prob) - 0.5) * 0.05
                else:
                    drift = random.uniform(-0.005, 0.005)
                    
                predicted_value = round(current_value * (1 + drift), 2)

        return jsonify({
            "ticker": ticker,
            "dates": dates,
            "prices": prices,
            "current_price": current_value,
            "predicted_price": predicted_value
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/news/<ticker>", methods=["GET"])
def get_news(ticker):
    """
    Fetches the latest relative financial news items using the Polygon.io API.
    """
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
        prob_up = 0.5
        if os.path.exists(data_file):
            latest_df = pd.read_json(data_file)
            stock_match = latest_df[latest_df['Stock'] == ticker.upper()]
            if not stock_match.empty:
                recommendation = stock_match.iloc[0]['Recommendation']
                prob_up = stock_match.iloc[0]['Prob_Up']

        # 3. News & Sentiment
        headlines = get_news_headlines(ticker)
        sentiment = get_sentiment(headlines)

        # 4. Predict next value
        if recommendation == 'BUY':
            base_drift = 0.015 + (prob_up - 0.5) * 0.05
        elif recommendation == 'SELL':
            base_drift = -0.015 - ((1 - prob_up) - 0.5) * 0.05
        else:
            base_drift = 0.0 

        sent_drift = sentiment["score"] * 0.01
        total_drift = base_drift + sent_drift
        
        predicted_price = round(float(current_price) * (1 + total_drift), 2)
        suggestion = recommendation 

        return jsonify({
            "ticker": ticker.upper(),
            "current_price": current_price,
            "predicted_price": predicted_price,
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
        print("Starting Master Predictor Server on port 5001...")
        app.run(debug=True, port=5001)
    except Exception as e:
        print(f"CRITICAL ERROR DURING STARTUP: {e}")
        import traceback
        traceback.print_exc()
