import pandas as pd
import matplotlib.pyplot as plt
import requests
from datetime import datetime
import os
import time
from dotenv import load_dotenv

# Load environment variables (not needed in GitHub Actions since secrets are injected directly)
# load_dotenv()

# Imgur API setup
IMGUR_CLIENT_ID = os.getenv('IMGUR_CLIENT_ID')  # GitHub Actions will set this as an environment variable
IMGUR_UPLOAD_URL = 'https://api.imgur.com/3/image'
IMGUR_DELETE_URL = 'https://api.imgur.com/3/image/{image_id}'  # URL for deleting images from Imgur

# CoinGecko API setup for fetching coin data
def fetch_data_from_coingecko(symbol):
    # For daily EMAs, get last 30-90 days of data (adjust as needed)
    url = f'https://api.coingecko.com/api/v3/coins/{symbol}/market_chart'
    params = {'vs_currency': 'usd', 'days': '90', 'interval': 'daily'}
    
    response = requests.get(url, params=params)
    
    if response.status_code == 429:
        print(f"Rate limit hit for {symbol}, retrying after a delay...")
        time.sleep(10)  # Wait 10 seconds before retrying
        return fetch_data_from_coingecko(symbol)  # Retry the request
    
    if response.status_code != 200:
        print(f"Error fetching data for {symbol}: {response.status_code}")
        return pd.DataFrame()  # Return an empty DataFrame if there's an issue
    
    data = response.json()
    
    if 'prices' not in data:
        print(f"No 'prices' found in the response for {symbol}")
        return pd.DataFrame()  # Return an empty DataFrame if 'prices' is missing
    
    # Process daily data
    prices = data['prices']
    dates = [datetime.utcfromtimestamp(item[0] / 1000) for item in prices]
    prices = [item[1] for item in prices]
    df = pd.DataFrame({'DATE': dates, 'PRICE': prices})
    
    # Calculate EMAs with parameters matching TradingView's defaults for daily timeframe
    # For daily charts, TradingView typically uses 9 and 21 by default
    df['EXP_9'] = df['PRICE'].ewm(span=9, adjust=False).mean()
    df['EXP_21'] = df['PRICE'].ewm(span=21, adjust=False).mean()
    
    return df

# Function to upload image to Imgur
def upload_to_imgur(image_path):
    headers = {
        'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'
    }
    
    with open(image_path, 'rb') as image_file:
        files = {
            'image': image_file,
            'type': 'file'
        }
        
        # Send the file to Imgur
        response = requests.post(IMGUR_UPLOAD_URL, headers=headers, files=files)
        
    response_data = response.json()
    
    if response.status_code == 200:
        return response_data['data']['link'], response_data['data']['id']
    else:
        print(f"Failed to upload to Imgur: {response_data}")
        return None, None

# Function to delete old Imgur images
def delete_old_imgur_image(image_id):
    headers = {
        'Authorization': f'Client-ID {IMGUR_CLIENT_ID}'
    }
    
    # Send the delete request
    response = requests.delete(IMGUR_DELETE_URL.format(image_id=image_id), headers=headers)
    
    if response.status_code == 200:
        print(f"Deleted old image with ID: {image_id}")
    else:
        print(f"Failed to delete old image: {response.status_code}, {response.text}")

# Generate chart and upload to Imgur
def generate_and_upload_chart(asset, symbol):
    chart_name = f'{asset}_chart.png'

    print(f"Fetching data for {asset} ({symbol})...")
    df = fetch_data_from_coingecko(symbol)
    if df.empty:
        print(f"No data for {asset}")
        return None

    print(f"Generating chart for {asset}...")
    plt.figure(figsize=(12, 7))
    
    # Plot daily price
    plt.plot(df['DATE'], df['PRICE'], label=f'{asset} Daily Price', color='gray', alpha=0.5)
    
    # Plot EMAs - using 9 & 21 but labeling them as 10 & 20
    plt.plot(df['DATE'], df['EXP_9'], label=f'{asset} EMA(10)', color='blue', linewidth=2)
    plt.plot(df['DATE'], df['EXP_21'], label=f'{asset} EMA(20)', color='red', linewidth=2)
    
    # Add chart title indicating daily timeframe
    plt.title(f'{asset} Daily Price with EMAs')
    plt.xlabel('Date')
    plt.ylabel('Price (USD)')
    plt.legend()
    plt.grid()
    plt.xticks(rotation=45)
    plt.tight_layout()  # Adjust layout to make room for rotated labels
    plt.savefig(chart_name, dpi=300)
    plt.close()

    print(f"Uploading chart for {asset} to Imgur...")
    imgur_url, imgur_image_id = upload_to_imgur(chart_name)

    # If upload successful, delete the local image file and write URL to a file
    if imgur_url:
        print(f"Uploaded new chart to Imgur: {imgur_url}")
        
        # Append the URL to the 'latest_chart_urls.txt' file
        with open('latest_chart_urls.txt', 'a') as file:
            file.write(f'{asset}: {imgur_url}\n')  # Save asset name and the corresponding chart URL
        print(f"Saved new chart URL for {asset} to latest_chart_urls.txt")
        
        # Clean up local image file
        try:
            os.remove(chart_name)
            print(f"Removed local image file: {chart_name}")
        except Exception as e:
            print(f"Failed to remove local image file: {e}")
            
    return imgur_url

# Save the new chart URLs to the file
def save_chart_urls(links):
    # Open the file in write mode to overwrite the existing content
    with open('latest_chart_urls.txt', 'w') as file:
        for asset, url in links.items():
            file.write(f'{asset}: {url}\n')
    print("Saved new chart URLs to latest_chart_urls.txt")

# Main function to process the coins and upload their charts
def main():
    assets = {'ETH': 'ethereum', 'AVAX': 'avalanche-2', 'XLM': 'stellar', 'ONDO': 'ondo-finance'}
    links = {}
    
    # Add rate limiting to avoid CoinGecko API limits
    for asset, symbol in assets.items():
        print(f"Processing {asset} ({symbol})...")
        link = generate_and_upload_chart(asset, symbol)
        if link:
            links[asset] = link
        else:
            print(f"Failed to generate or upload chart for {asset}")
        
        # Add delay between API calls to avoid rate limiting
        if asset != list(assets.keys())[-1]:  # If not the last asset
            print("Waiting 2 seconds before next API call...")
            time.sleep(2)

    print("Updated chart links:", links)

    # Save the latest chart URLs to the text file
    if links:
        save_chart_urls(links)

if __name__ == "__main__":
    main()
