# modules/sentiment_analyzer.py
import requests
import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime, timedelta
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from logger import Logger
from config import API_KEYS
from typing import List, Dict

class SentimentAnalyzer:
    def __init__(self, logger: Logger = None, model_name: str = "ProsusAI/finbert"):
        self.logger = logger or Logger()
        self.conn = sqlite3.connect('data/database.db')
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.nlp_pipeline = pipeline("text-classification", 
                                   model=self.model, 
                                   tokenizer=self.tokenizer,
                                   return_all_scores=True)

    def fetch_financial_news(self, commodity: str) -> List[Dict]:
        """AlphaVantage API'den finansal haberleri çek"""
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': commodity,
                'apikey': API_KEYS['alphavantage'],
                'limit': 50  # Maksimum desteklenen limit
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            raw_data = response.json()
            
            return raw_data.get('feed', [])
            
        except Exception as e:
            self.logger.error(f"News fetch failed: {str(e)}", "SENTIMENT_ANALYZER")
            return []

    def _preprocess_text(self, text: str) -> str:
        """Haber metnini FinBERT için optimize şekilde temizle"""
        text = text[:512]  # BERT maksimum uzunluk
        return text.replace("$", "").replace("\n", " ").strip()

    def analyze_sentiment(self, news_list: List[Dict]) -> pd.DataFrame:
        """Haber listesi üzerinde toplu duygu analizi yap"""
        results = []
        
        for news in news_list:
            try:
                text = self._preprocess_text(news.get('title', '') + ". " + news.get('summary', ''))
                sentiment_result = self.nlp_pipeline(text)[0]
                
                scores = {item['label']: item['score'] for item in sentiment_result}
                overall_sentiment = max(scores, key=scores.get)
                
                news_entry = {
                    'timestamp': pd.to_datetime(news.get('time_published', datetime.utcnow())),
                    'title': news.get('title', ''),
                    'url': news.get('url', ''),
                    'sentiment': overall_sentiment,
                    'positive_score': scores['positive'],
                    'negative_score': scores['negative'],
                    'neutral_score': scores['neutral'],
                    'related_tickers': ','.join([item['ticker'] for item in news.get('ticker_sentiment', [])])
                }
                
                results.append(news_entry)
                
            except Exception as e:
                self.logger.warning(f"News analysis failed: {str(e)}", "SENTIMENT_ANALYZER")
        
        return pd.DataFrame(results)

    def save_to_database(self, df: pd.DataFrame, commodity: str) -> None:
        """Analiz sonuçlarını veritabanına kaydet"""
        try:
            df['commodity'] = commodity
            df.to_sql('news_sentiment', self.conn, 
                     if_exists='append', index=False)
            self.conn.commit()
            self.logger.info(f"Saved {len(df)} news entries for {commodity}", "SENTIMENT_ANALYZER")
        except Exception as e:
            self.logger.error(f"Database save failed: {str(e)}", "SENTIMENT_ANALYZER")
            self.conn.rollback()

    def get_recent_sentiment(self, commodity: str, hours: int = 24) -> float:
        """Son X saatlik ortalama pozitif duygu skorunu getir"""
        try:
            query = f"""
                SELECT AVG(positive_score) as avg_score 
                FROM news_sentiment 
                WHERE commodity='{commodity}' 
                AND timestamp >= datetime('now', '-{hours} hours')
            """
            result = pd.read_sql(query, self.conn)
            return result['avg_score'].iloc[0] or 0.5  # Default neutral
            
        except Exception as e:
            self.logger.error(f"Sentiment query failed: {str(e)}", "SENTIMENT_ANALYZER")
            return 0.5

    def full_pipeline(self, commodity: str) -> float:
        """Tüm haber işlem pipeline'ını çalıştır"""
        news_data = self.fetch_financial_news(commodity)
        if not news_data:
            return 0.5
            
        analyzed_df = self.analyze_sentiment(news_data)
        self.save_to_database(analyzed_df, commodity)
        
        return analyzed_df['positive_score'].mean()

    def __del__(self):
        """Veritabanı bağlantısını kapat"""
        self.conn.close()

# Örnek kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    analyzer = SentimentAnalyzer(logger)
    
    # BTC haberlerini analiz et ve skor hesapla
    btc_sentiment = analyzer.full_pipeline('BTC')
    print(f"Son 24 saatlik ortalama pozitif skor: {btc_sentiment:.2f}")
    
    # Veritabanından son skoru getir
    recent_score = analyzer.get_recent_sentiment('BTC', hours=6)
    print(f"Son 6 saatlik skor: {recent_score:.2f}")