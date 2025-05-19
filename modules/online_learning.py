# modules/online_learning.py
import sqlite3
import pandas as pd
import numpy as np
import joblib
from datetime import datetime, timedelta
from river import compose, linear_model, preprocessing, drift
from logger import Logger

class OnlineLearner:
    def __init__(self, commodity: str, logger: Logger = None):
        self.commodity = commodity
        self.logger = logger or Logger()
        self.conn = sqlite3.connect('data/database.db')
        
        # Model ve drift dedektörü
        self.model = self._init_online_model()
        self.drift_detector = drift.ADWIN()
        self.last_train_time = datetime.now()
        
        # Önceden eğitilmiş XGBoost modeli
        self.base_model = joblib.load(f'models/xgboost_model_{commodity}.pkl')
        
    def _init_online_model(self):
        """River pipeline'ını oluştur"""
        return compose.Pipeline(
            preprocessing.StandardScaler(),
            linear_model.LogisticRegression()
        )
    
    def _fetch_new_data(self, last_timestamp: datetime) -> pd.DataFrame:
        """Son kayıttan itibaren yeni verileri çek"""
        query = f"""
            SELECT * FROM cleaned_data 
            WHERE commodity='{self.commodity}' 
            AND timestamp > '{last_timestamp}'
            ORDER BY timestamp
        """
        return pd.read_sql(query, self.conn)
    
    def _preprocess_for_river(self, X: pd.Series) -> dict:
        """Pandas Series'ı River formatına dönüştür"""
        return X.to_dict()
    
    def _predict_and_learn(self, X: dict, y: float) -> None:
        """Online modeli güncelle"""
        self.model = self.model.learn_one(X, y)
        
        # Concept drift kontrolü
        error = abs(y - self.model.predict_proba_one(X).get(1, 0.5))
        self.drift_detector.update(error)
        
        if self.drift_detector.drift_detected:
            self.logger.warning(
                f"Concept drift detected in {self.commodity}! Resetting model...",
                "ONLINE_LEARNING"
            )
            self._handle_concept_drift()
    
    def _handle_concept_drift(self) -> None:
        """Drift durumunda yeni model başlat ve uyarı gönder"""
        # Mevcut modelin performansını kaydet
        joblib.dump(self.model, f'models/drifted_model_{self.commodity}_{datetime.now().timestamp()}.pkl')
        
        # Yeni model başlat
        self.model = self._init_online_model()
        self.drift_detector.reset()
        
    def _hybrid_predict(self, X: pd.DataFrame) -> np.ndarray:
        """XGBoost ve online modelin ensemble tahmini"""
        online_preds = np.array([self.model.predict_proba_one(self._preprocess_for_river(row))[1] 
                             for _, row in X.iterrows()])
        xgb_preds = self.base_model.predict_proba(X)[:, 1]
        return (online_preds + xgb_preds) / 2
    
    def process_new_data(self, batch_size: int = 100) -> None:
        """Yeni veriler üzerinde online öğrenme uygula"""
        try:
            # Son işlem zamanını kontrol et
            new_data = self._fetch_new_data(self.last_train_time)
            if new_data.empty:
                return
                
            # Özellikler ve hedef
            X = new_data.drop(['signal', 'commodity', 'timestamp'], axis=1)
            y = new_data['signal']
            
            # Hibrit tahmin yap
            predictions = self._hybrid_predict(X)
            
            # Online modeli güncelle
            for idx, row in X.iterrows():
                river_X = self._preprocess_for_river(row)
                self._predict_and_learn(river_X, y.iloc[idx])
            
            # Modeli periyodik olarak kaydet
            if (datetime.now() - self.last_train_time) > timedelta(hours=1):
                joblib.dump(self.model, f'models/online_model_{self.commodity}.pkl')
                self.last_train_time = datetime.now()
                self.logger.info(f"Online model saved for {self.commodity}", "ONLINE_LEARNING")
            
            return predictions
            
        except Exception as e:
            self.logger.error(f"Online learning failed: {str(e)}", "ONLINE_LEARNING")
            return None

# Örnek kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    learner = OnlineLearner('BTCUSDT', logger)
    
    # Simüle edilmiş gerçek zamanlı veri akışı
    while True:
        predictions = learner.process_new_data()
        if predictions is not None:
            print(f"Processed {len(predictions)} new samples")
            print(f"Current drift warning count: {learner.drift_detector.n_warnings}")
            
        time.sleep(60)  # 1 dakikada bir kontrol