# modules/economic_calendar.py
import requests
import pandas as pd
import sqlite3
from datetime import datetime, timedelta
from config import API_KEYS
from .logger import Logger
from typing import Dict, List

class EconomicCalendar:
    def __init__(self):
        self.logger = Logger(log_file='logs/app_log.json')
        self.conn = sqlite3.connect('data/database.db')
        self.base_url = "https://financialmodelingprep.com/api/v3/economic_calendar"
        self.headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    def fetch_economic_events(self, days_ahead: int = 7) -> pd.DataFrame:
        """Belirtilen gün aralığındaki ekonomik etkinlikleri çeker"""
        try:
            start_date = datetime.now().strftime("%Y-%m-%d")
            end_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
            
            params = {
                'from': start_date,
                'to': end_date,
                'apikey': API_KEYS['financialmodelingprep']
            }

            response = requests.get(
                self.base_url,
                params=params,
                headers=self.headers,
                timeout=10
            )
            response.raise_for_status()
            
            raw_data = response.json()
            processed_df = self._parse_events(raw_data)
            risk_df = self._calculate_event_risk(processed_df)
            self._save_to_database(risk_df)
            
            return risk_df

        except Exception as e:
            self.logger.error(f"Economic calendar fetch failed: {str(e)}")
            return pd.DataFrame()

    def _parse_events(self, raw_data: List[Dict]) -> pd.DataFrame:
        """Ham veriyi işlenebilir DataFrame'e dönüştürür"""
        df = pd.DataFrame(raw_data)[['event', 'date', 'country', 'importance', 'actual', 'previous', 'change']]
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
        df['currency'] = df['country'].apply(lambda x: x.split(' ')[-1])
        df['hours_to_event'] = (df['date'] - pd.Timestamp.now()).dt.total_seconds() / 3600
        return df.dropna()

    def _calculate_event_risk(self, df: pd.DataFrame) -> pd.DataFrame:
        """Etkinlik risk skorunu hesaplar (0-10 arası)"""
        importance_map = {'High': 3, 'Medium': 2, 'Low': 1}
        df['importance_score'] = df['importance'].map(importance_map)
        
        # Risk formülü: (Önem * 3) + (Volatilite * 2) - (Süre * 0.5)
        df['volatility_score'] = abs(df['change'].fillna(0) / 100) # % cinsinden değişim
        df['time_score'] = df['hours_to_event'].apply(lambda x: max(0, 24 - x)/24)  # 24 saat içindeki etkinlikler
        
        df['risk_score'] = (
            (df['importance_score'] * 3) +
            (df['volatility_score'] * 2) +
            (df['time_score'] * 0.5)
        ).round(2)
        
        # Risk seviyesi kategorilendirme
        df['risk_level'] = pd.cut(df['risk_score'],
                               bins=[0, 3, 6, 10],
                               labels=['Low', 'Medium', 'High'])
        
        return df[['event', 'date', 'currency', 'risk_score', 'risk_level', 'actual', 'previous']]

    def _save_to_database(self, df: pd.DataFrame) -> None:
        """Verileri SQLite veritabanına kaydeder"""
        try:
            df.to_sql('economic_calendar', self.conn, 
                     if_exists='replace', index=False)
            self.conn.commit()
            self.logger.info(f"Saved {len(df)} economic events to database")
        except Exception as e:
            self.logger.error(f"Database save error: {str(e)}")
            self.conn.rollback()

    def get_high_risk_events(self, threshold: float = 6.0) -> pd.DataFrame:
        """Risk skoru threshold üstündeki etkinlikleri getirir"""
        query = f"SELECT * FROM economic_calendar WHERE risk_score >= {threshold}"
        return pd.read_sql(query, self.conn)

    def __del__(self):
        """Veritabanı bağlantısını kapat"""
        self.conn.close()

# Örnek kullanım
if __name__ == "__main__":
    calendar = EconomicCalendar()
    events_df = calendar.fetch_economic_events(days_ahead=3)
    
    print("Yaklaşan Yüksek Riskli Etkinlikler:")
    high_risk = calendar.get_high_risk_events()
    print(high_risk[['event', 'date', 'risk_score']].to_string(index=False))