import requests
import pandas as pd
import datetime
from time import time, sleep

# Hardcoded values
API_KEY = "your_api_key_here"  # Replace with your actual API key
INSTRUMENT = "STORJUSDT"  # Replace with your desired instrument
EXCHANGE = "binance"  # Replace with your desired exchange

def get_funding_rate_data(start_date, end_date, max_retries=4):
    url = f"https://web3api.io/api/v2/market/futures/funding-rates/{INSTRUMENT}/historical"
    params = {
        "exchange": EXCHANGE,
        "startDate": start_date.strftime("%Y-%m-%d"),
        "endDate": end_date.strftime("%Y-%m-%d"),
        "timeInterval": "hours",
        "timeFormat": "hr"
    }
    headers = {
        "accept": "application/json",
        "x-api-key": API_KEY
    }

    retries = 0
    while retries <= max_retries:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()['payload']['data']
        else:
            retries += 1
            sleep(2)  # Wait for 2 seconds before retrying

    print(f"Failed to fetch data for period {start_date} to {end_date} after {max_retries} retries.")
    return [{"timestamp": start_date.strftime("%Y-%m-%d %H:%M:%S"), "fundingRate": "NO DATA"}]

def main():
    # Get the start date for the funding rate data
    info_url = f"https://web3api.io/api/v2/market/futures/exchanges/information"
    params = {
        "exchange": EXCHANGE,
        "instrument": INSTRUMENT,
        "includeDates": "true",
        "includeInactive": "true",
        "timeFormat": "hr"
    }
    headers = {
        "accept": "application/json",
        "x-api-key": API_KEY
    }

    response = requests.get(info_url, headers=headers, params=params)
    if response.status_code != 200:
        print("Failed to fetch start date for funding rate data")
        return

    start_date = datetime.datetime.strptime(response.json()['payload']['data'][EXCHANGE][INSTRUMENT]['funding_rate']['startDate'], "%Y-%m-%d %H:%M:%S %f")
    end_date = datetime.datetime.now()

    all_data = []

    # Iterate through time periods in 10-day intervals
    while start_date < end_date:
        next_end_date = min(start_date + datetime.timedelta(days=10), end_date)
        print(f"Fetching data from {start_date} to {next_end_date}")
        data = get_funding_rate_data(start_date, next_end_date)
        all_data.extend(data)
        start_date = next_end_date

    # Convert to DataFrame and save as CSV
    file_name = f"{INSTRUMENT}_{EXCHANGE}_hourly.csv"
    df = pd.DataFrame(all_data)
    df.to_csv(file_name, index=False)
    print(f"Data saved to {file_name}")

if __name__ == "__main__":
    start_time = time()
    main()
    end_time = time()
    print(f"Script completed in {end_time - start_time} seconds")