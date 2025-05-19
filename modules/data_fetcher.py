# modules/data_fetcher.py
import requests
import pandas as pd
import sqlite3
import threading
import time
from config import API_KEYS
from .logger import Logger

class DataFetcher:
    def __init__(self):
        self.logger = Logger(log_file='logs/app_log.json')
        self.conn = sqlite3.connect('data/database.db')
        self.api_usage = {
            'binance': {'limit': 1200, 'remaining': 1200, 'reset_time': None},
            'alphavantage': {'limit': 500, 'remaining': 500, 'reset_time': None},
            'twelvedata': {'limit': 800, 'remaining': 800, 'reset_time': None}
        }
        self.lock = threading.Lock()

    def _update_api_counter(self, api_name):
        """API çağrı limitlerini günceller"""
        with self.lock:
            self.api_usage[api_name]['remaining'] -= 1
            if self.api_usage[api_name]['remaining'] <= 0:
                reset_time = time.time() + 3600  # 1 saat sonra reset
                self.api_usage[api_name].update({'remaining': self.api_usage[api_name]['limit'], 
                                               'reset_time': reset_time})
                self.logger.warning(f"{api_name} API limit reached! Resets at {reset_time}")

    def _save_raw_data(self, df, commodity):
        """Ham verileri veritabanına kaydeder"""
        try:
            df['commodity'] = commodity
            df['fetch_time'] = pd.Timestamp.now()
            df.to_sql('raw_data', self.conn, if_exists='append', index=False)
            self.conn.commit()
        except Exception as e:
            self.logger.error(f"Database save failed: {str(e)}")
            self.conn.rollback()

    def fetch_binance_data(self, symbol, interval='1m', limit=500):
        """Binance'den kaldıraçlı işlem verilerini çeker"""
        try:
            url = "https://fapi.binance.com/fapi/v1/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': limit
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            self._update_api_counter('binance')
            
            data = response.json()
            df = pd.DataFrame(data, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_volume', 'trades', 'taker_buy_volume',
                'taker_buy_quote_volume', 'ignore'
            ])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
        except Exception as e:
            self.logger.error(f"Binance fetch error: {str(e)}")
            return None

    def fetch_alphavantage_data(self, symbol):
        """AlphaVantage'den temel verileri çeker"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'TIME_SERIES_INTRADAY',
                'symbol': symbol,
                'interval': '1min',
                'apikey': API_KEYS['alphavantage'],
                'outputsize': 'full'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            self._update_api_counter('alphavantage')
            
            data = response.json()['Time Series (1min)']
            df = pd.DataFrame.from_dict(data, orient='index')
            df.index = pd.to_datetime(df.index)
            df.columns = ['open', 'high', 'low', 'close', 'volume']
            return df.reset_index().rename(columns={'index': 'timestamp'})
            
        except Exception as e:
            self.logger.error(f"AlphaVantage fetch error: {str(e)}")
            return None

    def fetch_twelvedata_data(self, symbol):
        """TwelveData'dan emtia verilerini çeker"""
       