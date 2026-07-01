"""
realtime.py — Live stock data + news sentiment module for Master Predictor.

Three public functions:
  get_live_price(ticker)   -> dict with current price, 30-day history
  get_news_headlines(ticker) -> list of dicts (title, url, source)
  get_sentiment(headlines)   -> dict with score, label, per-headline scores
"""

import yfinance as yf
import requests
import feedparser
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from urllib.parse import quote_plus

_analyzer = SentimentIntensityAnalyzer()

# Financial Lexicon for VADER (Refining Sentiment Correctness)
# Injects finance-specific meanings for common market terms
FINANCIAL_LEXICON = {
    "bullish": 2.0,
    "bearish": -2.0,
    "soaring": 2.5,
    "plunging": -2.5,
    "rally": 1.5,
    "slump": -1.5,
    "surge": 2.0,
    "crash": -3.0,
    "outperform": 1.8,
    "underperform": -1.8,
    "growth": 1.2,
    "profit": 1.5,
    "loss": -1.5,
    "debt": -1.0,
    "dividend": 1.0,
    "upgrade": 1.5,
    "downgrade": -1.5,
    "bankrupt": -4.0,
    "volatile": -0.5,
    "steady": 0.5,
    "rebound": 1.2,
    "selling": -0.8,
    "buying": 0.8,
    "target": 0.5,
    "peak": 0.5,
    "low": -0.5,
    "hit": -0.5, # Often used as "hit a low" or "hit by loss"
}
_analyzer.lexicon.update(FINANCIAL_LEXICON)
 


# ─────────────────────────────────────────
# 1. LIVE PRICE & HISTORY (yfinance)
# ─────────────────────────────────────────

def get_live_price(ticker: str, period: str = "35d", interval: str = "1d") -> dict:
    """
    Fetches current price + historical close history for `ticker`.
    Ticker should be the Yahoo Finance symbol (e.g. 'RELIANCE.NS', 'AAPL').
    Returns:
        {
          "current_price": float,
          "dates": [str, ...],
          "prices": [float, ...]
        }
    Raises ValueError if data is unavailable.
    """
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period, interval=interval)

    if hist.empty and not ticker.endswith((".NS", ".BO", ".BSE")):
        # Fallback for Indian stocks (since dashboard cards omit suffix)
        stock = yf.Ticker(ticker + ".NS")
        hist = stock.history(period=period, interval=interval)

    if hist.empty:
        raise ValueError(f"No data found for ticker '{ticker}'. Check the symbol.")

    hist = hist.tail(30)
    if interval == "1d":
        dates = hist.index.strftime("%Y-%m-%d").tolist()
    else:
        dates = hist.index.strftime("%H:%M").tolist() # Just show time for intraday
    prices = [round(float(p), 2) for p in hist["Close"].tolist()]
    current_price = prices[-1]

    return {
        "current_price": current_price,
        "dates": dates,
        "prices": prices,
    }


# ─────────────────────────────────────────
# 2. NEWS HEADLINES (Google News RSS)
# ─────────────────────────────────────────

def get_news_headlines(ticker: str, limit: int = 5) -> list:
    """
    Fetches the latest stock-related headlines from Google News RSS.
    No API key required.
    Returns a list of dicts: [{"title": str, "url": str, "source": str}, ...]
    Returns empty list on failure (no exception raised).
    """
    # Enhanced search term for more genuine financial news
    search_term = f"{ticker.split('.')[0]} stock price market analysis news"
    encoded = quote_plus(search_term)
    # Using more specific region/language parameters for relevant English financial news
    rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"

    try:
        feed = feedparser.parse(rss_url)
        
        # Sort by published_parsed descending to get absolute newest
        entries = feed.entries
        entries.sort(
            key=lambda x: x.get("published_parsed", (0,)*9) or (0,)*9,
            reverse=True
        )
        
        articles = []
        for entry in entries[:limit]:
            # Google News RSS source is in entry.source.title
            source = getattr(getattr(entry, "source", None), "title", "Google News")
            articles.append({
                "title": entry.get("title", "No title"),
                "url": entry.get("link", "#"),
                "source": source,
            })
        return articles
    except Exception:
        return []


# ─────────────────────────────────────────
# 3. VADER SENTIMENT
# ─────────────────────────────────────────

def get_sentiment(headlines: list) -> dict:
    """
    Runs VADER sentiment on a list of headline dicts (must have 'title').
    Returns:
        {
          "score": float,         # compound score -1.0 to +1.0
          "label": str,           # 'positive' | 'neutral' | 'negative'
          "per_headline": [float] # compound score per headline
        }
    Returns neutral defaults if headlines is empty.
    """
    if not headlines:
        return {"score": 0.0, "label": "neutral", "per_headline": []}

    scores = [_analyzer.polarity_scores(h["title"])["compound"] for h in headlines]
    avg = round(sum(scores) / len(scores), 4)

    if avg >= 0.05:
        label = "positive"
    elif avg <= -0.05:
        label = "negative"
    else:
        label = "neutral"

    return {
        "score": avg,
        "label": label,
        "per_headline": [round(s, 4) for s in scores],
    }


# ─────────────────────────────────────────
# 4. GLOBAL INDICES (yfinance)
# ─────────────────────────────────────────

def get_indices_data() -> list:
    """
    Fetches real-time data for major global indexes.
    Returns a list of dicts: [{"name": str, "price": float, "change": float, "pct_change": float}, ...]
    """
    indices_map = {
        "NIFTY 50": "^NSEI",
        "SENSEX": "^BSESN",
        "S&P 500": "^GSPC",
        "NASDAQ": "^IXIC",
        "FTSE 100": "^FTSE",
        "NIKKEI 225": "^N225"
    }
    
    # Using download for efficiency
    tickers = list(indices_map.values())
    try:
        data = yf.download(tickers, period="8d", interval="1d", group_by='ticker', progress=False)
        results = []
        
        for name, ticker in indices_map.items():
            try:
                if ticker in data.columns.levels[0]:
                    ticker_data = data[ticker]
                    if not ticker_data.empty:
                        # Get close prices
                        closes = ticker_data['Close'].dropna()
                        if len(closes) >= 1:
                            current = closes.iloc[-1]
                            prev = closes.iloc[-2] if len(closes) > 1 else current
                            change = current - prev
                            pct_change = (change / prev) * 100 if prev != 0 else 0
                            
                            # Last 7 days for sparkline
                            history = [round(float(p), 2) for p in closes.tail(7).tolist()]
                            
                            results.append({
                                "name": name,
                                "ticker": ticker,
                                "price": round(float(current), 2),
                                "change": round(float(change), 2),
                                "pct_change": round(float(pct_change), 2),
                                "history": history
                            })
            except Exception:
                continue
        return results
    except Exception:
        return []

