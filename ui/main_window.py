# ui/main_window.py
import tkinter as tk
from tkinter import ttk
from threading import Thread
from queue import Queue
from components import (
    GrafikBileseni,
    HaberPaneli,
    APISayac,
    SinyalGostergesi,
    DarkTheme
)
from modules.data_fetcher import DataFetcher
from modules.signal_generator import SignalGenerator
from modules.risk_manager import RiskManager
from modules.sentiment_analyzer import SentimentAnalyzer
from logger import Logger

class MainWindow(tk.Tk):
    def __init__(self, logger: Logger):
        super().__init__()
        self.logger = logger
        self.fetcher = DataFetcher()
        self.running = True
        self.current_commodity = tk.StringVar()
        self.data_queue = Queue()
        
        self.title("Borsa Asistan v1.0")
        self.geometry("1200x800")
        self.configure(bg=DarkTheme.BG)
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        self.init_ui()
        self.start_update_cycle()

    def init_ui(self):
        """Arayüz bileşenlerini oluştur ve yerleştir"""
        # Üst Bilgi Çubuğu
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Emtia Seçimi
        ttk.Label(header_frame, text="Emtia:").pack(side=tk.LEFT, padx=5)
        self.combo = ttk.Combobox(
            header_frame,
            textvariable=self.current_commodity,
            values=["BTCUSDT", "ETHUSDT", "XAUUSD", "EURUSD", "GBPUSD", "CL=F"],
            state="readonly",
            width=10
        )
        self.combo.pack(side=tk.LEFT, padx=5)
        self.combo.current(0)
        self.combo.bind("<<ComboboxSelected>>", self.on_commodity_change)
        
        # API Sayaçları
        self.api_counters = {
            'Binance': APISayac(header_frame, "Binance"),
            'AlphaVantage': APISayac(header_frame, "AlphaVantage"),
            'TwelveData': APISayac(header_frame, "12Data")
        }
        for counter in self.api_counters.values():
            counter.pack(side=tk.LEFT, padx=15)
        
        # Ana İçerik Alanı
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Grafik Paneli
        self.grafik = GrafikBileseni(main_frame)
        self.grafik.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Haber ve Sinyal Paneli
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=5)
        
        self.haber_paneli = HaberPaneli(right_panel)
        self.haber_paneli.pack(fill=tk.X)
        
        # Sinyal ve Risk Göstergeleri
        signal_frame = ttk.Frame(right_panel)
        signal_frame.pack(pady=10)
        
        self.sinyal_gosterge = SinyalGostergesi(signal_frame)
        self.sinyal_gosterge.pack(pady=5)
        
        self.risk_label = ttk.Label(
            signal_frame,
            text="Risk: Yüksek",
            foreground=DarkTheme.WARNING
        )
        self.risk_label.pack()
        
        # Durum Çubuğu
        self.status_bar = ttk.Label(
            self, 
            text="Bağlantı kuruluyor...",
            anchor=tk.W
        )
        self.status_bar.pack(fill=tk.X, padx=10, pady=2)

    def on_commodity_change(self, event):
        """Emtya değiştiğinde verileri yenile"""
        Thread(target=self.load_initial_data, daemon=True).start()

    def load_initial_data(self):
        """Başlangıç verilerini yükle"""
        commodity = self.current_commodity.get()
        self.status_bar.config(text=f"{commodity} verileri yükleniyor...")
        
        try:
            # Veri çek ve temizle
            self.fetcher.parallel_fetch_all(commodity)
            df = self.grafik.update_grafik(
                self.get_historical_data(commodity),
                f"{commodity} Canlı Grafik"
            )
            
            # Haberleri yükle
            analyzer = SentimentAnalyzer()
            haberler = analyzer.fetch_financial_news(commodity)
            self.haber_paneli.haber_ekle(haberler[:5])
            
            self.status_bar.config(text=f"{commodity} verileri güncel")
            
        except Exception as e:
            self.logger.error(f"Veri yükleme hatası: {str(e)}", "MAIN_WINDOW")

    def get_historical_data(self, commodity):
        """Temizlenmiş verileri getir"""
        query = f"""
            SELECT * FROM cleaned_data 
            WHERE commodity='{commodity}'
            ORDER BY timestamp DESC 
            LIMIT 200
        """
        return pd.read_sql(query, self.fetcher.conn)

    def start_update_cycle(self):
        """Gerçek zamanlı güncelleme döngüsünü başlat"""
        def update_loop():
            while self.running:
                try:
                    # API limitlerini güncelle
                    self.api_counters['Binance'].update_sayac(
                        1200 - self.fetcher.api_usage['binance']['remaining'],
                        1200
                    )
                    self.api_counters['AlphaVantage'].update_sayac(
                        500 - self.fetcher.api_usage['alphavantage']['remaining'],
                        500
                    )
                    self.api_counters['TwelveData'].update_sayac(
                        800 - self.fetcher.api_usage['twelvedata']['remaining'],
                        800
                    )
                    
                    # Sinyal üret
                    generator = SignalGenerator(self.current_commodity.get())
                    signal = generator.generate_signals()
                    self.sinyal_gosterge.update_sinyal(signal.get('signal', 'Hold'))
                    
                    # Risk seviyesi
                    risk = RiskManager(self.current_commodity.get()).calculate_total_risk(0.6, 1.5)
                    self.update_risk(risk['risk_level'])
                    
                    # Her 60 saniyede bir veri güncelle
                    self.after(60000, self.load_initial_data)
                    
                except Exception as e:
                    self.logger.error(f"Güncelleme hatası: {str(e)}", "MAIN_WINDOW")
        
        Thread(target=update_loop, daemon=True).start()

    def update_risk(self, risk_level: str):
        """Risk göstergesini güncelle"""
        colors = {
            'High': DarkTheme.WARNING,
            'Medium': '#f39c12',
            'Low': DarkTheme.ACCENT
        }
        self.risk_label.config(
            text=f"Risk: {risk_level}",
            foreground=colors.get(risk_level, DarkTheme.FG)
        )

    def on_close(self):
        """Pencere kapanırken kaynakları temizle"""
        self.running = False
        self.fetcher.conn.close()
        self.destroy()

# Örnek Kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    app = MainWindow(logger)
    app.mainloop()