import pandas as pd

def load_stock(csv_file):
    """Load either the project's Yahoo-style CSV or a normal OHLCV CSV."""
    with open(csv_file, encoding="utf-8") as source:
        header = source.readline().strip().split(",")
    if header and header[0] == "Price":
        # Rows 2 and 3 contain the ticker and a second date label.
        df = pd.read_csv(csv_file, skiprows=[1, 2])
        df = df.rename(columns={"Price": "Date"})
    else:
        df = pd.read_csv(csv_file)

    columns = ["Date", "Close", "High", "Low", "Open", "Volume"]
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns in {csv_file}: {sorted(missing)}")
    df = df[columns].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    for column in columns[1:]:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df = df.dropna(subset=columns)
    return df.sort_values("Date").reset_index(drop=True)
