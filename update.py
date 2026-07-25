from src.data import update_market_data

if __name__ == "__main__":
    prices, status = update_market_data(years=5)
    print(status.to_string(index=False))
    print(f"market rows: {len(prices)}")
