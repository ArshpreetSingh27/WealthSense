import re

class SentimentEngine:
    def __init__(self):
        # Basic finance-specific lexicons
        self.positive_words = r"(profit|beat|buy|record|dividend|growth|high|surge|gain|strong|upgrade|positive)"
        self.negative_words = r"(loss|miss|sell|decline|drop|low|crash|fall|weak|downgrade|negative|debt)"
        
    def score_headline(self, text):
        """
        Simple regex-based sentiment scorer.
        """
        text = text.lower()
        pos_count = len(re.findall(self.positive_words, text))
        neg_count = len(re.findall(self.negative_words, text))
        
        total = pos_count + neg_count
        if total == 0: return 0
        return (pos_count - neg_count) / total

    def simulate_historical_sentiment(self, df):
        """
        For backtesting: Proxy sentiment as Price-Volume Momentum.
        """
        df["Sentiment_Score"] = df["Return"].rolling(3).mean().shift(1) * 10
        df["Sentiment_Score"] = df["Sentiment_Score"].fillna(0).clip(-1, 1)
        return df

if __name__ == "__main__":
    engine = SentimentEngine()
    test_headline = "Record profit reported by bank, shares surge."
    print(f"Headline: {test_headline}")
    print(f"Sentiment Score: {engine.score_headline(test_headline)}")
