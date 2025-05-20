import logging
import json
from datetime import datetime
import threading
from typing import Dict, Optional

class Logger:
    """
    Uygulama genelinde standartlaştırılmış ve JSON formatında loglama sağlayan sınıf.
    """
    def __init__(self, log_file: str = 'app_log.json'):
        self.log_file = log_file
        self.lock = threading.Lock() # Günlük yazma sırasında eşzamanlı erişimi yönetmek için kilit
        self.logger = logging.getLogger('TradingAppLogger')
        self.logger.setLevel(logging.INFO) # Varsayılan log seviyesi INFO

        # Logger'a handler'ların yalnızca bir kez eklenmesini sağlar
        self._setup_logger()

    def _setup_logger(self):
        # Logger'a handler'ların zaten eklenip eklenmediğini kontrol et
        if not self.logger.handlers:
            # Dosya handler'ı: Logları belirtilen dosyaya yazar
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(JSONFormatter()) # Özel JSON formatlayıcıyı kullan
            self.logger.addHandler(file_handler)

            # İsteğe bağlı: Konsol çıktısı için StreamHandler (geliştirme sırasında faydalıdır)
            stream_handler = logging.StreamHandler()
            stream_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            self.logger.addHandler(stream_handler)

    def log(self, level: str, message: str, module: str, extra: Optional[Dict] = None) -> None:
        """
        Özelleştirilmiş JSON log kaydı oluşturur.

        Args:
            level (str): Log seviyesi (örn: 'INFO', 'WARNING', 'ERROR', 'CRITICAL').
            message (str): Log mesajı.
            module (str): Logu oluşturan özel modül adı (örn: 'DATA_FETCHER', 'RISK_MANAGER').
            extra (Optional[Dict]): Log kaydına eklenecek ek anahtar-değer çiftleri.
        """
        # LogRecord'a eklenecek özel nitelikler için bir sözlük oluştur.
        # Standart 'module' niteliğiyle çakışmayı önlemek için benzersiz bir anahtar kullanıyoruz.
        log_record_extra = {'custom_module_name': module}

        if extra:
            log_record_extra.update(extra) # Çağıran tarafından sağlanan diğer 'extra' verilerini birleştir

        with self.lock: # Aynı anda yalnızca bir iş parçacığının log yazmasını sağla
            try:
                # Standart Python günlükleme metodunu çağır.
                # 'message' mesaj olarak, 'level' günlükleme seviyesi olarak geçirilir.
                # 'extra' sözlüğü, LogRecord'a eklenecek özel nitelikleri içerir.
                self.logger.log(getattr(logging, level.upper()), message, extra=log_record_extra)
                self._check_for_alert(log_record_extra) # Uyarı kontrolü yap
            except Exception as e:
                print(f"Logging failed: {str(e)}") # Günlükleme hatasını konsola yaz

    def debug(self, message: str, module: str, extra: Optional[Dict] = None) -> None:
        self.log('DEBUG', message, module, extra)

    def info(self, message: str, module: str, extra: Optional[Dict] = None) -> None:
        self.log('INFO', message, module, extra)

    def warning(self, message: str, module: str, extra: Optional[Dict] = None) -> None:
        self.log('WARNING', message, module, extra)

    def error(self, message: str, module: str, extra: Optional[Dict] = None) -> None:
        self.log('ERROR', message, module, extra)

    def critical(self, message: str, module: str, extra: Optional[Dict] = None) -> None:
        self.log('CRITICAL', message, module, extra)

    def shutdown(self):
        """
        Tüm logger handler'larını temizler ve kapatır.
        Uygulama düzgün bir şekilde kapatıldığında çağrılmalıdır.
        """
        self.logger.info("Günlükleme sistemi kapatılıyor ve dosyalar temizleniyor.", "LOGGER_SHUTDOWN")
        for handler in self.logger.handlers[:]: # Liste üzerinde dönerken değiştirmemek için kopyasını kullan
            handler.flush() # Tamponlanmış tüm logları diske yaz
            handler.close() # Handler'ı kapat
            self.logger.removeHandler(handler) # Logger'dan handler'ı kaldır
        self.logger.handlers = [] # Handler listesini temizle

    def _check_for_alert(self, log_data: Dict) -> None:
        """
        Belirli log verilerine göre uyarı tetikleme mantığı.
        Bu metodun içi uygulamanızın gereksinimlerine göre doldurulacaktır.
        """
        # Örneğin:
        # if log_data.get('level') == 'CRITICAL':
        #     # Bir bildirim gönderme veya başka bir uyarı mekanizması tetikleme
        #     print(f"CRITICAL UYARI: {log_data.get('message')}")
        pass # Şu an için boş bırakıldı

class JSONFormatter(logging.Formatter):
    """
    Log kayıtlarını JSON formatına dönüştüren özel formatlayıcı.
    """
    def format(self, record: logging.LogRecord) -> str:
        # Log verisi sözlüğünü JSON çıktısı için oluştur
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(), # LogRecord'dan standart zaman damgası
            'level': record.levelname, # LogRecord'dan standart seviye adı
            # Özel modül adımızı tercih et, yoksa standart record.module'u (log çağrısının yapıldığı modül) kullan
            'module': getattr(record, 'custom_module_name', record.module),
            'message': record.getMessage(), # LogRecord'dan standart mesaj
        }

        # Log metodunda 'extra' dict aracılığıyla geçirilen diğer özel nitelikleri ekle
        # Bu nitelikler LogRecord objesinin doğrudan nitelikleri haline gelir.
        for key, value in record.__dict__.items():
            # Standart LogRecord niteliklerini ve bizim zaten işlediğimiz 'custom_module_name'i dışarıda bırak
            # Ayrıca içsel/özel Python niteliklerini (alt çizgi ile başlayanlar) de dışarıda bırak
            if key not in ['name', 'levelname', 'pathname', 'filename', 'lineno', 'funcName', 'created',
                           'asctime', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process',
                           'exc_info', 'exc_text', 'stack_info', 'msg', 'args', 'module', 'custom_module_name'] and not key.startswith('_'):
                log_data[key] = value

        return json.dumps(log_data, ensure_ascii=False) # JSON formatında döndür