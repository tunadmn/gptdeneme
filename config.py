# config.py
import os
from dotenv import load_dotenv
from typing import Dict, Any

# .env dosyasını yükle
load_dotenv()

def get_env(key: str, default: Any = None, type_cast: type = str) -> Any:
    """Tip dönüşümlü çevre değişkeni okuyucu"""
    value = os.getenv(key, default)
    return type_cast(value) if value is not None else None

# API Anahtarları
API_KEYS: Dict[str, str] = {
    'binance': get_env('BINANCE_API_KEY', ''),
    'alphavantage': get_env('ALPHAVANTAGE_API_KEY', ''),
    'twelvedata': get_env('TWELVEDATA_API_KEY', ''),
    'financialmodelingprep': get_env('FMP_API_KEY', '')
}

# Genel Ayarlar
GENERAL_SETTINGS: Dict[str, Any] = {
    'timezone': get_env('TIMEZONE', 'Europe/Istanbul'),
    'database_path': get_env('DATABASE_PATH', os.path.join('data', 'database.db')),
    'log_settings': {
        'max_log_size': get_env('LOG_MAX_SIZE', 10_485_760, int),
        'backup_count': get_env('LOG_BACKUP_COUNT', 3, int),
        'log_file': get_env('LOG_FILE', os.path.join('logs', 'app_log.json'))
    }
}

# Model Parametreleri
MODEL_PARAMS: Dict[str, Any] = {
    'signal_timeframes': get_env('SIGNAL_TIMEFRAMES', '5T,15T,60T,240T').split(','),
    'arima_order': tuple(map(int, get_env('ARIMA_ORDER', '1,1,1').split(','))),
    'atr_period': get_env('ATR_PERIOD', 14, int),
    'atr_multiplier': get_env('ATR_MULTIPLIER', 2.0, float),
    'risk_thresholds': {
        'high': get_env('RISK_HIGH', 6.0, float),
        'medium': get_env('RISK_MEDIUM', 3.0, float)
    }
}

# API Limitleri (Dakikada)
API_LIMITS: Dict[str, Dict[str, int]] = {
    'binance': {
        'requests': get_env('BINANCE_REQ_LIMIT', 1200, int),
        'weight': get_env('BINANCE_WEIGHT_LIMIT', 1200, int)
    },
    'alphavantage': {
        'requests': get_env('ALPHAVANTAGE_REQ_LIMIT', 5, int),
        'weight': get_env('ALPHAVANTAGE_WEIGHT_LIMIT', 300, int)
    },
    'twelvedata': {
        'requests': get_env('TWELVEDATA_REQ_LIMIT', 800, int),
        'weight': get_env('TWELVEDATA_WEIGHT_LIMIT', 800, int)
    }
}

# Geliştirici Uyarısı
if all(v == '' for v in API_KEYS.values()):
    import logging
    logging.warning("API anahtarları tanımlanmamış! Lütfen .env dosyasını kontrol edin.")