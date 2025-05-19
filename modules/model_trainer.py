# modules/model_trainer.py
import optuna
import xgboost as xgb
import shap
import pandas as pd
import numpy as np
import sqlite3
import joblib
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_squared_error, classification_report
from .logger import Logger

class ModelTrainer:
    def __init__(self, commodity: str, logger: Logger = None):
        self.commodity = commodity
        self.logger = logger or Logger()
        self.conn = sqlite3.connect('data/database.db')
        self.best_params = None
        self.feature_importance = None
        self.shap_explainer = None

    def load_data(self) -> tuple:
        """Veritabanından temizlenmiş verileri yükler"""
        try:
            query = f"""
                SELECT * FROM cleaned_data 
                WHERE commodity='{self.commodity}'
                ORDER BY timestamp
            """
            df = pd.read_sql(query, self.conn)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            
            # Özellikler ve hedef değişken
            X = df.drop(['signal', 'commodity'], axis=1)
            y = df['signal']  # 1: Long, 0: Short
            
            self.logger.info(f"Loaded {len(X)} samples for {self.commodity}")
            return X, y
            
        except Exception as e:
            self.logger.error(f"Data loading failed: {str(e)}", "MODEL_TRAINER")
            return None, None

    def objective(self, trial: optuna.Trial, X: pd.DataFrame, y: pd.Series) -> float:
        """Optuna için optimizasyon hedef fonksiyonu"""
        params = {
            'objective': 'binary:logistic',
            'eval_metric': 'logloss',
            'booster': trial.suggest_categorical('booster', ['gbtree', 'dart']),
            'lambda': trial.suggest_float('lambda', 1e-8, 1.0, log=True),
            'alpha': trial.suggest_float('alpha', 1e-8, 1.0, log=True),
            'max_depth': trial.suggest_int('max_depth', 3, 9),
            'eta': trial.suggest_float('eta', 1e-3, 0.3, log=True),
            'gamma': trial.suggest_float('gamma', 1e-8, 1.0),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
        }
        
        tscv = TimeSeriesSplit(n_splits=5)
        scores = []
        
        for train_idx, val_idx in tscv.split(X):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            
            model = xgb.XGBClassifier(**params)
            model.fit(X_train, y_train,
                      eval_set=[(X_val, y_val)],
                      verbose=False)
            
            preds = model.predict_proba(X_val)[:, 1]
            rmse = mean_squared_error(y_val, preds, squared=False)
            scores.append(rmse)
        
        return np.mean(scores)

    def optimize_hyperparameters(self, X: pd.DataFrame, y: pd.Series, n_trials: int = 100) -> dict:
        """Hiperparametre optimizasyonu çalıştır"""
        study = optuna.create_study(direction='minimize')
        study.optimize(lambda trial: self.objective(trial, X, y), n_trials=n_trials)
        
        self.best_params = study.best_params
        self.logger.info(f"Optimization completed. Best params: {self.best_params}", "MODEL_TRAINER")
        return study.best_params

    def train_final_model(self, X: pd.DataFrame, y: pd.Series) -> xgb.XGBClassifier:
        """Son modeli eğit ve SHAP analizi yap"""
        model = xgb.XGBClassifier(**self.best_params)
        model.fit(X, y)
        
        # SHAP analizi
        explainer = shap.Explainer(model, X)
        shap_values = explainer(X)
        
        # Özellik önemini kaydet
        self.feature_importance = pd.DataFrame({
            'feature': X.columns,
            'importance': model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        # SHAP değerlerini sakla
        self.shap_explainer = explainer
        joblib.dump(explainer, f'models/shap_explainer_{self.commodity}.pkl')
        
        # Görselleştirme
        shap.summary_plot(shap_values, X, show=False)
        plt.savefig(f'models/shap_summary_{self.commodity}.png')
        plt.close()
        
        return model

    def evaluate_model(self, model: xgb.XGBClassifier, X: pd.DataFrame, y: pd.Series) -> dict:
        """Model performansını değerlendir"""
        preds = model.predict(X)
        report = classification_report(y, preds, output_dict=True)
        
        metrics = {
            'accuracy': report['accuracy'],
            'precision': report['weighted avg']['precision'],
            'recall': report['weighted avg']['recall'],
            'f1': report['weighted avg']['f1-score']
        }
        
        self.logger.info(f"Model evaluation: {metrics}", "MODEL_TRAINER")
        return metrics

    def full_pipeline(self) -> bool:
        """Tüm eğitim pipeline'ını çalıştır"""
        X, y = self.load_data()
        if X is None:
            return False
            
        self.optimize_hyperparameters(X, y)
        model = self.train_final_model(X, y)
        metrics = self.evaluate_model(model, X, y)
        
        # Modeli ve özellik önemini kaydet
        joblib.dump(model, f'models/xgboost_model_{self.commodity}.pkl')
        self.feature_importance.to_csv(f'models/feature_importance_{self.commodity}.csv', index=False)
        
        return True

# Örnek kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    trainer = ModelTrainer('BTCUSDT', logger)
    
    if trainer.full_pipeline():
        print("Model training completed successfully!")
        print(f"Best parameters: {trainer.best_params}")
        print(f"Feature importance:\n{trainer.feature_importance.head()}")
    else:
        print("Model training failed!")