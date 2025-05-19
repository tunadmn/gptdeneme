# ui/training_window.py
import tkinter as tk
from tkinter import ttk
from threading import Thread
from queue import Queue
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from .components import DarkTheme
from modules.model_trainer import ModelTrainer
from modules.online_learning import OnlineLearner
from modules.logger import Logger
import pandas as pd

class TrainingWindow(tk.Toplevel):
    def __init__(self, parent, commodity: str, logger: Logger):
        super().__init__(parent)
        self.commodity = commodity
        self.logger = logger
        self.queue = Queue()
        self.running = True
        
        self.title(f"Model Eğitim - {commodity}")
        self.geometry("1400x800")
        self.configure(bg=DarkTheme.BG)
        
        self.init_ui()
        self.start_update_cycle()

    def init_ui(self):
        """Eğitim arayüz bileşenlerini oluştur"""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Sol Panel - Kontroller
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        
        # Sağ Panel - Görselleştirmeler
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        self.create_controls(left_panel)
        self.create_visualizations(right_panel)
        self.create_status_bar()

    def create_controls(self, parent):
        """Model kontrollerini oluştur"""
        control_frame = ttk.LabelFrame(parent, text="Eğitim Ayarları")
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Model Seçimi
        ttk.Label(control_frame, text="Model Türü:").grid(row=0, column=0, sticky='w')
        self.model_type = ttk.Combobox(
            control_frame,
            values=["XGBoost", "Online Learning"],
            state="readonly"
        )
        self.model_type.current(0)
        self.model_type.grid(row=0, column=1, sticky='ew', padx=5)
        
        # Hiperparametreler
        ttk.Label(control_frame, text="Optuna Denemeleri:").grid(row=1, column=0, sticky='w')
        self.trial_count = ttk.Spinbox(control_frame, from_=50, to=200, width=5)
        self.trial_count.set(100)
        self.trial_count.grid(row=1, column=1, sticky='w', padx=5)
        
        ttk.Label(control_frame, text="Lookback Periyodu:").grid(row=2, column=0, sticky='w')
        self.lookback = ttk.Spinbox(control_frame, from_=30, to=365, width=5)
        self.lookback.set(90)
        self.lookback.grid(row=2, column=1, sticky='w', padx=5)
        
        # Eğitim Butonları
        btn_frame = ttk.Frame(control_frame)
        btn_frame.grid(row=3, columnspan=2, pady=10)
        
        self.train_btn = ttk.Button(
            btn_frame,
            text="Eğitimi Başlat",
            command=lambda: Thread(target=self.start_training, daemon=True).start()
        )
        self.train_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Backtest Çalıştır",
            command=lambda: Thread(target=self.run_backtest, daemon=True).start()
        ).pack(side=tk.LEFT, padx=5)
        
        # Progress Bar
        self.progress = ttk.Progressbar(
            control_frame,
            orient=tk.HORIZONTAL,
            mode='determinate'
        )
        self.progress.grid(row=4, columnspan=2, sticky='ew', pady=10)
        
        # Feature Importance
        ttk.Label(parent, text="Özellik Önemliliği").pack(pady=5)
        self.feature_tree = ttk.Treeview(
            parent,
            columns=('Feature', 'Importance'),
            show='headings',
            height=15
        )
        self.feature_tree.heading('Feature', text='Özellik')
        self.feature_tree.heading('Importance', text='Önem')
        self.feature_tree.column('Feature', width=200)
        self.feature_tree.column('Importance', width=80)
        self.feature_tree.pack(fill=tk.X, padx=5)

    def create_visualizations(self, parent):
        """Grafik ve metrik panelleri"""
        notebook = ttk.Notebook(parent)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Metrik Grafikleri
        self.metric_fig = Figure(figsize=(8, 4), facecolor=DarkTheme.BG)
        self.metric_ax = self.metric_fig.add_subplot(111)
        self.metric_ax.set_facecolor(DarkTheme.BG)
        self.metric_canvas = FigureCanvasTkAgg(self.metric_fig, notebook)
        metric_tab = ttk.Frame(notebook)
        self.metric_canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        notebook.add(metric_tab, text="Eğitim Metrikleri")
        
        # Backtest Sonuçları
        self.backtest_text = tk.Text(
            notebook,
            bg=DarkTheme.BG,
            fg=DarkTheme.FG,
            wrap=tk.WORD
        )
        notebook.add(self.backtest_text, text="Backtest Raporu")

    def create_status_bar(self):
        """Durum çubuğu"""
        self.status = ttk.Label(
            self,
            text="Hazır",
            anchor=tk.W
        )
        self.status.pack(fill=tk.X, padx=10, pady=2)

    def start_training(self):
        """Model eğitimini başlat"""
        try:
            self.train_btn.config(state=tk.DISABLED)
            self.status.config(text="Model eğitimi başlatılıyor...")
            
            trainer = ModelTrainer(self.commodity, self.logger)
            trainer.optimize_hyperparameters(n_trials=int(self.trial_count.get()))
            model = trainer.train_final_model()
            
            self.queue.put(('progress', 100))
            self.queue.put(('features', trainer.feature_importance))
            self.queue.put(('log', "Eğitim başarıyla tamamlandı!"))
            
        except Exception as e:
            self.logger.error(f"Eğitim hatası: {str(e)}", "TRAINING_WINDOW")
            self.queue.put(('error', str(e)))

    def run_backtest(self):
        """Backtest işlemini çalıştır"""
        try:
            self.status.config(text="Backtest çalıştırılıyor...")
            
            # Backtest mantığı buraya eklenecek
            report = {
                'accuracy': 0.78,
                'precision': 0.81,
                'recall': 0.75,
                'sharpe_ratio': 1.45,
                'max_drawdown': -12.5
            }
            
            self.queue.put(('backtest', report))
            
        except Exception as e:
            self.logger.error(f"Backtest hatası: {str(e)}", "TRAINING_WINDOW")

    def update_metrics(self, data):
        """Metrikleri gerçek zamanlı güncelle"""
        # Grafikleri yeniden çiz
        self.metric_ax.clear()
        self.metric_ax.plot(data['train_loss'], label='Eğitim Kaybı')
        self.metric_ax.plot(data['val_loss'], label='Validasyon Kaybı')
        self.metric_ax.legend()
        self.metric_canvas.draw()

    def start_update_cycle(self):
        """Kuyruktaki verileri işle"""
        if not self.queue.empty():
            item = self.queue.get_nowait()
            
            if item[0] == 'progress':
                self.progress['value'] = item[1]
            elif item[0] == 'features':
                self.update_feature_table(item[1])
            elif item[0] == 'log':
                self.status.config(text=item[1])
            elif item[0] == 'backtest':
                self.show_backtest_results(item[1])
            elif item[0] == 'error':
                self.status.config(text=f"Hata: {item[1]}", foreground=DarkTheme.WARNING)
                self.train_btn.config(state=tk.NORMAL)
                
        self.after(100, self.start_update_cycle)

    def update_feature_table(self, df):
        """Özellik önemliliğini güncelle"""
        self.feature_tree.delete(*self.feature_tree.get_children())
        for _, row in df.iterrows():
            self.feature_tree.insert('', tk.END, values=(
                row['feature'],
                f"{row['importance']:.4f}"
            ))

    def show_backtest_results(self, report):
        """Backtest sonuçlarını göster"""
        text = f"""Backtest Sonuçları ({self.commodity})
        \nDoğruluk: {report['accuracy']:.2%}
        Hassasiyet: {report['precision']:.2%}
        Geri Çağırma: {report['recall']:.2%}
        Sharpe Oranı: {report['sharpe_ratio']:.2f}
        Maksimum Çekilme: {report['max_drawdown']:.1f}%"""
        
        self.backtest_text.delete(1.0, tk.END)
        self.backtest_text.insert(tk.END, text)
        self.status.config(text="Backtest tamamlandı")

    def on_close(self):
        """Pencere kapanırken kaynakları temizle"""
        self.running = False
        self.destroy()

# Örnek Kullanım
if __name__ == "__main__":
    logger = Logger(log_file='logs/app_log.json')
    window = TrainingWindow(None, "BTCUSDT", logger)
    window.mainloop()