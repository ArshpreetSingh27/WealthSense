import pandas as pd

def load_stock(csv_file):
    df = pd.read_csv(
        csv_file,
        skiprows=2,   # skip Yahoo/NSE junk rows
        names=["Date", "Close", "High", "Low", "Open", "Volume"]
    )

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna()
    df = df.reset_index(drop=True)

    return df
