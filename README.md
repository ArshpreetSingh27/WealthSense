# WEALTH sense - Portfolio Intelligence

WEALTH sense is a multi-user paper trading and portfolio application for NSE India markets. Each user has a separate virtual account and may opt in to a daily paper bot. Kite is used only to show that user's read-only Zerodha portfolio. The current research model is experimental.

See [PROJECT_PHASES.md](PROJECT_PHASES.md) for the implementation phases and release gates.

---

## Features

**Experimental research signals**
Generates directional BUY, SELL, and HOLD labels from historical NSE data. The daily classifier is not a validated price forecast.

**World Market Pulse**
Shows the latest available global index quotes including NIFTY 50, SENSEX, S&P 500, NASDAQ, FTSE 100, and NIKKEI 225 via Yahoo Finance.

**News Sentiment Engine**
Calculates real-time sentiment scores from Google News RSS headlines using VADER sentiment analysis with a custom financial lexicon.

**Wealth Portfolio Tracker**
Tracks manually entered holdings with latest available prices and estimated P&L. It is separate from the Kite portfolio and the paper account.

**Kite Portfolio (read-only integration)**
Each website user can connect or disconnect their own Zerodha account. The `/portfolio` page reads that user's Kite holdings, open positions, funds, and recent orders. The original manually entered tracker is at `/portfolio/manual` and is kept separate from broker data. Broker orders are not placed by this integration.

**Per-user paper trading**
The Paper Trading tab gives each user ₹10,00,000 in virtual starting cash. Manual paper buys and sells use the latest available NSE close and modeled 0.12% execution friction. A user can enable a daily long-only paper bot or run it manually. Virtual trades are stored per user in SQLite and never sent to Kite.

**Paper trading limits**
Virtual orders require available cash, cannot short stocks, and cap a single paper position at 20% of starting capital. Users can pause their paper bot.

**Interactive Stock Charts**
Drill-down charts with historical OHLCV data, RSI indicator, and model confidence scores.

**Subscriber Authentication**
Secure login and registration system with an admin panel for user management.

**ML Pipeline Scripts**
A full suite of backtesting, feature engineering, walk-forward validation, and model retraining scripts.

---

## Tech Stack

Backend:
- Python 3.10+, Flask
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
- Python 3.10 or higher
- pip package manager

### 1. Clone the Repository
```bash
git clone https://github.com/flyingsaucer1/WealthSense.git
cd WealthSense
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python start_site.py
```

The launcher opens `http://127.0.0.1:5050/login` automatically. The HTML files in `templates/` must be rendered by Flask; opening them directly from File Explorer shows raw template tags and no styling. Set `APP_PORT` if port 5050 is already in use. You can also run `python app.py` and open the URL yourself.

On first launch, Flask initializes the local SQLite database. New accounts have no admin rights. After registering an account, grant its admin role locally with `python database.py --promote-admin your@email.example`, then sign in again. Existing accounts are not promoted automatically.

---

## Project Structure

```
WealthSense/
|
|-- app.py                         # Flask server, API endpoints and routing
|-- database.py                    # SQLite models, auth logic, user management
|-- paper_accounts.py              # Per-user virtual cash, positions, and fills
|-- paper_bot.py                   # Opt-in daily virtual trading logic
|-- kite_integration.py            # Read-only Kite API client
|-- kite_routes.py                 # Per-user Kite connect and sync routes
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
        |-- run_market_pipeline.py # Scheduled refresh and opted-in paper bots
        |-- update_pipeline.py     # Daily market-data and recommendation refresh
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

You can override default settings using environment variables. Copy `.env.example` to `.env` in the project root (it is listed in `.gitignore`):

```
FLASK_SECRET_KEY=your_secret_key_here
APP_HTTPS=1
POLYGON_API_KEY=your_polygon_api_key_here
KITE_API_KEY=your_kite_app_key
KITE_API_SECRET=your_kite_app_secret
KITE_TOKEN_ENCRYPTION_KEY=your_fernet_key
KITE_ENV=production
```

| Variable | Description |
|---|---|
| FLASK_SECRET_KEY | Secret key used for Flask session storage |
| APP_HTTPS | Set to `1` when serving through HTTPS to secure session cookies |
| POLYGON_API_KEY | Optional Polygon.io news key; detailed news is unavailable without it |
| KITE_API_KEY / KITE_API_SECRET | Server-side Kite Connect app credentials |
| KITE_TOKEN_ENCRYPTION_KEY | Fernet key used to encrypt each user's Kite access token in SQLite |
| KITE_ENV | `production` or `sandbox` (defaults to `production`) |

For a local Kite sandbox trial, set `KITE_ENV=sandbox` and use the demo app credentials documented by Kite. Generate a persistent encryption key once with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Configure the Kite app redirect URL as `https://YOUR_HOST/kite/callback` (or the corresponding local URL for sandbox). Keep the API secret and encryption key on the server; never put them in browser code. Users reconnect after their Kite session expires, normally by 6 AM the next day. The broker page refreshes when opened and every 60 seconds while visible.

The Kite integration reads broker data only. Before a public multi-user launch, arrange the appropriate Kite platform access with Zerodha and complete production security, deployment, and reconciliation.

The signal API rejects recommendations and trading signals whose source market date is more than seven calendar days old. Directional scores are not converted into invented price targets. The scheduled `MarketDataPipeline` refreshes market data and runs only user-enabled paper bots. The legacy shared `ShadowTradingPipeline` task remains disabled; its old file is not used for user accounts. No broker orders are placed.

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
