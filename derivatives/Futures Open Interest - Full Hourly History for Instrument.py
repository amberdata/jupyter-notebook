import requests
import csv
from datetime import datetime, timedelta

# Set your API Key and Instrument Name here
api_key = "Your_API_Key_Here"
instrument_name = "BTCUSDT"  

def format_date(date):
    return date.strftime("%Y-%m-%dT%H:%M:%S")

def get_oldest_start_date():
    url = f"https://web3api.io/api/v2/market/futures/exchanges/information?instrument={instrument_name}&includeDates=true&includeInactive=true&timeFormat=hr"
    headers = {
        "accept": "application/json",
        "x-api-key": api_key
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()['payload']['data']
        oldest_date = datetime.now()
        for exchange in data:
            if 'open_interest' in data[exchange][instrument_name]:
                start_date_str = data[exchange][instrument_name]['open_interest']['startDate']
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S %f")
                if start_date < oldest_date:
                    oldest_date = start_date
        return oldest_date
    else:
        print(f"Failed to fetch start date. Error: {response.text}")
        return None

def get_data(start_date, end_date):
    url = f"https://web3api.io/api/v2/market/futures/open-interest/{instrument_name}/historical?startDate={start_date}&endDate={end_date}&timeInterval=hours&timeFormat=hr"
    headers = {
        "accept": "application/json",
        "x-api-key": api_key
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()['payload']['data']
    else:
        print(f"Failed to fetch data for range {start_date} to {end_date}. Error: {response.text}")
        return []

# Start the timer
start_time = datetime.now()

# Get the oldest start date for Open Interest data
start_period = get_oldest_start_date()
if not start_period:
    raise Exception("Failed to obtain start date for Open Interest data.")

# Set the end period to the current date
end_period = datetime.now()

all_data = []

current_start = start_period
while current_start < end_period:
    current_end = min(current_start + timedelta(days=31), end_period)
    data = get_data(format_date(current_start), format_date(current_end))
    all_data.extend(data)
    current_start = current_end

csv_file_name = f'{instrument_name}_open_interest.csv'
with open(csv_file_name, 'w', newline='') as file:
    writer = csv.writer(file)
    writer.writerow(['exchange', 'timestamp', 'value', 'type'])
    for entry in all_data:
        writer.writerow([entry['exchange'], entry['timestamp'], entry['value'], entry['type']])

# End the timer
end_time = datetime.now()

# Calculate and print the total runtime
total_runtime = end_time - start_time
print(f"Data retrieval complete. CSV file '{csv_file_name}' created. Total runtime: {total_runtime}")