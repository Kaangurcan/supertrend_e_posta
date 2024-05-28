import pandas as pd
import numpy as np
import time
import smtplib
import yfinance as yf
import configparser
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from tabulate import tabulate

# Define the symbol and time interval
period = "5d"  # 5 days worth of data
timeframes = ['30m']  # 30 minutes timeframes to check

# Define markets and symbols
markets = [
    {'symbol': '^GSPC'},  # S&P 500 Index
    {'symbol': '^DJI'},   # Dow Jones Industrial Average
    {'symbol': '^IXIC'},  # NASDAQ Composite
    {'symbol': '^VIX'},   # CBOE Volatility Index
    {'symbol': 'NVDA'},   # NVIDIA Corporation
    {'symbol': 'XU100.IS'},   # BIST 100
    {'symbol': 'AMZN'},   # Amazon.com, Inc.
    {'symbol': 'TSLA'},   # Tesla, Inc.
    {'symbol': 'GC=F'},   # Gold Futures
    {'symbol': 'SI=F'},   # Silver Futures
    {'symbol': 'BZ=F'},   # Brent Crude Oil Last Day Finance
    {'symbol': 'UNG'},    # United States Natural Gas Fund
    {'symbol': 'CC=F'},   # Cocoa Jul 24
    {'symbol': 'TRY=X'},  # USD/TRY
    {'symbol': 'EURUSD=X'},  # EUR/USD
    {'symbol': 'JPY=X'},  # USD/JPY
    {'symbol': 'BTC-USD'},  # Bitcoin
    {'symbol': 'ETH-USD'},  # Ethereum
    {'symbol': 'AVAX-USD'},  # Avalanche
]

# Email settings
config = configparser.ConfigParser()
config.read('config.ini')
sender_email = config['EMAIL_SETTINGS']['SENDER_EMAIL']
receiver_email = config['EMAIL_SETTINGS']['RECEIVER_EMAIL']
password = config['EMAIL_SETTINGS']['PASSWORD']

# Function to send email
def send_email(subject, body):
    message = MIMEText(body)
    message['Subject'] = subject
    message['From'] = sender_email
    message['To'] = receiver_email
    
    # Connect to SMTP server and send email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, password)
        try:
            server.sendmail(sender_email, receiver_email, message.as_string())
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print("E-posta gönderilirken bir hata oluştu:", e)

# Function to calculate Supertrend
def calculate_supertrend(dataframe, period=10, multiplier=3):
    high = dataframe['High']
    low = dataframe['Low']
    close = dataframe['Close']
    
    # Calculate ATR (Average True Range)
    dataframe['ATR'] = (high - low).rolling(period).mean()
    dataframe['basic_ub'] = (high + low) / 2 + multiplier * dataframe['ATR']
    dataframe['basic_lb'] = (high + low) / 2 - multiplier * dataframe['ATR']
    
    dataframe['final_ub'] = np.nan
    dataframe['final_lb'] = np.nan
    dataframe.loc[dataframe.index[period], 'final_ub'] = dataframe['basic_ub'].iloc[:period].mean()
    dataframe.loc[dataframe.index[period], 'final_lb'] = dataframe['basic_lb'].iloc[:period].mean()

    for i in range(period + 1, len(dataframe)):
        if dataframe['Close'].iloc[i - 1] <= dataframe['final_ub'].iloc[i - 1]:
            dataframe.loc[dataframe.index[i], 'final_ub'] = min(dataframe['basic_ub'].iloc[i], dataframe['final_ub'].iloc[i - 1])
        else:
            dataframe.loc[dataframe.index[i], 'final_ub'] = dataframe['basic_ub'].iloc[i]
        
        if dataframe['Close'].iloc[i - 1] >= dataframe['final_lb'].iloc[i - 1]:
            dataframe.loc[dataframe.index[i], 'final_lb'] = max(dataframe['basic_lb'].iloc[i], dataframe['final_lb'].iloc[i - 1])
        else:
            dataframe.loc[dataframe.index[i], 'final_lb'] = dataframe['basic_lb'].iloc[i]
    
    dataframe['supertrend'] = np.where(close <= dataframe['final_ub'], dataframe['final_ub'], dataframe['final_lb'])
    
    return dataframe  # Eklenen satır


# Dictionary to store last signals
last_signals = {market['symbol']: None for market in markets}

# Function to wait until the next half-hour mark
def wait_for_next_half_hour():
    now = datetime.now()
    next_half_hour = now.replace(minute=30, second=0, microsecond=0) if now.minute < 30 else (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    wait_seconds = (next_half_hour - now).total_seconds()
    time.sleep(max(wait_seconds, 0))

# Main loop
first_run = True
while True:
    # Perform the analysis immediately on the first run
    if not first_run:
        # Wait for the next half-hour interval
        wait_for_next_half_hour()
    
    first_run = False

    terminal_output = []  # Add this line
    
    for market in markets:
        for timeframe in timeframes:
            try:
                # Retrieve data without progress bar
                symbol = market['symbol']
                data = yf.download(symbol, period=period, interval=timeframe, progress=False)
                
                if data.empty:
                    raise ValueError("Data not available")

                # Calculate Supertrend
                df = calculate_supertrend(data)
                
                # Get closing price and Supertrend value
                closing_price = df['Close'].iloc[-1]
                supertrend_value = df['supertrend'].iloc[-1]
                
                # Determine current signal
                if closing_price > supertrend_value:
                    current_signal = "LONG"
                else:
                    current_signal = "SHORT"
                
                # Check if the signal has changed
                if current_signal != last_signals[symbol]:
                    last_signals[symbol] = current_signal
                    subject = "{} ({}): Supertrend {} signal!".format(symbol, timeframe, current_signal)
                    body = "{} ({}): Supertrend {} signal detected at closing price: ${:.2f}".format(symbol, timeframe, current_signal, closing_price)
                    send_email(subject, body)
                    # Format the terminal message
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    terminal_message = [symbol, current_time, "${:.2f}".format(closing_price), "Supertrend {} signal!".format(current_signal), f"E-posta gönderildi: {current_time}"]
                    terminal_output.append(terminal_message)  # Add this line
                else:
                    # Format the terminal message for the same signal
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    terminal_message = [symbol, current_time, "${:.2f}".format(closing_price), "Supertrend {} signal!".format(current_signal), f"E-posta gönderildi: {current_time}"]
                    terminal_output.append(terminal_message)  # Add this line
                
            except Exception as e:
                print('Error:', e)
    
    # Print the table with aligned columns using tabulate
    print(tabulate(terminal_output, headers=["Symbol", "DateTime", "Last Price", "Signal", "Email Status"], tablefmt="plain"))  # Add this line
