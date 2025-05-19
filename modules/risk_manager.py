# modules/risk_manager.py
import sqlite3
import numpy as np
import pandas as pd
from typing import Optional, Tuple
from .logger import Logger
from .sentiment_analyzer import SentimentAnalyzer
from .economic_calendar import EconomicCalendar

class RiskManager:
    def __init__(self, commodity: str, logger: Logger = None):
        self.commodity = commodity
        self.logger = logger or Logger()
        self.conn = sqlite3.connect('data/database.db')
        self.sentiment_analyzer = SentimentAnalyzer()
        self.economic_calendar = EconomicCalendar()

    def calculate_kelly_position(self, win_prob: float, win_loss_ratio: float) -> float:
        """Kelly Criterion ile pozisyon büyüklüğü hesapla"""
        try:
            if win_prob <= 0 or win_loss_ratio <= 0:
                return 0.0
                
            kelly_f = (win_prob * (win_loss_ratio + 1) - 1) / win_loss_ratio
            return max(0.0, min(kelly_f, 1.0))  # 0-1 arasında sınırla
            
        except Exception as e:
            self.logger.error(f"Kelly calculation failed: {str(e)}", "RISK_MANAGER")
            return 0.0

    def calculate_atr_stop_loss(self, period: int = 14, multiplier: float = 2.0) -> Tuple[float, float]:
        """ATR tabanlı dinamik stop-loss seviyesi"""
        try:
            query = f"""
                SELECT high, low, close 
                FROM cleaned_data 
                WHERE commodity='{self.commodity}'
                ORDER BY timestamp DESC 
                LIMIT {period + 1}
            """
            df = pd.read_sql(query, self.conn)
            
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            atr = tr.rolling(period).mean().iloc[-1]
            
            current_price = df['close'].iloc[-1]
            stop_loss_long = current_price - (multiplier * atr)
            stop_loss_short = current_price + (multiplier * atr)
            
            return round(stop_loss_long, 4), round(stop_loss_short, 4)
            
        except Exception as e:
            self.logger.error(f"ATR calculation failed: {str(e)}", "RISK_MANAGER")
            return 0.0, 0.0

    def analyze_user_prediction(self, entry_price: float, prediction_type: str) -> dict:
        """Kullanıcı tahmininin risk analizini yap"""
        try:
            # Mevcut piyasa verilerini al
            query = f"""
                SELECT close, volatility 
                FROM cleaned_data 
                WHERE commodity='{self.commodity}'
                ORDER BY timestamp DESC 
                LIMIT 1
            """
            current_data = pd.read_sql(query, self.conn).iloc[0]
            current_price = current_data['close']
            volatility = current_data['volatility']
            
            # Fiyat farkını volatiliteye göre normalize et
            price_diff = abs(current_price - entry_price)
            risk_score = min(price_diff / (volatility * 2), 3.0)  # 3x volatilite
            
            # Risk seviyesi
            if risk_score < 0.5:
                risk_level = 'Low'
            elif risk_score < 1.5:
                risk_level = 'Medium'
            else:
                risk_score = min(risk_score, 3.0)  # Maks 3.0
                risk_level = 'High'
            
            return {
                'current_price': current_price,
                'entry_diff': round(price_diff, 4),
                'volatility': round(volatility, 4),
                'risk_score': round(risk_score, 2),
                'risk_level': risk_level,
                'recommendation': 'Long' if prediction_type == 'Long' and current_price < entry_price else 'Short'
            }
            
        except Exception as e:
            self.logger.error(f"Prediction analysis failed: {str(e)}", "RISK_MANAGER")
            return {}

    def news_based_risk_adjustment(self, position_size: float) -> float:
        """Haber ve ekonomik takvim riskine göre pozisyon ayarla"""
        try:
            # Son 24 saat haber duygu analizi
            sentiment_score = self.sentiment_analyzer.get_recent_sentiment(self.commodity, hours=24)
            
            # Yaklaşan yüksek riskli etkinlikler
            high_risk_events = self.economic_calendar.get_high_risk_events(threshold=6.0)
            event_risk = len(high_risk_events[high_risk_events['currency'] == self.commodity[:3]])
            
            # Risk modifikasyon faktörleri
            sentiment_factor = max(0.5, 1.0 - (0.2 * (1.0 - sentiment_score)))  # Duygu 0-1 arası
            event_factor = max(0.3, 1.0 - (0.1 * event_risk))
            
            adjusted_size = position_size * sentiment_factor * event_factor
            return min(adjusted_size, 1.0)
            
        except Exception as e:
            self.logger.error(f"News risk adjustment failed: {str(e)}", "RISK_MANAGER")
            return position_size

    def calculate_total_risk(self, win_prob: float, win_loss_ratio: float, 
                           entry_price: Optional[float] = None) -> dict:
        """Tüm risk parametrelerini birleştiren ana fonksiyon"""
        kelly_size = self.calculate_kelly_position(win_prob, win_loss_ratio)
        stop_losses = self.calculate_atr_stop_loss()
        
        risk_report = {
            'kelly_position': round(kelly_size, 2),
            'stop_loss_long': stop_losses[0],
            'stop_loss_short': stop_losses[1],
            'news_adjusted_position': self.news_based_risk_adjustment(kelly_size)
        }
        
        if entry_price is not None:
            prediction_analysis = self.analyze_user_prediction(entry_price, 'Long')
            risk_report.update(prediction_analysis)
            risk_report['final_position'] = risk_report['news_adjusted_position'] * (
                1.0 - (risk_report['risk_score'] / 3.0)
            )
        else:
            risk_report['final_position'] = risk_report['news_adjusted_position']
            
        return risk_report

# Örnek kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    risk_mgr = RiskManager('BTCUSDT', logger)
    
    # Kelly pozisyon boyutu
    print(f"Kelly Position: {risk_mgr.calculate_kelly_position(0.55, 1.5):.2%}")
    
    # Stop-loss seviyeleri
    sl_long, sl_short = risk_mgr.calculate_atr_stop_loss()
    print(f"Stop Loss Levels - Long: {sl_long}, Short: {sl_short}")
    
    # Kullanıcı tahmin analizi
    prediction_risk = risk_mgr.analyze_user_prediction(45000.0, 'Long')
    print("\nPrediction Risk Analysis:")
    print(prediction_risk)
    
    # Tam risk raporu
    full_risk_report = risk_mgr.calculate_total_risk(
        win_prob=0.6,
        win_loss_ratio=1.8,
        entry_price=45200.0
    )
    print("\nFull Risk Report:")
    print(full_risk_report)