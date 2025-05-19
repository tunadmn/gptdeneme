# main.py
import tkinter as tk
import sys
from modules.logger import Logger
from ui.main_window import MainWindow

def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler"""
    logger = Logger(log_file='logs/app_log.json')
    logger.error(f"Unhandled exception: {exc_value}", "MAIN")
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

def main():
    """Uygulama başlangıç fonksiyonu"""
    # Global hata yakalama
    sys.excepthook = handle_exception
    
    # Logger ve ana pencereyi başlat
    logger = Logger(log_file='logs/app_log.json')
    app = MainWindow(logger)
    
    try:
        # Tkinter event loop
        app.mainloop()
    except KeyboardInterrupt:
        app.on_close()
        sys.exit(0)

if __name__ == "__main__":
    main()