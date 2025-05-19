# modules/signal_generator.py
import pandas as pd
import numpy as np
import sqlite3
import logging
from datetime import datetime, timedelta
from statsmodels.tsa.stattools import adfuller
from logger import Logger
from modules.data_cleaner import DataCleaner
from modules.model_trainer import ModelTrainer

class SignalGenerator:
    def __init__(self, commodity: str, logger: Logger = None):
        self.commodity = commodity
        self.logger = logger or Logger()
        self.conn = sqlite3.connect('data/database.db')
        self.data_cleaner = DataCleaner()
        self.model_trainer = ModelTrainer(commodity)

    def load_historical_data(self, timeframe: str = '5T') -> pd.DataFrame:
        """Temizlenmiş verileri zaman dilimine göre yükle"""
        try:
            query = f"""
                SELECT * FROM cleaned_data 
                WHERE commodity='{self.commodity}'
                ORDER BY timestamp
            """
            df = pd.read_sql(query, self.conn)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Zaman dilimine göre resample
            ohlc_dict = {
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }
            return df.resample(timeframe).apply(ohlc_dict).dropna()
            
        except Exception as e:
            self.logger.error(f"Data loading failed: {str(e)}", "SIGNAL_GENERATOR")
            return pd.DataFrame()

    def calculate_technical_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Teknik göstergeleri hesapla"""
        # Bollinger Bantları
        df['ma20'] = df['close'].rolling(20).mean()
        df['stddev'] = df['close'].rolling(20).std()
        df['upper_band'] = df['ma20'] + (df['stddev'] * 2)
        df['lower_band'] = df['ma20'] - (df['stddev'] * 2)
        
        # MACD
        df['ema12'] = df['close'].ewm(span=12, adjust=False).mean()
        df['ema26'] = df['close'].ewm(span=26, adjust=False).mean()
        df['macd'] = df['ema12'] - df['ema26']
        df['signal'] = df['macd'].ewm(span=9, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['rsi'] = 100 - (100 / (1 + (gain / loss)))
        
        # Heikin-Ashi
        df['ha_close'] = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open = (df['open'].shift(1) + df['close'].shift(1)) / 2
        df['ha_open'] = ha_open
        df['ha_high'] = df[['high', 'ha_open', 'ha_close']].max(axis=1)
        df['ha_low'] = df[['low', 'ha_open', 'ha_close']].min(axis=1)
        
        return df.dropna()

    def detect_market_regime(self, df: pd.DataFrame) -> str:
        """Piyasa rejimini belirle (Trending/Range-bound)"""
        # ADF Testi ile stationarity kontrolü
        adf_result = adfuller(df['close'])
        
        # Bollinger Bantları daralma kontrolü
        bandwidth = (df['upper_band'].iloc[-1] - df['lower_band'].iloc[-1]) / df['ma20'].iloc[-1]
        
        if adf_result[1] < 0.05 and bandwidth < 0.1:
            return "Range-bound"
        else:
            return "Trending"

    def generate_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """ML modeli için özellik mühendisliği"""
        df['momentum'] = df['close'].pct_change(periods=5)
        df['volatility'] = df['close'].rolling(20).std()
        df['volume_change'] = df['volume'].pct_change()
        df['ma_cross'] = (df['ma20'] > df['ma50']).astype(int)
        
        # Lag özellikleri
        for lag in [1, 3, 5]:
            df[f'return_{lag}'] = df['close'].pct_change(lag)
            
        return df.dropna()

    def generate_signals(self, timeframe: str = '5T') -> dict:
        """Tüm sinyal üretim pipeline'ını çalıştır"""
        try:
            raw_df = self.load_historical_data(timeframe)
            if raw_df.empty:
                return {}
                
            df = self.calculate_technical_indicators(raw_df)
            df = self.generate_features(df)
            
            # Model tahmini
            model = self.model_trainer.load_model()
            features = df.drop(['commodity', 'signal'], axis=1, errors='ignore')
            df['prediction'] = model.predict_proba(features)[:, 1]
            
            # Sinyal oluşturma
            last_row = df.iloc[-1]
            signal = "Long" if last_row['prediction'] > 0.7 else "Short" if last_row['prediction'] < 0.3 else "Hold"
            
            # Piyasa rejimi
            regime = self.detect_market_regime(df)
            
            # Risk seviyesi
            risk_level = "High" if last_row['volatility'] > 0.03 else "Medium" if last_row['volatility'] > 0.015 else "Low"
            
            # SHAP açıklamaları
            explainer = self.model_trainer.load_shap_explainer()
            shap_values = explainer.shap_values(features.iloc[-1:])
            top_features = pd.Series(shap_values[0], index=features.columns).abs().nlargest(3).index.tolist()
            
            return {
                'timestamp': datetime.now().isoformat(),
                'commodity': self.commodity,
                'timeframe': timeframe,
                'signal': signal,
                'probability': round(last_row['prediction'], 2),
                'regime': regime,
                'risk_level': risk_level,
                'price': round(last_row['close'], 4),
                'top_features': top_features
            }
            
        except Exception as e:
            self.logger.error(f"Signal generation failed: {str(e)}", "SIGNAL_GENERATOR")
            return {}

    def save_signals_to_db(self, signal_data: dict) -> bool:
        """Sinyalleri veritabanına kaydet"""
        try:
            df = pd.DataFrame([signal_data])
            df.to_sql('signals', self.conn, if_exists='append', index=False)
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Signal save failed: {str(e)}", "SIGNAL_GENERATOR")
            self.conn.rollback()
            return False

# Örnek kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    sg = SignalGenerator('BTCUSDT', logger)
    
    # 15 dakikalık zaman dilimi için sinyal üret
    signal = sg.generate_signals('15T')
    print("Üretilen Sinyal:")
    print(signal)
    
    # Veritabanına kaydet
    sg.save_signals_to_db(signal)