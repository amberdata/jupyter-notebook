import requests
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

api_key = "YOUR_API_KEY_HERE"
asset = "eth"

# Function to parse the custom timestamp format
def parse_timestamp(timestamp_str):
    return datetime.strptime(timestamp_str[:-4], '%Y-%m-%d %H:%M:%S')

# Initialize variables
base_url = "https://api.amberdata.com/markets/spot/reference-rates/" + asset
headers = {"accept": "application/json", "x-api-key": api_key}
start_date = datetime(2010, 1, 1)
end_date = datetime.now()
all_data = []

# Iterative API calls
while start_date < end_date:
    formatted_start_date = start_date.strftime("%Y-%m-%d")
    next_date = start_date + timedelta(days=730)
    formatted_end_date = min(next_date, end_date).strftime("%Y-%m-%d")
    
    url = f"{base_url}?startDate={formatted_start_date}&endDate={formatted_end_date}&timeFormat=hr&timeInterval=hours"
    response = requests.get(url, headers=headers).json()
    
    # Extract and append data
    prices = response['payload']['data']['referenceRates']
    for price in prices:
        timestamp = parse_timestamp(price['timestamp'])
        unit_price = price['unitPrice']
        all_data.append({"Timestamp": timestamp, "UnitPrice": unit_price})
    
    start_date = next_date

# Create DataFrame from the list
data_frame = pd.DataFrame(all_data)

# Data processing
data_frame.sort_values(by='Timestamp', inplace=True)

# Data visualization
plt.figure(figsize=(12, 6))
plt.plot(data_frame['Timestamp'], data_frame['UnitPrice'])
plt.title(asset.upper() +' Price Over Time')
plt.xlabel('Date')
plt.ylabel('Price (USD)')
plt.grid(True)
plt.show()