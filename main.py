import tkinter as tk
from ui.main_window import MainWindow
from modules.logger import Logger
from config import API_KEYS, DATABASE_PATH, LOG_PATH
import sys
import os
import traceback

# Uygulamanın ihtiyaç duyduğu dizinleri oluştur
# Bu dizinler loglar, veri ve modeller için kullanılacaktır.
os.makedirs('logs', exist_ok=True)
os.makedirs('data', exist_ok=True)
os.makedirs('models', exist_ok=True)


# Global exception handler
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    # Logger'ı burada başlatın; path artık doğru çalışma dizinine göre ayarlandı.
    logger = Logger(log_file='logs/app_log.json')
    logger.critical(f"Unhandled exception: {exc_value}", "MAIN_APP", extra={'traceback': traceback.format_exception(exc_type, exc_value, exc_traceback)})
    tk.messagebox.showerror("Hata", f"Beklenmedik bir hata oluştu: {exc_value}")

sys.excepthook = handle_exception

def main():
    # Logger'ı başlat
    logger = Logger(log_file='logs/app_log.json')

    # Uygulamanın başladığına dair bir log mesajı ekleyelim
    logger.info("Uygulama başarıyla başlatılıyor...", "MAIN_APP")

    app = MainWindow(logger)

    # Güncelleme döngüsünü, Tkinter'ın ana olay döngüsü başladıktan sonra çalışacak şekilde planlayın.
    # 10ms'lik kısa bir gecikme, mainloop'un tam olarak başlatılmasına olanak tanır.
    app.after(10, app.start_update_cycle)

    app.mainloop() # Tkinter ana olay döngüsünü başlatır

if __name__ == "__main__":
    main()