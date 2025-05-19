# modules/data_cleaner.py
import sqlite3
import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from statsmodels.tsa.arima.model import ARIMA
import logging

class DataCleaner:
    def __init__(self, db_path='data/database.db', logger=None):
        self.db_path = db_path
        self.logger = logger or logging.getLogger(__name__)
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        
    def load_raw_data(self, commodity_name):
        """Ham verileri veritabanından yükler"""
        try:
            query = f"SELECT * FROM raw_data WHERE commodity='{commodity_name}'"
            df = pd.read_sql(query, self.conn)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            self.logger.info(f"Raw data loaded for {commodity_name}")
            return df
        except Exception as e:
            self.logger.error(f"Data loading failed: {str(e)}")
            return None

    def clean_data(self, commodity_name):
        """Tüm temizleme pipeline'ını çalıştırır"""
        raw_df = self.load_raw_data(commodity_name)
        if raw_df is None:
            return False

        # Eksik verileri impute et
        df_imputed = self._impute_missing_with_arima(raw_df)
        
        # Aykırı değerleri temizle
        cleaned_df, outlier_mask = self._detect_outliers_with_dbscan(df_imputed)
        
        # Temizlenmiş veriyi kaydet
        self._save_cleaned_data(cleaned_df, commodity_name)
        return True

    def _impute_missing_with_arima(self, df):
        """ARIMA ile eksik veri tahmini"""
        for column in df.columns:
            if df[column].isna().sum() > 0:
                try:
                    model = ARIMA(df[column], order=(1,1,1))
                    model_fit = model.fit()
                    predictions = model_fit.predict(start=df.index[0], end=df.index[-1])
                    df[column].fillna(predictions, inplace=True)
                    self.logger.info(f"ARIMA imputation done for {column}")
                except Exception as e:
                    self.logger.warning(f"ARIMA failed for {column}: {str(e)}")
        return df

    def _detect_outliers_with_dbscan(self, df, eps=0.5, min_samples=5):
        """DBSCAN ile aykırı değer tespiti"""
        numeric_df = df.select_dtypes(include=[np.number])
        clustering = DBSCAN(eps=eps, min_samples=min_samples).fit(numeric_df)
        outlier_mask = clustering.labels_ == -1
        cleaned_df = df[~outlier_mask]
        self.logger.info(f"Outliers removed: {outlier_mask.sum()} points")
        return cleaned_df, outlier_mask

    def _save_cleaned_data(self, df, commodity_name):
        """Temizlenmiş veriyi veritabanına kaydet"""
        try:
            df.reset_index(inplace=True)
            df['commodity'] = commodity_name
            df.to_sql('cleaned_data', self.conn, if_exists='append', index=False)
            self.conn.commit()
            self.logger.info(f"Cleaned data saved for {commodity_name}")
        except Exception as e:
            self.logger.error(f"Data saving failed: {str(e)}")
            self.conn.rollback()

    def __del__(self):
        """Veritabanı bağlantısını kapat"""
        self.conn.close()

# Örnek kullanım
if __name__ == "__main__":
    from logger import Logger  # Projenize özel logger modülünüz
    
    logger = Logger(log_file='logs/app_log.json')
    cleaner = DataCleaner(db_path='data/database.db', logger=logger)
    cleaner.clean_data('BTCUSDT')