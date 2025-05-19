# modules/logger.py
import json
import logging
import traceback
from datetime import datetime
import threading
from typing import Optional, Dict, Any

class Logger:
    def __init__(self, log_file: str = 'logs/app_log.json', alert_threshold: str = 'CRITICAL'):
        self.log_file = log_file
        self.alert_threshold = alert_threshold
        self.lock = threading.Lock()
        self._setup_logger()

    def _setup_logger(self) -> None:
        """JSON formatter ile temel logger konfigürasyonu"""
        self.logger = logging.getLogger('borsasistan')
        self.logger.setLevel(logging.DEBUG)
        
        # JSON File Handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)

    def log(self, level: str, message: str, module: str, extra: Optional[Dict] = None) -> None:
        """Özelleştirilmiş JSON log kaydı"""
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': level.upper(),
            'module': module,
            'message': message,
            **({'extra': extra} if extra else {})
        }
        
        with self.lock:
            try:
                self.logger.log(getattr(logging, level.upper()), message, extra=log_data)
                self._check_for_alert(log_data)
            except Exception as e:
                print(f"Logging failed: {str(e)}")

    def _check_for_alert(self, log_data: Dict[str, Any]) -> None:
        """Kritik hata durumunda alert tetikle"""
        if log_data['level'] == self.alert_threshold:
            self.trigger_alert(log_data)

    def trigger_alert(self, alert_data: Dict[str, Any]) -> None:
        """UI için alert mesajı üret (UI modülü bu methodu override edecek)"""
        # Base class'ta sadece konsola yazdır
        print(f"! ALERT ! [{alert_data['level']}] {alert_data['message']}")

    def exception_handler(self, exception: Exception, module: str) -> None:
        """Exception logging için optimize edilmiş method"""
        tb = traceback.extract_tb(exception.__traceback__)
        self.log('ERROR', 
                f"{type(exception).__name__}: {str(exception)}",
                module,
                extra={
                    'traceback': [{
                        'file': frame.filename,
                        'line': frame.lineno,
                        'function': frame.name
                    } for frame in tb]
                })

    # Kolay erişim için kısa metodlar
    def info(self, message: str, module: str) -> None:
        self.log('INFO', message, module)

    def warning(self, message: str, module: str) -> None:
        self.log('WARNING', message, module)

    def error(self, message: str, module: str) -> None:
        self.log('ERROR', message, module)

    def critical(self, message: str, module: str) -> None:
        self.log('CRITICAL', message, module)

class JSONFormatter(logging.Formatter):
    """Custom JSON log formatter"""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'module': record.module,
            'message': record.getMessage(),
            **getattr(record, 'extra', {})
        }
        
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
            
        return json.dumps(log_data, ensure_ascii=False)

# Örnek kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/test_log.json')
    
    logger.info("Uygulama başlatıldı", "TEST")
    logger.warning("API limiti yaklaşıyor", "DATA_FETCHER")
    
    try:
        1 / 0
    except Exception as e:
        logger.exception_handler(e, "LOGGER_TEST")
    
    logger.critical("Kritik sistem hatası!", "CORE")