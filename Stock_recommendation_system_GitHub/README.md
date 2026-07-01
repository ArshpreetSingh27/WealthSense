# Master Predictor - Algorithmic Stock Recommendation System

Master Predictor is a web-based financial analytics terminal built with Flask, SQLite, and Python. It provides algorithmic trading signals (Daily & Intraday), real-time global market intelligence, sentiment analysis on financial news, portfolio risk tracking, and a de-risking engine.

---

## Features

1. **Daily and Intraday Signals**: View real-time recommendations (BUY/SELL/HOLD) derived from machine learning and algorithmic models.
2. **World Market Intelligence**: Track global indices (NIFTY 50, SENSEX, S&P 500, NASDAQ, FTSE 100, NIKKEI 225) alongside real-time updates.
3. **Sentiment Analysis**: Sentiment scores dynamically calculated from Google News RSS headlines using VADER Sentiment analysis with a customized financial lexicon.
4. **Wealth Portfolio**: Track private holdings, current valuations, P&L, and T+1 predicted price targets based on model drift.
5. **Institutional Risk Monitor**: Automatically calculates net and gross exposures and implements drawdown de-risking and ADV constraints.
6. **Machine Learning Pipeline**: Custom scripts in `data/scripts/` to train and evaluate predictors using LightGBM, Random Forests, and event-driven ensembles.

---

## Tech Stack

- **Backend**: Python, Flask, Flask-CORS, SQLite3
- **Data & Models**: pandas, numpy, scikit-learn, LightGBM, yfinance, VADER Sentiment
- **Frontend**: HTML5, Vanilla CSS (Design system), Vanilla Javascript, Chart.js

---

## Installation & Setup

### Prerequisites
- Python 3.8 or higher
- `pip` package manager

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Stock_recommendation_system
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database & Run Server
Run the Flask server:
```bash
python app.py
```
Upon launching, Flask will automatically initialize the local SQLite database (`master_predictor.db`) if it doesn't already exist.

Access the application in your browser at:
`http://127.0.0.1:5001`

---

## Project Structure

```text
├── app.py                      # Flask main server & API endpoints
├── database.py                 # SQLite database models & authentication logic
├── realtime.py                 # YFinance, Google News RSS, and Sentiment engine
├── risk_manager.py             # Portfolio risk guardrails & exposure limits
├── requirements.txt            # System dependencies
├── templates/                  # Frontend HTML templates
│   ├── index.html              # Main dashboard
│   ├── portfolio.html          # Portfolio viewer
│   ├── login.html              # Subscriber login/registration
│   └── admin.html              # Admin panel
├── static/                     # Assets & Stylesheets
│   ├── css/                    # Custom CSS stylesheets
│   └── js/                     # Client-side JavaScript
└── data/                       # Cached recommendations, logs, and ML pipeline scripts
    ├── processed/              # Formatted features and models recommendations
    └── scripts/                # Python scripts for backtesting and ML model training
```

---

## Configuration

You can override standard settings using environment variables:
- `FLASK_SECRET_KEY`: Override the secret key for session storage.
- `POLYGON_API_KEY`: API key for news sentiment checks (falls back to a default key if not set).
