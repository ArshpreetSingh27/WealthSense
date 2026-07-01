# Master Predictor - Algorithmic Stock Recommendation System

Master Predictor is a full-stack, AI-powered stock recommendation terminal built for NSE India markets. It combines machine learning predictions, real-time market data, sentiment analysis on live financial news, and an institutional-grade portfolio risk engine — all served through a web interface.

---

## Features

**AI Signals (Daily and Intraday)**
Generates BUY, SELL, and HOLD recommendations using LightGBM, Random Forest, and event-driven ensemble models trained on historical NSE data.

**World Market Pulse**
Tracks live global indices including NIFTY 50, SENSEX, S&P 500, NASDAQ, FTSE 100, and NIKKEI 225 via the Yahoo Finance API.

**News Sentiment Engine**
Calculates real-time sentiment scores from Google News RSS headlines using VADER sentiment analysis with a custom financial lexicon.

**Wealth Portfolio Tracker**
Tracks private holdings with live P&L, current valuations, and T+1 predicted price targets based on model drift.

**Institutional Risk Monitor**
Calculates net and gross exposures and enforces drawdown de-risking and ADV (Average Daily Volume) constraints automatically.

**Interactive Stock Charts**
Drill-down charts with historical OHLCV data, RSI indicator, and model confidence scores.

**Subscriber Authentication**
Secure login and registration system with an admin panel for user management.

**ML Pipeline Scripts**
A full suite of backtesting, feature engineering, walk-forward validation, and model retraining scripts.

---

## Tech Stack

Backend:
- Python 3.8+, Flask, Flask-CORS
- SQLite3
- yfinance for live stock prices and OHLCV history
- feedparser for Google News RSS
- vaderSentiment for NLP sentiment analysis
- LightGBM and scikit-learn for ML prediction models

Frontend:
- HTML5, Vanilla CSS with a custom dark-mode design system
- Vanilla JavaScript, Chart.js

ML Pipeline:
- pandas, numpy for feature engineering
- Walk-forward cross-validation
- Event-driven ensemble combining LightGBM, Ridge regression, and Random Forest

---

## Getting Started

### Prerequisites
- Python 3.8 or higher
- pip package manager

### 1. Clone the Repository
```bash
git clone https://github.com/YOUR_USERNAME/Stock_recommendation_system.git
cd Stock_recommendation_system
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python app.py
```

Open your browser at `http://127.0.0.1:5001`

On first launch, Flask automatically initializes the local SQLite database. Default admin credentials are configured in `database.py`.

---

## Project Structure

```
Stock_recommendation_system/
|
|-- app.py                         # Flask server, API endpoints and routing
|-- database.py                    # SQLite models, auth logic, user management
|-- realtime.py                    # Live data: yFinance, Google News RSS, Sentiment
|-- risk_manager.py                # Portfolio risk guardrails and exposure limits
|-- requirements.txt               # Python dependencies
|-- README.md
|
|-- templates/
|   |-- index.html                 # Main dashboard (signals, market pulse, news)
|   |-- portfolio.html             # Portfolio tracker and risk monitor
|   |-- login.html                 # Auth page (login and registration)
|   `-- admin.html                 # Admin panel (user management)
|
|-- static/
|   |-- css/
|   |   |-- style.css              # Main dashboard design system
|   |   `-- portfolio.css          # Portfolio page styles
|   `-- js/
|       |-- main.js                # Dashboard logic (charts, signals, news)
|       |-- portfolio.js           # Portfolio tracker logic
|       `-- admin.js               # Admin panel logic
|
`-- data/
    |-- latest_trading_signals.json
    |-- portfolio_schema.json
    |-- processed/
    |   |-- latest_recommendations.json
    |   `-- latest_recommendations_intraday.json
    |-- models/
    |   |-- lgb_event.pkl
    |   |-- lgb_midcap.pkl
    |   |-- lgb_neutral.pkl
    |   |-- lgb_ranking.pkl
    |   |-- rf_midcap.pkl
    |   `-- ...
    `-- scripts/
        |-- update_pipeline.py     # Master daily pipeline runner
        |-- train_model.py         # Daily model training
        |-- train_intraday_model.py
        |-- train_event_ensemble.py
        |-- backtest.py
        |-- generate_daily_signals.py
        |-- paper_trader.py
        `-- ...
```

---

## Configuration

You can override default settings using environment variables. Create a `.env` file in the project root (it is already listed in `.gitignore` and will not be committed to Git):

```
FLASK_SECRET_KEY=your_secret_key_here
POLYGON_API_KEY=your_polygon_api_key_here
```

| Variable | Description |
|---|---|
| FLASK_SECRET_KEY | Secret key used for Flask session storage |
| POLYGON_API_KEY | API key for Polygon.io news data (optional, has fallback) |

---

## Updating Predictions

To refresh ML recommendations with the latest market data, run:

```bash
python data/scripts/update_pipeline.py
```

This will fetch fresh OHLCV data from Yahoo Finance, engineer features, run model inference, and output updated recommendation JSON files to `data/processed/`.

---

## Data Sources

| Data Type | Source | Method |
|---|---|---|
| Stock Prices and History | Yahoo Finance | yfinance API, fetched live on each request |
| Global Index Prices | Yahoo Finance | yf.download(), fetched live on each request |
| News Headlines | Google News RSS | feedparser, fetched live on each request |
| Detailed News | Polygon.io | REST API, fetched live on each request |
| ML Predictions | Local pipeline | Pre-computed JSON files, updated by running the pipeline |

---

## License

This project is licensed under the MIT License.
